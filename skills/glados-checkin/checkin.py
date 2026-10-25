#!/usr/bin/env python3
"""GLaDOS 自动签到（本地版）

Adapted from https://github.com/Devilstore/Glados-Railgun-checkin (GPL-3.0)
for local use: configuration is read from a `.env` file next to this script
(falling back to real environment variables), instead of GitHub Secrets.
No GitHub Actions required — just run:  python3 checkin.py

Flow per cookie x per domain:
  GET  /api/user/status    -> remaining days
  POST /api/user/checkin   -> check-in (payload {"token": <domain>})
  GET  /api/user/points    -> total points
  POST /api/user/exchange  -> optional auto-exchange (payload {"planType": plan})

Check-in response codes: 0 = success, 1 = already checked in today,
-2 = no permission (cookie expired), 4 = device-mismatch (retry once with
the User-Agent of the platform the account last logged in from).
"""

import os
import sys
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from logging_config import init_logger


def load_dotenv() -> None:
    """Load KEY=VALUE pairs from the .env file next to this script.

    Real environment variables take precedence (a key already present in
    os.environ is not overwritten). Values are taken verbatim after the
    first '=' so cookie strings containing '=' / ';' / '&' survive.
    """
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value


load_dotenv()
logger = init_logger()


class CheckinStatus(Enum):
    """签到状态"""

    SUCCESS = 0
    REPEAT = 1
    FAILURE = -2


class ExchangePlan(Enum):
    """兑换计划"""

    PLAN100 = "plan100"
    PLAN200 = "plan200"
    PLAN500 = "plan500"


class APIEndpoint(Enum):
    """API端点"""

    CHECKIN = "/api/user/checkin"
    STATUS = "/api/user/status"
    POINTS = "/api/user/points"
    EXCHANGE = "/api/user/exchange"


class LogEmoji:
    """日志 Emoji 常量"""

    SUCCESS = "✅"
    FAIL = "❌"
    REPEAT = "🔄"
    CHECKIN = "🎫"
    STATUS = "📊"
    POINTS = "💰"
    EXCHANGE = "🎁"
    START = "🚀"
    END = "🏁"
    COOKIE = "🍪"
    DOMAIN = "🌐"
    WARNING = "⚠️"
    ERROR = "🔴"
    INFO = "ℹ️"


class Config:
    """应用配置（来自 .env / 环境变量）"""

    ENV_PUSH_KEY = "PUSHDEER_SENDKEY"
    ENV_SERVERCHAN_KEY = "SERVERCHAN_SENDKEY"
    ENV_COOKIES = "GLADOS_COOKIES"
    ENV_EXCHANGE_PLAN = "GLADOS_EXCHANGE_PLAN"
    ENV_VERBOSE = "GLADOS_VERBOSE"

    DEFAULT_EXCHANGE_PLAN = "none"  # none 表示不自动兑换
    DEFAULT_VERBOSE = False

    """默认域名（同一账号两个域名都会尝试）"""
    DOMAINS = ["glados.cloud", "railgun.info"]

    EXCHANGE_PLANS = {
        ExchangePlan.PLAN100.value: 100,
        ExchangePlan.PLAN200.value: 200,
        ExchangePlan.PLAN500.value: 500,
    }

    def __init__(self):
        self.push_key: str = os.environ.get(self.ENV_PUSH_KEY, "") or ""
        self.serverchan_key: str = os.environ.get(self.ENV_SERVERCHAN_KEY, "") or ""

        raw_cookies = os.environ.get(self.ENV_COOKIES, "") or ""
        self.cookies_list: List[str] = [
            c.strip() for c in raw_cookies.split("&") if c.strip()
        ]

        plan = (os.environ.get(self.ENV_EXCHANGE_PLAN, "") or "").strip()
        if plan in self.EXCHANGE_PLANS:
            self.exchange_plan = plan
        else:
            if plan and plan != self.DEFAULT_EXCHANGE_PLAN:
                logger.warning(
                    f"{LogEmoji.WARNING} {self.ENV_EXCHANGE_PLAN} 的值 '{plan}' 无效，将跳过自动兑换。"
                )
            self.exchange_plan = self.DEFAULT_EXCHANGE_PLAN

        verbose_raw = (os.environ.get(self.ENV_VERBOSE, "") or "").strip().lower()
        self.verbose = verbose_raw in ("true", "1", "yes", "y")

        logger.info(f"{LogEmoji.INFO} 共加载了 {len(self.cookies_list)} 个 Cookie 用于签到。")
        logger.info(f"{LogEmoji.INFO} 当前 {self.ENV_EXCHANGE_PLAN}: {self.exchange_plan}。")


# 各平台合法 User-Agent（版本号无关，仅平台 token 关键）
PLATFORM_UA = {
    "Windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "macOS": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Linux": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "iPhone": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Android": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
}


class API:
    """GLaDOS API 调用"""

    def __init__(self, domain: str, cookie_index: int = 0, verbose: bool = False):
        self.domain = domain
        self.cookie_index = cookie_index
        self.verbose = verbose
        self.headers: Dict[str, str] = {
            "origin": f"https://{domain}",
            "user-agent": PLATFORM_UA["Windows"],
        }
        self._device_ua_cache: Dict[str, str] = {}
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        # 网络抖动时自动重试（指数退避），避免误报失败
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _log(self, level: str, emoji: str, message: str, force: bool = False) -> None:
        prefix = f"{LogEmoji.COOKIE}[{self.cookie_index}] {LogEmoji.DOMAIN}[{self.domain}]"
        if force or self.verbose:
            getattr(logger, level)(f"{prefix} {emoji} {message}")

    def _url(self, path: str) -> str:
        return f"https://{self.domain}{path}"

    def _make_request(
        self,
        url: str,
        method: str,
        data: Optional[Dict] = None,
        cookies: str = "",
        user_agent: Optional[str] = None,
    ) -> Optional[requests.Response]:
        headers = dict(self.headers)
        if user_agent:
            headers["user-agent"] = user_agent
        headers["cookie"] = cookies
        try:
            if method.upper() == "POST":
                response = self.session.post(url, headers=headers, data=data, timeout=(60, 120))
            elif method.upper() == "GET":
                response = self.session.get(url, headers=headers, timeout=(60, 120))
            else:
                self._log("error", LogEmoji.ERROR, f"不支持的 HTTP 方法: {method}", force=True)
                return None
            if not response.ok:
                self._log(
                    "warning",
                    LogEmoji.WARNING,
                    f"向 {url} 发起的请求失败，状态码 {response.status_code}。响应内容: {response.text}",
                    force=True,
                )
                return None
            return response
        except requests.exceptions.RequestException as e:
            self._log("error", LogEmoji.ERROR, f"向 {url} 发起请求时发生网络错误: {e}", force=True)
            return None

    # ---- 签到 ----
    def checkin(self, cookies: str) -> Dict[str, Union[str, CheckinStatus]]:
        """执行签到，含设备平台自适应重试"""
        url = self._url(APIEndpoint.CHECKIN.value)
        data = {"token": self.domain}
        start_ua = self._device_ua_cache.get("_last") or self.headers.get("user-agent")
        raw = self._checkin_attempt(url, data, cookies, start_ua)
        # 设备不匹配(code 4)时按服务端 loginDevice 切换 UA 重试一次
        if raw is not None and raw.get("code") == 4 and raw.get("reason") == "device-mismatch":
            login_device = raw.get("loginDevice")
            recover_ua = self._device_ua_cache.get(login_device) or PLATFORM_UA.get(login_device)
            if recover_ua and recover_ua != start_ua:
                self._log(
                    "warning",
                    LogEmoji.WARNING,
                    f"设备平台不匹配 (loginDevice={login_device})，切换 UA 重试",
                    force=True,
                )
                raw = self._checkin_attempt(url, data, cookies, recover_ua)
        return self._parse_checkin(raw)

    def _checkin_attempt(self, url: str, data: Dict, cookies: str, user_agent: str) -> Optional[Dict]:
        response = self._make_request(url, "POST", data, cookies, user_agent=user_agent)
        if not response:
            return None
        try:
            raw = response.json()
        except ValueError:
            self._log("error", LogEmoji.ERROR, "签到响应解析失败", force=True)
            return None
        # 缓存学得的设备 UA，供本次运行后续请求复用
        if raw.get("code") == 4 and raw.get("reason") == "device-mismatch":
            login_device = raw.get("loginDevice")
            if login_device in PLATFORM_UA:
                self._device_ua_cache[login_device] = PLATFORM_UA[login_device]
        elif raw.get("code") in (CheckinStatus.SUCCESS.value, CheckinStatus.REPEAT.value):
            self._device_ua_cache["_last"] = user_agent
        return raw

    def _parse_checkin(self, raw: Optional[Dict]) -> Dict[str, Union[str, CheckinStatus]]:
        result: Dict[str, Union[str, CheckinStatus]] = {
            "status": "签到失败",
            "points": "0",
            "message": "",
            "code": CheckinStatus.FAILURE,
        }
        if not raw:
            result["message"] = "网络请求失败"
            return result

        code = raw.get("code", -2)
        message = raw.get("message", "无消息字段")
        points = str(raw.get("points", 0))

        if code == CheckinStatus.SUCCESS.value:
            self._log("info", LogEmoji.SUCCESS, f"{{ code : {code}, points : {points}, message : {message} }}")
            result.update(code=CheckinStatus.SUCCESS, status="签到成功", points=points, message=message)
        elif code == CheckinStatus.REPEAT.value:
            self._log("info", LogEmoji.REPEAT, f"{{ code : {code}, message : {message} }}", force=True)
            result.update(code=CheckinStatus.REPEAT, status="重复签到", points="0", message=message)
        else:
            # 失败分支：按 code 细分诊断，便于快速定位根因
            if code == 4:
                reason = raw.get("reason")
                if reason == "device-mismatch":
                    login_device = raw.get("loginDevice") or "未知"
                    self._log(
                        "error",
                        LogEmoji.ERROR,
                        f"设备平台不匹配(loginDevice={login_device})，重试后仍失败，请确认登录设备平台",
                        force=True,
                    )
                else:
                    self._log(
                        "error",
                        LogEmoji.ERROR,
                        f"服务端拒绝签到(code=4, reason={reason})，请检查账户风控状态",
                        force=True,
                    )
            elif code == -2:
                self._log(
                    "error",
                    LogEmoji.ERROR,
                    f"无权限(code=-2)：Cookie 可能已失效，请重新登录 {self.domain} 刷新 Cookie 并更新 .env 中的 GLADOS_COOKIES 后重试",
                    force=True,
                )
            else:
                self._log(
                    "error",
                    LogEmoji.ERROR,
                    f"未预期响应(code={code}, message={message})，请检查 GLaDOS 服务状态或 Cookie",
                    force=True,
                )
            result.update(code=CheckinStatus.FAILURE, status="签到失败", points="0", message=message)
        return result

    # ---- 状态 / 积分 / 兑换 ----
    def get_status(self, cookies: str) -> Tuple[str, int]:
        """获取剩余天数"""
        response = self._make_request(self._url(APIEndpoint.STATUS.value), "GET", cookies=cookies)
        if response:
            data = response.json()
            code = data.get("code", -2)
            left_days = data.get("data", {}).get("leftDays", None)
            if left_days is not None:
                left_days_int = int(float(left_days))
                self._log("info", LogEmoji.SUCCESS, f"{{ code : {code}, leftDays : {left_days_int} 天}}")
                return f"{left_days_int} 天", code
            self._log("info", LogEmoji.FAIL, f"{{ code : {code}, leftDays : {left_days} 天}}")
            return "None 天", code
        self._log("warning", LogEmoji.WARNING, "获取状态失败")
        return "None 天", -2

    def get_points(self, cookies: str) -> Tuple[str, int]:
        """获取总积分"""
        response = self._make_request(self._url(APIEndpoint.POINTS.value), "GET", cookies=cookies)
        if response:
            data = response.json()
            code = data.get("code", -2)
            points = data.get("points", None)
            if points is not None:
                points_int = int(float(points))
                self._log("info", LogEmoji.SUCCESS, f"{{ code : {code}, points : {points_int} 积分}}")
                return f"{points_int} 积分", points_int
            self._log("info", LogEmoji.FAIL, f"{{ code : {code}, points : {points} 积分}}")
            return "None 积分", 0
        self._log("warning", LogEmoji.WARNING, "获取积分失败")
        return "None 积分", 0

    def exchange(self, cookies: str, plan: str, required_points: int) -> str:
        """执行积分兑换"""
        response = self._make_request(
            self._url(APIEndpoint.EXCHANGE.value), "POST", {"planType": plan}, cookies
        )
        if response:
            data = response.json()
            code = data.get("code", -2)
            message = data.get("message", "未知错误")
            if code == 0:
                self._log("info", LogEmoji.SUCCESS, f"{{ code : {code}, message : {message} }}")
                return f"兑换成功: {plan}"
            self._log("info", LogEmoji.FAIL, f"{{ code : {code}, message : {message} }}", force=True)
            return f"兑换失败: {message}"
        self._log("warning", LogEmoji.WARNING, "兑换失败", force=True)
        return "兑换失败"


@dataclass()
class CheckinResult:
    """单个 cookie x domain 的签到结果"""

    cookie_index: int
    domain: str
    status: str = "签到失败"
    points: str = "0"
    days: str = "None"
    points_total: str = "None"
    exchange: str = "未兑换"
    code: CheckinStatus = CheckinStatus.FAILURE  # 0: 成功, 1: 重复, -2: 失败

    def to_dict(self) -> Dict:
        return asdict(self)


def render_payload(payload: dict, line_sep: str = "\n") -> str:
    """将结构化签到结果渲染为文本。PushDeer 用 \\n，Server酱 用 '  \\n'（Markdown 硬换行）。"""
    lines = []
    for r in payload.get("rows", []):
        line = (
            f"#{r['index']:<2}  {r['emoji']} {r['status']:<6}  {r['domain']:<13}  "
            f"获得 {r['points']} 积分 · 剩余 {r['days']} · 总 {r['points_total']}"
        )
        if r.get("exchange"):
            line += f" · {r['exchange']}"
        lines.append(line)
    note = payload.get("note")
    if note:
        lines.append(note)
    return line_sep.join(lines)


class PushBackend:
    """推送后端抽象基类（策略模式）"""

    name = "base"

    def send(self, title: str, payload: dict) -> bool:
        raise NotImplementedError

    def _render(self, payload: dict) -> str:
        return render_payload(payload, "\n")


class PushDeerBackend(PushBackend):
    name = "PushDeer"

    def __init__(self, push_key: str):
        self.push_key = push_key

    def send(self, title: str, payload: dict) -> bool:
        # 延迟导入：未配置 PushDeer 时不要求安装 pypushdeer
        try:
            from pypushdeer import PushDeer
        except ImportError:
            logger.error(f"{LogEmoji.ERROR} [{self.name}] 推送失败: 未安装 pypushdeer，请先执行 pip install pypushdeer。")
            return False
        try:
            PushDeer(pushkey=self.push_key).send_text(title, desp=self._render(payload))
            return True
        except Exception as e:
            logger.error(f"{LogEmoji.ERROR} [{self.name}] 推送失败: {e}")
            return False


class ServerChanBackend(PushBackend):
    name = "Server酱"

    def __init__(self, send_key: str):
        self.send_key = send_key

    def _render(self, payload: dict) -> str:
        # Server酱 按 Markdown 渲染，单 \n 不换行；用行尾两空格+\n 做硬换行
        return render_payload(payload, "  \n")

    def send(self, title: str, payload: dict) -> bool:
        # 延迟导入：未安装 SDK 时不阻断其他后端
        try:
            from serverchan_sdk import sc_send
        except ImportError:
            logger.error(f"{LogEmoji.ERROR} [{self.name}] 推送失败: 未安装 serverchan_sdk，请先执行 pip install serverchan-sdk。")
            return False
        try:
            resp = sc_send(sendkey=self.send_key, title=title, desp=self._render(payload))
            if isinstance(resp, dict) and resp.get("code") == 0:
                return True
            logger.error(f"{LogEmoji.ERROR} [{self.name}] 推送失败: 接口返回 {resp}")
            return False
        except Exception as e:
            logger.error(f"{LogEmoji.ERROR} [{self.name}] 推送失败: {e}")
            return False


class PushService:
    """推送服务：聚合多个后端，向全部已配置后端发送（都发）"""

    def __init__(self, config: Optional[Config]):
        self.backends: List[PushBackend] = []
        if config:
            if config.push_key:
                self.backends.append(PushDeerBackend(config.push_key))
            if config.serverchan_key:
                self.backends.append(ServerChanBackend(config.serverchan_key))

    def send(self, title: str, payload: dict) -> bool:
        if not self.backends:
            logger.info(f"{LogEmoji.WARNING} 未配置推送密钥，跳过。")
            return False
        names = "、".join(b.name for b in self.backends)
        logger.info(f"{LogEmoji.INFO} 已配置 {len(self.backends)} 个后端（{names}），开始发送")
        results = [backend.send(title, payload) for backend in self.backends]
        if any(results):
            logger.info(f"{LogEmoji.SUCCESS} 发送完成：{sum(results)}/{len(results)} 个后端成功")
            return True
        logger.error(f"{LogEmoji.ERROR} 全部后端发送失败")
        return False


class Checker:
    """签到执行器"""

    def __init__(self, config: Config):
        self.config = config
        self.results: List[CheckinResult] = []

    def _log(self, cookie_idx: int, domain: str, emoji: str, message: str, force: bool = False) -> None:
        if self.config.verbose or force:
            logger.info(f"{LogEmoji.COOKIE}[{cookie_idx}] {LogEmoji.DOMAIN}[{domain}] {emoji} {message}")

    def checkin_all(self) -> None:
        cookie_count = len(self.config.cookies_list)
        domain_count = len(self.config.DOMAINS)
        logger.info(f"{LogEmoji.INFO} 共 {cookie_count} 个 Cookie, {domain_count} 个域名, 共 {cookie_count * domain_count} 个任务")
        task_idx = 0
        for cookie_idx, cookie in enumerate(self.config.cookies_list, 1):
            logger.info(f"{LogEmoji.START} ========== 开始处理 Cookie {cookie_idx} ==========")
            for domain in self.config.DOMAINS:
                task_idx += 1
                logger.info(f"{LogEmoji.INFO} ----- 任务 {task_idx}/{cookie_count * domain_count}: {LogEmoji.COOKIE}[{cookie_idx}] on {LogEmoji.DOMAIN}[{domain}] -----")
                result = self._checkin_on_domain(cookie, cookie_idx, domain)
                self.results.append(result)
                result_message = f"结果: {result.status}"
                if result.code == CheckinStatus.SUCCESS and self.config.verbose:
                    result_message = (
                        f"结果: {result.status}, 获得 {result.points} 积分, "
                        f"剩余 {result.days}, 总 {result.points_total}, {result.exchange}"
                    )
                self._log(
                    cookie_idx,
                    domain,
                    LogEmoji.SUCCESS if result.code == CheckinStatus.SUCCESS else LogEmoji.WARNING,
                    result_message,
                    force=True,
                )

    def _checkin_on_domain(self, cookie: str, cookie_idx: int, domain: str) -> CheckinResult:
        result = CheckinResult(cookie_idx, domain)
        with API(domain, cookie_idx, verbose=self.config.verbose) as api:
            self._log(cookie_idx, domain, LogEmoji.STATUS, "查询剩余天数")
            days_str, _status_code = api.get_status(cookie)
            result.days = days_str

            self._log(cookie_idx, domain, LogEmoji.CHECKIN, "执行签到")
            checkin_result = api.checkin(cookie)
            result.status = checkin_result["status"]
            result.code = checkin_result.get("code", CheckinStatus.FAILURE)
            result.points = str(checkin_result.get("points", "0"))

            self._log(cookie_idx, domain, LogEmoji.POINTS, "查询总积分")
            points_str, _points_num = api.get_points(cookie)
            result.points_total = points_str

            if self.config.exchange_plan in self.config.EXCHANGE_PLANS:
                required_points = self.config.EXCHANGE_PLANS[self.config.exchange_plan]
                self._log(cookie_idx, domain, LogEmoji.EXCHANGE, f"开始兑换 {self.config.exchange_plan} (需要 {required_points} 积分)")
                result.exchange = api.exchange(cookie, self.config.exchange_plan, required_points)
            else:
                result.exchange = "未配置兑换计划，跳过自动兑换"
                self._log(cookie_idx, domain, LogEmoji.INFO, "未配置兑换计划，跳过自动兑换")
        return result

    def format_results(self) -> dict:
        results = [r.to_dict() for r in self.results]
        success_count = sum(1 for r in results if r["code"] == CheckinStatus.SUCCESS)
        repeat_count = sum(1 for r in results if r["code"] == CheckinStatus.REPEAT)
        fail_count = sum(1 for r in results if r["code"] == CheckinStatus.FAILURE)
        emoji_map = {
            CheckinStatus.SUCCESS: LogEmoji.SUCCESS,
            CheckinStatus.REPEAT: LogEmoji.REPEAT,
            CheckinStatus.FAILURE: LogEmoji.ERROR,
        }
        title = f"GLaDOS 签到 · 成功 {success_count} · 失败 {fail_count} · 重复 {repeat_count}"
        rows = []
        for i, res in enumerate(results, 1):
            rows.append(
                {
                    "index": i,
                    "emoji": emoji_map.get(res["code"], LogEmoji.ERROR),
                    "status": res["status"],
                    "domain": res["domain"],
                    "points": res["points"],
                    "days": res["days"],
                    "points_total": res["points_total"],
                    "exchange": res["exchange"],
                }
            )
        return {
            "title": title,
            "rows": rows,
            "success": success_count,
            "fail": fail_count,
            "repeat": repeat_count,
        }


def main() -> int:
    exit_code = 0
    config = None
    try:
        logger.info(f"{LogEmoji.START} 步骤 1: 加载配置")
        config = Config()

        if not config.cookies_list:
            logger.error(f"{LogEmoji.ERROR} 未找到有效的 Cookie, 退出程序。请在脚本同目录的 .env 中设置 GLADOS_COOKIES。")
            payload = {"title": "# 未找到 cookies!", "rows": []}
            exit_code = 1
        else:
            logger.info(f"{LogEmoji.START} 步骤 2: 执行签到")
            checker = Checker(config)
            checker.checkin_all()

            logger.info(f"{LogEmoji.START} 步骤 3: 格式化结果")
            payload = checker.format_results()
            logger.info(f"\n{LogEmoji.END} ========== 签到总结 ==========\n{payload['title']}\n{render_payload(payload)}")
            # 全部失败（如 Cookie 整体失效）时用非零退出码，方便定时任务/上层感知
            if payload["success"] == 0 and payload["repeat"] == 0:
                exit_code = 1
    except Exception as e:
        logger.error(f"{LogEmoji.ERROR} 主程序执行过程中发生未预期的错误: {e}")
        payload = {"title": "# 脚本执行出错", "rows": [], "note": str(e)}
        exit_code = 1

    logger.info(f"{LogEmoji.START} 步骤 4: 发送推送")
    PushService(config).send(payload["title"], payload)
    logger.info(f"{LogEmoji.END} 签到完成")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
