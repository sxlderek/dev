#!/usr/bin/env python3
"""
check_cdn.py - Inspect a website/domain/URL for CDN, edge network, and bot-challenge usage.

Passive inspection only: plain HTTP GET requests, no payload injection, no
challenge triggering. When given a bare domain it also probes /login and
/signup for bot-challenge detection, and it deep-scans linked JS/CSS bundles
for third-party CDN references.

Usage:
  python3 check_cdn.py <url-or-domain>            # JSON summary
  python3 check_cdn.py <url-or-domain> --report   # human-readable report
"""
import sys
import re
import socket
import urllib.request
import urllib.error
import json
from urllib.parse import urlparse, urljoin

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Sub-paths probed for bot challenges when a bare domain is supplied.
AUTO_PROBE_PATHS = ["/login", "/signup"]

# How many linked JS/CSS bundles to fetch during the deep asset crawl.
DEEP_CRAWL_LIMIT = 5

# How many discovered asset hosts to probe with a HEAD-style request.
ASSET_HOST_PROBE_LIMIT = 5

BOT_PROTECTIONS = [
    ("Cloudflare Turnstile", [r"challenges\.cloudflare\.com/turnstile", r"\bcf-turnstile\b"]),
    ("Cloudflare JS Challenge", [r"cdn-cgi/challenge-platform", r"cdn-cgi/js"]),
    ("Arkose Labs (FunCaptcha)", [r"arkoselabs\.com", r"client-api\.arkoselabs\.com"]),
    ("DataDome", [r"datadome\.js", r"api-js\.datadome\.co"]),
    ("PerimeterX / HUMAN", [r"perimeterx\.net", r"px-client", r"client\.perimeterx\.net"]),
    ("Google reCAPTCHA", [r"google\.com/recaptcha", r"recaptcha/api\.js"]),
    ("hCaptcha", [r"hcaptcha\.com/1/api\.js", r"js\.hcaptcha\.com"]),
    ("Kasada", [r"149e1639-", r"ips\.js"]),
]

# Hostname markers seen inside fetched JS/CSS bundles -> CDN label.
THIRD_PARTY_CDN_MARKERS = [
    ("jsdelivr.net", "jsDelivr"),
    ("unpkg.com", "unpkg"),
    ("cdnjs.cloudflare.com", "cdnjs"),
    ("cdnjs.com", "cdnjs"),
    ("bootstrapcdn.com", "BootstrapCDN"),
    ("cloudinary.com", "Cloudinary"),
    ("b-cdn.net", "BunnyCDN"),
    ("bunnycdn", "BunnyCDN"),
    ("keycdn.com", "KeyCDN"),
    ("stackpath", "StackPath"),
    ("fastly.net", "Fastly"),
    ("fastlylb.net", "Fastly"),
    ("cloudfront.net", "AWS CloudFront"),
    ("akamaized.net", "Akamai"),
    ("akamaihd.net", "Akamai"),
    ("azureedge.net", "Azure CDN"),
    ("edgecast", "Edgecast"),
    ("gstatic.com", "Google (gstatic)"),
    ("fonts.googleapis.com", "Google Fonts"),
    ("googleapis.com", "Google APIs"),
    ("fontawesome.com", "Font Awesome CDN"),
    ("uicdn", "uiCDN"),
    ("staticfile.org", "Staticfile"),
    ("hwcdn.net", "hwCDN (StackPath)"),
    ("netdna", "MaxCDN/StackPath"),
    ("edgekey.net", "Akamai (edgekey)"),
    ("cdn-cgi", "Cloudflare (cdn-cgi)"),
    ("githubusercontent.com", "GitHub raw assets"),
    ("github.io", "GitHub Pages"),
]

HOSTNAME_RE = re.compile(r"(?:https?:)?//([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")
ASSET_REF_RE = re.compile(r"(?:src|href)\s*=\s*[\"']([^\"']+)[\"']", re.I)
# Asset-host discovery is limited to <script src> and <link href> per spec,
# so footer/nav anchors (x.com, youtube.com, ...) are excluded.
ASSET_TAG_RE = re.compile(
    r"<script[^>]+src\s*=\s*[\"']([^\"']+)[\"']|<link[^>]+href\s*=\s*[\"']([^\"']+)[\"']",
    re.I,
)


def asset_tag_refs(body):
    """URLs referenced by <script src> / <link href> tags only."""
    out = []
    for m in ASSET_TAG_RE.finditer(body):
        ref = (m.group(1) or m.group(2) or "").strip()
        if ref and not ref.startswith(("data:", "#", "javascript:", "mailto:")):
            out.append(ref)
    return out


def get_asn_info(ip):
    try:
        req = urllib.request.Request(
            f"https://rdap.arin.net/registry/ip/{ip}",
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            name = data.get("name", "") or ""
            org = (data.get("customer", {}) or {}).get("name", "") or data.get("name", "") or ""
            return (org or name or "Unknown ASN/Org").strip()
    except Exception:
        return "Unknown ASN/Org"


def fetch(url, timeout=8):
    """Passive GET. Returns (headers_lower_dict, body_text, status)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return ({k.lower(): v for k, v in resp.headers.items()},
                    resp.read().decode("utf-8", errors="ignore"),
                    resp.status)
    except urllib.error.HTTPError as e:
        return ({k.lower(): v for k, v in e.headers.items()},
                e.read().decode("utf-8", errors="ignore"),
                e.code)
    except Exception as e:
        return {}, "", f"ERR: {type(e).__name__}: {e}"


def detect_cdns(headers):
    """Map response headers to a CDN/edge provider list."""
    h = {k.lower(): v for k, v in headers.items()}
    server = h.get("server", "").lower()
    via = h.get("via", "").lower()
    out = []
    if "cloudflare" in server or "cf-ray" in h or "cf-cache-status" in h:
        out.append("Cloudflare")
    if "cloudfront" in via or "x-amz-cf-id" in h or "x-amz-cf-pop" in h:
        out.append("AWS CloudFront")
    if "varnish" in via or "x-served-by" in h or "fastly-restarts" in h or "x-fastly-request-id" in h:
        out.append("Fastly")
    if "akamaighost" in server or "x-akamai-transformed" in h or "x-akamai-request-id" in h:
        out.append("Akamai")
    if "sucuri" in server or "x-sucuri-id" in h:
        out.append("Sucuri")
    if "x-iinfo" in h or "incap_ses" in h:
        out.append("Imperva / Incapsula")
    if "x-azure-ref" in h or "x-fd-features" in h:
        out.append("Azure Front Door")
    if "a8c-cdn" in h.get("server-timing", "").lower():
        out.append("a8c-cdn (self-hosted)")
    return out


def detect_protections(body):
    """Scan an HTML/JS body for bot-challenge fingerprints."""
    found = []
    if not body:
        return found
    for name, patterns in BOT_PROTECTIONS:
        for p in patterns:
            if re.search(p, body, re.I):
                found.append(name)
                break
    return found


def build_probe_list(url):
    """Bare domain -> target plus /login and /signup. Explicit path -> target only."""
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    target_path = p.path or "/"
    paths = [target_path]
    if target_path == "/":
        for extra in AUTO_PROBE_PATHS:
            if extra not in paths:
                paths.append(extra)
    return [(path, base + path) for path in paths]


def extract_asset_urls(body, base_url):
    """Linked .js/.css bundles, absolute, deduped, order-preserving."""
    out = []
    for ref in ASSET_REF_RE.findall(body):
        ref = ref.strip()
        if ref.startswith(("data:", "#", "javascript:", "mailto:")):
            continue
        if not re.search(r"\.(js|mjs|css)(\?|$)", ref, re.I):
            continue
        absu = urljoin(base_url, ref)
        if absu not in out:
            out.append(absu)
    return out


def crawl_assets(asset_urls):
    """Fetch up to DEEP_CRAWL_LIMIT bundles, scan payloads for third-party CDN refs."""
    scanned = []
    third_party = {}  # label -> sorted [hosts]
    for u in asset_urls[:DEEP_CRAWL_LIMIT]:
        hdrs, body, status = fetch(u, timeout=6)
        hosts = set(HOSTNAME_RE.findall(body))
        for host in hosts:
            low = host.lower()
            for marker, label in THIRD_PARTY_CDN_MARKERS:
                if marker in low:
                    third_party.setdefault(label, set()).add(low)
        scanned.append({
            "url": u,
            "status": status,
            "cdn": detect_cdns(hdrs),
            "hosts_referenced": len(hosts),
        })
    return scanned, {k: sorted(v) for k, v in sorted(third_party.items())}


def probe_asset_hosts(asset_hosts):
    """Request the asset host root and detect its edge CDN from headers."""
    detected = {}
    for host in asset_hosts[:ASSET_HOST_PROBE_LIMIT]:
        scheme = "https"
        hdrs, _, status = fetch(f"{scheme}://{host}", timeout=5)
        if isinstance(status, str) and status.startswith("ERR"):
            continue
        cdns = detect_cdns(hdrs)
        if cdns:
            detected[host] = cdns
    return detected


def check(target):
    if not target.startswith(("http://", "https://")):
        url = "https://" + target
    else:
        url = target
    parsed = urlparse(url)
    hostname = parsed.hostname

    result = {
        "url": url,
        "hostname": hostname,
        "ip": None,
        "asn_org": None,
        "probes": [],
        "main_cdn": [],
        "main_headers": {},
        "asset_hosts": [],
        "asset_cdns": {},
        "deep_crawl": {"bundles_found": 0, "bundles_scanned": 0, "scanned": [], "third_party_refs": {}},
        "bot_protections": [],
    }

    try:
        ip = socket.gethostbyname(hostname)
        result["ip"] = ip
        result["asn_org"] = get_asn_info(ip)
    except Exception as e:
        result["ip"] = f"DNS Error: {e}"

    protections = set()
    main_body = ""
    main_url = None

    for path, probe_url in build_probe_list(url):
        hdrs, body, status = fetch(probe_url, timeout=10)
        entry = {
            "path": path,
            "status": status,
            "server": hdrs.get("server", ""),
            "cdn": detect_cdns(hdrs),
            "protections": detect_protections(body),
        }
        result["probes"].append(entry)
        protections.update(entry["protections"])
        for c in entry["cdn"]:
            if c not in result["main_cdn"]:
                result["main_cdn"].append(c)
        if main_url is None:
            main_url = probe_url
            main_body = body
            result["main_headers"] = hdrs

    # Asset host discovery from the main document.
    asset_hosts = set()
    asset_urls = extract_asset_urls(main_body, main_url or url)
    for ref in asset_tag_refs(main_body):
        hp = urlparse(urljoin(main_url or url, ref))
        if hp.hostname and hp.hostname != hostname:
            asset_hosts.add(hp.hostname)
    for a in sorted(asset_urls):
        hp = urlparse(a)
        if hp.hostname and hp.hostname != hostname:
            asset_hosts.add(hp.hostname)

    result["asset_hosts"] = sorted(asset_hosts)
    result["deep_crawl"]["bundles_found"] = len(asset_urls)
    scanned, third_party = crawl_assets(asset_urls)
    result["deep_crawl"]["scanned"] = scanned
    result["deep_crawl"]["bundles_scanned"] = len(scanned)
    result["deep_crawl"]["third_party_refs"] = third_party
    result["asset_cdns"] = probe_asset_hosts(result["asset_hosts"])

    result["bot_protections"] = sorted(protections)
    # Convenience: which paths exposed which protections.
    result["protections_by_path"] = {
        e["path"]: e["protections"] for e in result["probes"] if e["protections"]
    }
    return result


def render_report(r):
    lines = [f"Target: {r['url']}", ""]

    cdns = ", ".join(r["main_cdn"]) if r["main_cdn"] else "Direct origin (no third-party CDN signature)"
    h = {k: v for k, v in r["main_headers"].items()
         if k in ("server", "via", "cf-ray", "cf-cache-status", "x-cache", "x-served-by",
                  "server-timing", "x-amz-cf-pop", "x-azure-ref")}
    notable = "; ".join(f"{k}: {v}" for k, v in h.items()) or "none"
    lines += [
        "1. Dynamic HTML pages:",
        f"- Origin / Edge: {r['asn_org']} (IP: {r['ip']})",
        f"- CDN Status: {cdns}",
        f"- Notable Headers: {notable}",
        "",
        "2. Static assets & media:",
        f"- Asset Host(s): {', '.join(r['asset_hosts']) or 'none (same-origin only)'}",
    ]
    if r["asset_cdns"]:
        for host, cdns_list in r["asset_cdns"].items():
            lines.append(f"- {host}: {', '.join(cdns_list)}")
    else:
        lines.append("- Asset host CDN: none detected")
    dc = r["deep_crawl"]
    lines.append(f"- Deep scan: {dc['bundles_scanned']}/{dc['bundles_found']} linked JS/CSS bundles fetched")
    if dc["third_party_refs"]:
        for label, hosts in dc["third_party_refs"].items():
            shown = ", ".join(hosts[:3]) + (f" (+{len(hosts)-3} more)" if len(hosts) > 3 else "")
            lines.append(f"    * {label}: {shown}")
    else:
        lines.append("- Third-party CDN references: none detected")

    lines += ["", "3. Bot Challenge / WAF / Turnstile:"]
    lines.append(f"- Probed path(s): {', '.join(e['path'] for e in r['probes'])}")
    turnstile = "Cloudflare Turnstile" in r["bot_protections"]
    lines.append(f"- Cloudflare Turnstile: {'Present' if turnstile else 'Not detected'}")
    others = [p for p in r["bot_protections"] if p != "Cloudflare Turnstile"]
    lines.append(f"- Other Protections: {', '.join(others) if others else 'None detected'}")
    if r["protections_by_path"]:
        for path, found in r["protections_by_path"].items():
            lines.append(f"    * {path}: {', '.join(found)}")
    return "\n".join(lines)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_report = "--report" in sys.argv
    if not args:
        print("Usage: check_cdn.py <url-or-domain> [--report]")
        sys.exit(1)
    data = check(args[0])
    print(render_report(data) if as_report else json.dumps(data, indent=2))
