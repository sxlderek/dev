---
name: cdn-checker
description: "Use when checking if a URL/domain is on a CDN or WAF. Passively detects CDN, split-CDN assets, and bot challenges."
version: 1.1.0
author: Hermes
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cdn, cloudflare, turnstile, fastly, cloudfront, akamai, waf, networking]
---

# cdn-checker

Determine whether a website, domain, or URL is hosted behind a CDN, uses split-CDN architecture for static assets, or employs anti-bot/WAF solutions like Cloudflare Turnstile.

## When to Use

- User asks "is this on a CDN?", "is <url> behind Cloudflare?", or provides a domain to check.
- Checking edge routing, origin IP leakage, or CDN provider signatures.
- Checking whether Cloudflare Turnstile, Arkose Labs, or other challenge mechanisms are present.

## Standing Rules

- **Passive only.** Send standard HTTP GET requests and inspect what the server returns. Never inject payloads, never probe with attack strings, never attempt to trigger a challenge page. The user approved passive inspection only.
- **Deep asset scan is on.** After the main document, fetch linked JS/CSS bundles and scan them for third-party CDN references.
- **Auto sub-path probing.** A bare domain (no path) also probes `/login` and `/signup` for bot-challenge detection. An explicit path (e.g. `example.com/checkout`) probes only that path.

## Architecture & Detection Layers

A modern website often uses a **split architecture**:
1. **Dynamic HTML Document:** May be served directly by origin, cloud provider edge (Azure, AWS, GCP), or CDN proxy (Cloudflare, Akamai).
2. **Static Assets & Media:** Often offloaded to specialized CDNs (Fastly, CloudFront, Akamai, Cloudflare, KeyCDN) via subdomains (`assets.*`, `cdn.*`, `*.githubassets.com`), and bundles may reference further third-party CDNs (jsDelivr, unpkg, cdnjs, cloudinary).
3. **Bot / Challenge Protection:** Turnstile, Arkose Labs, PerimeterX/HUMAN, DataDome, reCAPTCHA, etc., often on auth routes rather than the landing page.

## Step-by-Step Inspection Procedure

### Step 1: Normalize Input
Extract:
- Base hostname (`example.com`)
- Target URL (`https://example.com/`)
- Probe list: target path, plus `/login` and `/signup` when the input has no explicit path.

### Step 2: Probe Each Path
Run the consolidated checker (passive GETs only):
```bash
python3 scripts/check_cdn.py <url-or-domain> --report
```
Per path it collects:
- **IP & ASN:** DNS resolve + RDAP/ARIN ASN lookup.
- **HTTP Response Headers:** `server`, `via`, `cf-ray`, `cf-cache-status`, `x-amz-cf-*`, `x-served-by`, `x-cache`, `x-akamai-*`, `x-azure-ref`, `server-timing` (catches self-hosted edges like `a8c-cdn`).
- **Bot fingerprints in body:** Turnstile (`challenges.cloudflare.com/turnstile`, `.cf-turnstile`), Cloudflare JS challenge (`cdn-cgi/challenge-platform`), Arkose Labs, DataDome, PerimeterX/HUMAN, reCAPTCHA, hCaptcha, Kasada.

### Step 3: Asset & Deep Bundle Analysis
- Discover asset hosts from `<link>` / `<script src>` URLs whose host differs from the target; probe each (up to 5) for its edge CDN headers.
- Fetch up to 5 linked `.js`/`.mjs`/`.css` bundles and scan their payloads for third-party CDN hosts (jsDelivr, unpkg, cdnjs, BootstrapCDN, Cloudinary, BunnyCDN, KeyCDN, Fastly, CloudFront, Akamai, Azure CDN, gstatic, Google Fonts, Font Awesome, etc.).

### Step 4: Output Structured Summary Report

Use the script's `--report` output, or this format:

```text
Target: https://<domain>

1. Dynamic HTML pages:
- Origin / Edge: [Provider Name / Self-hosted / Cloud host] (IP: <ip>, ASN: <asn> <org>)
- CDN Status: [Direct / Proxied behind <CDN> / no third-party CDN signature]
- Notable Headers: [e.g. server: cloudflare, cf-ray, etc.]

2. Static assets & media:
- Asset Host(s): [<subdomain / CDN URL>]
- CDN Provider: [Fastly / CloudFront / Akamai / etc.]
- Signature Headers: [via: ..., x-served-by: ...]
- Deep scan: <n>/<m> linked JS/CSS bundles fetched
- Third-party CDN refs: [provider (host), ...] / none detected

3. Bot Challenge / WAF / Turnstile:
- Probed path(s): /, /login, /signup
- Cloudflare Turnstile: [Present / Not detected]
- Other Protections: [None / Arkose Labs / DataDome / PerimeterX / etc.]
    * <path>: [protections found there]
```

## Dependencies

- Python 3 stdlib only (urllib, socket, json, re) — no pip installs required.
- Network egress to the target, plus `rdap.arin.net` for ASN lookups (degrades gracefully to "Unknown ASN/Org" if blocked).
