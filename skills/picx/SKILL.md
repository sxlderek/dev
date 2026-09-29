---
name: picx
description: Image hosting and management via GitHub API (PicX-style). Upload images to GitHub repos, generate CDN links in Markdown/HTML/BBCode, compress images, add watermarks, and manage directories.
tags: [image-hosting, github, picx, cdn, image-tools, imgx]
---

# PicX Image Hosting Skill

Image hosting and management via GitHub API, providing PicX-style features without the web UI.

## When to Use

- Upload local images to a GitHub repo for public hosting
- Generate CDN links in Markdown, HTML, or BBCode format
- Compress images before upload
- Add watermarks to images
- Manage image directories in a GitHub repo
- Batch upload, delete, or copy image links

## Prerequisites

- `IMGX_TOKEN` in the Hermes `.env` file (a GitHub personal access token with `repo` scope — same token PicX web UI uses)
- `magick` (ImageMagick) for compression and watermarking
- GitHub repo for hosting (default: `<OWNER>/<REPO>`)

## Authentication

The script reads `IMGX_TOKEN` from `~/AppData/Local/hermes/.env` (Windows) or `~/.hermes/.env` (Linux/macOS).

### Personal Access Token (PAT) Issues

The `GITHUB_TOKEN` in `.env` can return 401 Bad Credentials even with full `repo` scope. This happens when:

- The PAT was created on a different machine/user
- The PAT is fine-grained and lacks Contents read/write permission
- The PAT has expired or been revoked
- GitHub fails silently and the token passes only basic auth

**Debug steps:**

```bash
gh auth status
gh api user
gh api repos/<OWNER>/<REPO>/contents/ --jq '.[].name'
```

If `gh` works but direct token auth via `curl` fails, use `gh auth token`:

```bash
TOKEN=$(gh auth token)
curl -s -X PUT https://api.github.com/repos/owner/repo/contents/path \
  -H "Authorization: token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"test","content":"dGVzdA=="}'
```

Or just use `gh api` — it auto-handles auth:

```bash
gh api repos/{owner}/{repo}/contents/{path} --field message="Upload" --field content="$(base64 -w0 file.jpg)"
```

### Preventing 401s

- Always use `gh auth token` instead of the raw env var for curl.
- For library requests in Python, `gh` auth's token via subprocess is more reliable than env var.
- Use the test `gh api repos/{owner}/{repo}/contents/` to verify the PAT and repo target before bulk operations.

## Commands

All commands live in `scripts/picx.py`:

### Upload

```bash
python3 scripts/picx.py upload <image_path> [--repo REPO] [--dir DIR] [--name NAME] [--compress] [--watermark TEXT]
```

### Delete

```bash
python3 scripts/picx.py delete <image_path_in_repo> [--repo REPO]
```

### List

```bash
python3 scripts/picx.py list [--repo REPO] [--dir DIR]
```

### Generate Link

```bash
python3 scripts/picx.py link <image_path> [--format markdown|html|bbcode|url] [--cdn github|github-pages|jsdelivr|statically]
```

### Batch Upload

```bash
python3 scripts/picx.py batch <image1> <image2> ... [--dir DIR] [--compress]
```

### Compress (local only)

```bash
python3 scripts/picx.py compress <image_path> [--quality 85] [--output OUTPUT]
```

### Watermark (local only)

```bash
python3 scripts/picx.py watermark <image_path> "Text" [--position bottom-right] [--opacity 50]
```

## CDN URL Patterns

| CDN | Pattern |
|---|---|
| `github` | `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}` |
| `jsdelivr` | `https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}` |
| `statically` | `https://cdn.statically.io/gh/{owner}/{repo}/{branch}/{path}` |

## Output Rules

- Return image links as **plain URL only** (no prefix text)
- Batch uploads return one URL per line
- CDN link formats: `![alt](url)` for markdown, `<img>` for html, `[img]url[/img]` for bbcode

## Examples

```bash
# Upload with compression to default repo
python3 scripts/picx.py upload photo.jpg --compress --repo <OWNER>/<REPO> --dir .

# Generate Markdown link via jsDelivr CDN
python3 scripts/picx.py link images/photo.jpg --format markdown
```

## Pitfalls

### Files uploaded via API don't show in PicX web UI

Files uploaded directly to the GitHub repo via API (or this script) will NOT appear in the PicX web management interface at `picx.xpoet.cn/#/management`. PicX maintains its own internal file index separate from the raw repo contents. The files ARE in the repo and accessible via CDN links — they just won't be listed in PicX's management page.

### ImageMagick resize syntax

Use quoted dimensions: `-resize "1920x1920>"`. Without quotes, ImageMagick interprets `>` as a shell redirect on most platforms.

### `gh api` argument parsing

Avoid using `gh api` subprocess for PUT/POST operations with JSON payloads. The `gh` CLI misinterprets JSON content as extra positional arguments. Use `curl` with `Authorization: token $IMGX_TOKEN` instead.

### Renaming a repo safely

The `gh` CLI does NOT support `--name` on `gh repo edit` (unknown flag error). Two reliable methods:

```bash
# Method 1 (preferred): gh api
gh api repos/owner/old-name --field name=new-name -X PATCH

# Method 2: curl with token
curl -X PATCH "https://api.github.com/repos/owner/old-name" \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"new-name"}'
```

After renaming, update your local remote and any hardcoded repo references. The GitHub Pages CDN URLs (`cdn.jsdelivr.net/gh/owner/repo@branch/path`) change with the repo name.

## Implementation Notes

- Uses `curl` with `IMGX_TOKEN` for all GitHub API operations
- Uses ImageMagick (`magick`) for compression/watermarking
- Auto-generates unique filenames with timestamp hash on name collision
- Converts to JPG when `--name` ends in `.jpg`/`.jpeg` and source is a different format
- Supports: PNG, JPG, JPEG, GIF, WebP, BMP, TIFF, SVG