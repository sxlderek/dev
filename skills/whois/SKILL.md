---
name: whois
description: "Look up domain WHOIS, DNS records, email security (DMARC/SPF/DKIM), and TLS details with optional screenshot."
version: 1.1.0
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [whois, dns, domain, security, email, tls]
    related_skills: []
---

# whois

Look up domain WHOIS information, DNS records, email security (DMARC/SPF/DKIM), and TLS details with an optional website screenshot.

## When to Use

Trigger when user types `whois` followed by a domain input.

### Input Processing Rules:
- Strip `https://`, `http://`, `www.` prefixes
- If input contains `@`, extract domain part after `@` (e.g., `user@example.com` → `example.com`)
- Convert non-ASCII (IDN) domains to Punycode automatically (e.g., `秒秒指南.com` → `xn--6krx87aehra.com`)

---

## Security Considerations

- **Input validation:** Only allow alphanumeric, hyphen, and dot characters after domain extraction. Reject anything else.
- **Command injection prevention:** Never interpolate user input directly into shell strings. Use `shlex.quote()` or subprocess with argument arrays.
- **Timeouts:** Every external call must have a bounded timeout (10s for WHOIS/DNS, 10s for TLS, 5s for screenshot capture).
- **Headless Screenshot Pitfall**: Running headless Chromium or Puppeteer inside minimal Docker containers without display servers can hang indefinitely waiting for IPC/page load events. Apply strict execution timeouts (max 5s) with fallback to external screenshot APIs (e.g., WordPress mShots `https://s0.wp.com/mshots/v1/...`) or omit the screenshot if rendering fails.
- **Error handling:** On failure, return a generic user-friendly message and keep details internal.
- **Output sanitization:** Build the final message as a single string before sending; never send partial responses.