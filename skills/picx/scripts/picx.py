#!/usr/bin/env python3
"""PicX-style image hosting via GitHub API with IMGX_TOKEN."""
import argparse, base64, json, os, re, subprocess, sys, time
from pathlib import Path

DEFAULT_REPO = os.getenv("PICX_REPO", "<OWNER>/<REPO>")
DEFAULT_BRANCH = "master"
DEFAULT_DIR = "images"

CDN_TEMPLATES = {
    "github": "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}",
    "github-pages": "https://{owner}.github.io/{repo}/{path}",
    "jsdelivr": "https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}",
    "statically": "https://cdn.statically.io/gh/{owner}/{repo}/{branch}/{path}",
}

def load_env():
    """Load GitHub token from environment or .env."""
    token = os.getenv("GITHUB_TOKEN") or os.getenv("IMGX_TOKEN")
    if token:
        return token
    for p in ['.env', os.path.expanduser('~/.env')]:
        if os.path.exists(p):
            try:
                with open(p) as f:
                    content = f.read()
                m = re.search(r'(?:GITHUB_TOKEN|IMGX_TOKEN)\s*=\s*"?([^"\' \n#]+)', content)
                if m:
                    return m.group(1).strip()
            except Exception:
                pass
    return None

def run(cmd, check=True):
    """Run a shell command."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result

def gh_api(method, path, data=None, token=None):
    """Make a GitHub API call via curl with IMGX_TOKEN."""
    import tempfile
    url = f"https://api.github.com{path}"
    cmd = ['curl', '-s', '-X', method, url,
           '-H', f'Authorization: token {token}',
           '-H', 'Accept: application/vnd.github.v3+json',
           '-H', 'Content-Type: application/json']
    if data:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            tmp_path = f.name
        cmd.extend(['-d', f'@{tmp_path}'])
        result = subprocess.run(cmd, capture_output=True, text=True)
        os.unlink(tmp_path)
    else:
        result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"API Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)

def get_repo_info(repo):
    """Extract owner and repo name."""
    parts = repo.split("/")
    return parts[0], parts[1]

def upload_image(image_path, repo=DEFAULT_REPO, branch=DEFAULT_BRANCH, directory=DEFAULT_DIR, name=None, compress=False, watermark=None, token=None):
    """Upload an image to GitHub via PicX-style API."""
    image_path = Path(image_path)
    if not image_path.exists():
        print(f"Error: {image_path} not found", file=sys.stderr)
        sys.exit(1)
    
    # Compress if requested
    if compress:
        temp_path = image_path.with_suffix(".compressed" + image_path.suffix)
        run(f'magick "{image_path}" -quality 85 -resize "1920x1920>" "{temp_path}"')
        image_path = temp_path
    
    # Convert to JPEG if name ends with .jpg or .jpeg but image isn't
    if name and (name.endswith(".jpg") or name.endswith(".jpeg")) and not image_path.suffix.lower() in [".jpg", ".jpeg"]:
        temp_path = image_path.with_suffix(".jpg")
        run(f'magick "{image_path}" "{temp_path}"')
        if str(temp_path) != str(image_path):
            image_path.unlink(missing_ok=True)
        image_path = temp_path
    
    # Add watermark if requested
    if watermark:
        temp_path = image_path.with_suffix(".watermarked" + image_path.suffix)
        gravity = "SouthEast"
        run(f'magick "{image_path}" -gravity {gravity} -pointsize 30 -fill "rgba(255,255,255,0.5)" -annotate +10+10 "{watermark}" "{temp_path}"')
        image_path = temp_path
    
    # Generate unique filename
    if name is None:
        stem = image_path.stem
        ext = image_path.suffix
        timestamp = str(int(time.time()))
        name = f"{stem}_{timestamp[-6:]}{ext}"
    
    # Read and encode image
    with open(image_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
    
    # GitHub API path
    path = f"/repos/{repo}/contents/{directory}/{name}"
    
    # Check if file exists
    try:
        existing = gh_api("GET", path, token=token)
        sha = existing.get("sha")
    except:
        sha = None
    
    # Create or update file
    data = {
        "message": f"Upload {name} via PicX",
        "content": content,
        "branch": branch,
    }
    if sha:
        data["sha"] = sha
    
    result = gh_api("PUT", path, data=data, token=token)
    
    # Clean up temp files
    if compress or watermark:
        image_path.unlink(missing_ok=True)
    
    # Return the download URL
    owner, repo_name = get_repo_info(repo)
    url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{directory}/{name}"
    return url

def delete_image(image_path, repo=DEFAULT_REPO, branch=DEFAULT_BRANCH, token=None):
    """Delete an image from GitHub."""
    path = f"/repos/{repo}/contents/{image_path}"
    
    # Get file SHA
    try:
        existing = gh_api("GET", path, token=token)
        sha = existing.get("sha")
    except:
        print(f"Error: {image_path} not found", file=sys.stderr)
        sys.exit(1)
    
    data = {
        "message": f"Delete {Path(image_path).name} via PicX",
        "sha": sha,
        "branch": branch,
    }
    gh_api("DELETE", path, data=data, token=token)
    print(f"Deleted: {image_path}")

def list_images(repo=DEFAULT_REPO, branch=DEFAULT_BRANCH, directory=DEFAULT_DIR, token=None):
    """List images in a directory."""
    path = f"/repos/{repo}/contents/{directory}?ref={branch}"
    try:
        items = gh_api("GET", path, token=token)
    except:
        print(f"Error: Could not list {directory}", file=sys.stderr)
        sys.exit(1)
    
    images = []
    for item in items:
        if item["type"] == "file":
            ext = Path(item["name"]).suffix.lower()
            if ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"]:
                images.append(item["name"])
    
    return images

def generate_link(image_path, repo=DEFAULT_REPO, branch=DEFAULT_BRANCH, format="markdown", cdn="jsdelivr"):
    """Generate a CDN link."""
    owner, repo_name = get_repo_info(repo)
    template = CDN_TEMPLATES.get(cdn, CDN_TEMPLATES["jsdelivr"])
    url = template.format(owner=owner, repo=repo_name, branch=branch, path=image_path)
    
    name = Path(image_path).name
    if format == "markdown":
        return f"![{name}]({url})"
    elif format == "html":
        return f'<img src="{url}" alt="{name}">'
    elif format == "bbcode":
        return f"[img]{url}[/img]"
    return url

def compress_image(image_path, quality=85, output=None):
    """Compress an image locally."""
    image_path = Path(image_path)
    if output is None:
        output = image_path.with_suffix(".compressed" + image_path.suffix)
    run(f'magick "{image_path}" -quality {quality} -resize "1920x1920>" "{output}"')
    return output

def add_watermark(image_path, text, position="bottom-right", opacity=50, output=None):
    """Add watermark to an image locally."""
    image_path = Path(image_path)
    gravity = {"top-left": "NorthWest", "top-right": "NorthEast", 
               "bottom-left": "SouthWest", "bottom-right": "SouthEast"}.get(position, "SouthEast")
    if output is None:
        output = image_path.with_suffix(".watermarked" + image_path.suffix)
    run(f'magick "{image_path}" -gravity {gravity} -pointsize 30 -fill "rgba(255,255,255,{opacity/100})" -annotate +10+10 "{text}" "{output}"')
    return output

def main():
    parser = argparse.ArgumentParser(description="PicX-style image hosting")
    subparsers = parser.add_subparsers(dest="command")
    
    # Upload
    upload_parser = subparsers.add_parser("upload")
    upload_parser.add_argument("image")
    upload_parser.add_argument("--repo", default=DEFAULT_REPO)
    upload_parser.add_argument("--branch", default=DEFAULT_BRANCH)
    upload_parser.add_argument("--dir", default=DEFAULT_DIR)
    upload_parser.add_argument("--name", default=None)
    upload_parser.add_argument("--compress", action="store_true")
    upload_parser.add_argument("--watermark", default=None)
    
    # Delete
    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("path")
    delete_parser.add_argument("--repo", default=DEFAULT_REPO)
    delete_parser.add_argument("--branch", default=DEFAULT_BRANCH)
    
    # List
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--repo", default=DEFAULT_REPO)
    list_parser.add_argument("--branch", default=DEFAULT_BRANCH)
    list_parser.add_argument("--dir", default=DEFAULT_DIR)
    
    # Link
    link_parser = subparsers.add_parser("link")
    link_parser.add_argument("path")
    link_parser.add_argument("--repo", default=DEFAULT_REPO)
    link_parser.add_argument("--branch", default=DEFAULT_BRANCH)
    link_parser.add_argument("--format", default="markdown", choices=["markdown", "html", "bbcode", "url"])
    link_parser.add_argument("--cdn", default="jsdelivr", choices=["github", "github-pages", "jsdelivr", "statically"])
    
    # Batch
    batch_parser = subparsers.add_parser("batch")
    batch_parser.add_argument("images", nargs="+")
    batch_parser.add_argument("--repo", default=DEFAULT_REPO)
    batch_parser.add_argument("--branch", default=DEFAULT_BRANCH)
    batch_parser.add_argument("--dir", default=DEFAULT_DIR)
    batch_parser.add_argument("--compress", action="store_true")
    batch_parser.add_argument("--watermark", default=None)
    
    # Compress
    compress_parser = subparsers.add_parser("compress")
    compress_parser.add_argument("image")
    compress_parser.add_argument("--quality", type=int, default=85)
    compress_parser.add_argument("--output", default=None)
    
    # Watermark
    watermark_parser = subparsers.add_parser("watermark")
    watermark_parser.add_argument("image")
    watermark_parser.add_argument("text")
    watermark_parser.add_argument("--position", default="bottom-right")
    watermark_parser.add_argument("--opacity", type=int, default=50)
    watermark_parser.add_argument("--output", default=None)
    
    args = parser.parse_args()
    
    # Load token
    token = load_env()
    if not token:
        print("Error: IMGX_TOKEN not found in .env", file=sys.stderr)
        sys.exit(1)
    
    if args.command == "upload":
        url = upload_image(args.image, args.repo, args.branch, args.dir, args.name, args.compress, args.watermark, token=token)
        print(url)
    elif args.command == "delete":
        delete_image(args.path, args.repo, args.branch, token=token)
    elif args.command == "list":
        images = list_images(args.repo, args.branch, args.dir, token=token)
        for img in images:
            print(img)
    elif args.command == "link":
        print(generate_link(args.path, args.repo, args.branch, args.format, args.cdn))
    elif args.command == "batch":
        for img in args.images:
            url = upload_image(img, args.repo, args.branch, args.dir, compress=args.compress, watermark=args.watermark, token=token)
            print(url)
    elif args.command == "compress":
        output = compress_image(args.image, args.quality, args.output)
        print(output)
    elif args.command == "watermark":
        output = add_watermark(args.image, args.text, args.position, args.opacity, args.output)
        print(output)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
