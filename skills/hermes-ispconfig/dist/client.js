"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ISPConfigClient = void 0;
const node_http_1 = __importDefault(require("node:http"));
const node_https_1 = __importDefault(require("node:https"));
const node_url_1 = require("node:url");
const errors_1 = require("./errors");
class ISPConfigClient {
    config;
    url;
    timeoutMs;
    verifySsl;
    sessionId = null;
    isLoggingIn = false;
    constructor(config) {
        this.config = config;
        this.url = new node_url_1.URL(config.apiUrl);
        this.timeoutMs = config.timeoutMs ?? 20_000;
        this.verifySsl = config.verifySsl ?? true;
    }
    async login() {
        if (this.sessionId) {
            return this.sessionId;
        }
        if (this.isLoggingIn) {
            await new Promise((resolve) => setTimeout(resolve, 150));
            return this.login();
        }
        this.isLoggingIn = true;
        try {
            const res = await this.rawCall("login", {
                username: this.config.username,
                password: this.config.password,
            }, true);
            if (!res || typeof res !== "string") {
                throw new errors_1.ISPConfigError("auth_error", "ISPConfig login failed: no session_id returned");
            }
            this.sessionId = res;
            return this.sessionId;
        }
        finally {
            this.isLoggingIn = false;
        }
    }
    async logout() {
        if (!this.sessionId) {
            return { ok: true, message: "No active session" };
        }
        try {
            return await this.rawCall("logout", { session_id: this.sessionId }, true);
        }
        finally {
            this.sessionId = null;
        }
    }
    async call(method, params = {}) {
        const sessionId = await this.login();
        try {
            return await this.rawCall(method, { session_id: sessionId, ...params }, true);
        }
        catch (error) {
            if (!this.shouldRetrySession(error)) {
                throw error;
            }
            this.sessionId = null;
            const refreshed = await this.login();
            return this.rawCall(method, { session_id: refreshed, ...params }, true);
        }
    }
    shouldRetrySession(error) {
        if (error instanceof errors_1.ISPConfigError) {
            return error.code === "auth_error" && error.retryable;
        }
        if (!(error instanceof Error)) {
            return false;
        }
        const msg = error.message.toLowerCase();
        return msg.includes("session") || msg.includes("invalid") || msg.includes("expired") || msg.includes("auth");
    }
    async rawCall(method, body, unwrapEnvelope) {
        const methodUrl = new node_url_1.URL(this.url.toString());
        methodUrl.search = method;
        const payload = JSON.stringify(body);
        const protocol = methodUrl.protocol === "https:" ? node_https_1.default : node_http_1.default;
        const requestOptions = {
            method: "POST",
            hostname: methodUrl.hostname,
            port: methodUrl.port,
            path: `${methodUrl.pathname}${methodUrl.search}`,
            headers: {
                "content-type": "application/json",
                "content-length": Buffer.byteLength(payload),
            },
            timeout: this.timeoutMs,
            rejectUnauthorized: this.verifySsl,
        };
        const raw = await new Promise((resolve, reject) => {
            const req = protocol.request(requestOptions, (res) => {
                const chunks = [];
                res.on("data", (chunk) => chunks.push(chunk));
                res.on("end", () => {
                    const txt = Buffer.concat(chunks).toString("utf8");
                    const status = res.statusCode ?? 500;
                    if (status >= 400) {
                        const code = status === 401 ? "auth_error"
                            : status === 403 ? "permission_denied"
                                : "api_error";
                        reject(new errors_1.ISPConfigError(code, `ISPConfig HTTP ${status}: ${txt}`, {
                            statusCode: status,
                            retryable: status >= 500 || status === 401,
                        }));
                        return;
                    }
                    resolve(txt);
                });
            });
            req.on("timeout", () => {
                req.destroy(new errors_1.ISPConfigError("network_error", `ISPConfig request timeout after ${this.timeoutMs}ms`, { retryable: true }));
            });
            req.on("error", (err) => {
                if (err instanceof errors_1.ISPConfigError) {
                    reject(err);
                }
                else {
                    reject(new errors_1.ISPConfigError("network_error", err.message, {
                        retryable: true,
                        cause: err,
                    }));
                }
            });
            req.write(payload);
            req.end();
        });
        let parsed;
        try {
            parsed = JSON.parse(raw);
        }
        catch {
            throw new errors_1.ISPConfigError("parse_error", `ISPConfig returned non-JSON response: ${raw}`);
        }
        if (!unwrapEnvelope) {
            return parsed;
        }
        const envelope = parsed;
        if (envelope.code && envelope.code !== "ok") {
            const msg = `ISPConfig API ${envelope.code}: ${envelope.message ?? "Unknown error"}`;
            const errorCode = (0, errors_1.classifyApiMessage)(msg);
            throw new errors_1.ISPConfigError(errorCode, msg, {
                retryable: errorCode === "auth_error",
            });
        }
        if (Object.prototype.hasOwnProperty.call(envelope, "response")) {
            return envelope.response;
        }
        return parsed;
    }
}
exports.ISPConfigClient = ISPConfigClient;
//# sourceMappingURL=client.js.map