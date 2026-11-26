#!/usr/bin/env python3
"""Build a tvkit home-screen mockup from the template and a JSON config.

Usage:
  build.py --config CONFIG.json [--before SCREENSHOT.png] [--wallpaper-photo PHOTO.jpg]
           [--out DIR] [--name tv-redesign] [--renders] [--no-wallpaper]

Writes into DIR (default: ~/.tvkit/redesign/<timestamp>/):
  <name>.html            standalone page, open it in a browser
  <name>.artifact.html   the same page without the html/head/body skeleton, for the Artifact tool
  <name>-wallpaper.png   1920x1080 wallpaper (needs Chrome, Chromium, Edge or Brave)
  <name>-<layout>.png    1920x1080 renders of each layout, with --renders (for posts and READMEs)
  config.json            the config that was embedded (images replaced by their source paths)

Standard library only. Set TVKIT_CHROME to a browser binary to override detection.
"""
import argparse
import base64
import copy
import datetime as dt
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "templates" / "tv-home.html"
PRESETS = ("ribbon", "shelf", "minimal")
CONFIG_RE = re.compile(r'(<script type="application/json" id="tv-config">)(.*?)(</script>)', re.S)
LOCAL_ONLY_RE = re.compile(r"<!-- local-only -->.*?<!-- /local-only -->", re.S)  # download link: inert inside artifacts
TITLE_RE = re.compile(r"<title>.*?</title>", re.S)
MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_PAGE_BYTES = 15 * 1024 * 1024
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def die(msg):
    sys.exit(f"error: {msg}")


def find_browser():
    candidates = [
        os.environ.get("TVKIT_CHROME"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "microsoft-edge", "brave-browser", "chrome", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    return None


def image_data_uri(path, max_side=1600):
    """Return a data: URI for an image, shrunk to JPEG when a converter is available."""
    src = pathlib.Path(path).expanduser()
    if not src.is_file():
        die(f"image not found: {src}")
    data, mime = None, MIME.get(src.suffix.lower(), "image/png")
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "img.jpg"
        cmd = None
        if shutil.which("sips"):  # macOS
            cmd = ["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "-Z", str(max_side), str(src), "--out", str(out)]
        elif shutil.which("magick"):
            cmd = ["magick", str(src), "-resize", f"{max_side}x{max_side}>", "-quality", "82", str(out)]
        elif shutil.which("convert"):
            cmd = ["convert", str(src), "-resize", f"{max_side}x{max_side}>", "-quality", "82", str(out)]
        if cmd:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0 and out.is_file() and out.stat().st_size > 0:
                data, mime = out.read_bytes(), "image/jpeg"
    if data is None:
        data = src.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        die(f"{src} is {len(data) // 1024} KB even after conversion; use a smaller image")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def load_config(path):
    p = pathlib.Path(path).expanduser()
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        die(f"cannot read config {p}: {e}")
    if not isinstance(cfg, dict):
        die("config must be a JSON object")
    if not any(isinstance(cfg.get(k), list) and cfg.get(k) for k in ("favorites", "apps", "inputs")):
        die("config needs at least one non-empty list: favorites, apps or inputs")
    if cfg.get("preset") not in PRESETS:
        if "preset" in cfg:
            print(f"note: unknown preset {cfg.get('preset')!r}, using 'ribbon'", file=sys.stderr)
        cfg["preset"] = "ribbon"
    if not cfg.get("generated"):
        today = dt.date.today()
        cfg["generated"] = f"{today.day} {today:%b %Y}"
    return cfg


def embed(template, cfg):
    blob = json.dumps(cfg, ensure_ascii=False, indent=2)
    blob = blob.replace("</", "<\\/").replace("<!--", "<\\u0021--")
    if not CONFIG_RE.search(template):
        die(f"template has no tv-config block: {TEMPLATE}")
    page = CONFIG_RE.sub(lambda m: m.group(1) + "\n" + blob + "\n" + m.group(3), template, count=1)
    title = html.escape(str(cfg.get("title") or "TV Home"))
    return TITLE_RE.sub(lambda m: f"<title>{title}</title>", page, count=1)


def standalone(page):
    """Wrap the artifact-ready page in a full HTML document for local viewing."""
    cut = page.find("</style>")
    head, body = (page[:cut + 8], page[cut + 8:]) if cut >= 0 else ("", page)
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            + head + "\n</head>\n<body>\n" + body.lstrip("\n") + "\n</body>\n</html>\n")


def screenshot(browser, page_path, fragment, out_png):
    url = page_path.resolve().as_uri() + "#" + fragment
    with tempfile.TemporaryDirectory() as profile:
        cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
               "--no-default-browser-check", "--force-device-scale-factor=1", f"--user-data-dir={profile}",
               "--window-size=1920,1080", "--virtual-time-budget=2500", f"--screenshot={out_png}", url]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            print(f"note: screenshot of #{fragment} failed: {e}", file=sys.stderr)
            return False
    return out_png.is_file() and out_png.stat().st_size > 0


def main():
    ap = argparse.ArgumentParser(description="Build a tvkit home-screen mockup from a JSON config.")
    ap.add_argument("--config", required=True, help="JSON config (see the redesign SKILL.md for the schema)")
    ap.add_argument("--before", help="screenshot of the current home screen to embed as the 'Before' view")
    ap.add_argument("--wallpaper-photo", help="photo to use as the wallpaper instead of a generated one")
    ap.add_argument("--out", help="output folder (default: ~/.tvkit/redesign/<timestamp>)")
    ap.add_argument("--name", default="tv-redesign", help="base file name (default: tv-redesign)")
    ap.add_argument("--renders", action="store_true", help="also save 1920x1080 PNGs of each layout")
    ap.add_argument("--no-wallpaper", action="store_true", help="skip the wallpaper PNG export")
    a = ap.parse_args()

    if not TEMPLATE.is_file():
        die(f"template missing: {TEMPLATE}")
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", a.name).strip("-.") or "tv-redesign"
    out = pathlib.Path(a.out).expanduser() if a.out else (
        pathlib.Path.home() / ".tvkit" / "redesign" / dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)

    cfg = load_config(a.config)
    record = copy.deepcopy(cfg)
    if a.before:
        before = cfg.get("before") if isinstance(cfg.get("before"), dict) else {}
        before["image"] = image_data_uri(a.before)
        before.setdefault("caption", f"Current home screen, captured {cfg['generated']}")
        cfg["before"] = before
        record.setdefault("before", {})["image"] = str(pathlib.Path(a.before).expanduser())
    if a.wallpaper_photo:
        wp = cfg.get("wallpaper") if isinstance(cfg.get("wallpaper"), dict) else {}
        wp["image"], wp["mood"] = image_data_uri(a.wallpaper_photo, max_side=1920), "photo"
        cfg["wallpaper"] = wp
        record.setdefault("wallpaper", {})["image"] = str(pathlib.Path(a.wallpaper_photo).expanduser())
    # Optional per-app "logo": an image path, typically a banner cropped from the TV's own Apps screen.
    # It is embedded as a small data URI, so the page stays self-contained.
    for key in ("favorites", "apps", "inputs"):
        for item in cfg.get(key) or []:
            logo = item.get("logo") if isinstance(item, dict) else None
            if isinstance(logo, str) and logo and not logo.startswith("data:"):
                item["logo"] = image_data_uri(logo, max_side=480)

    page = embed(TEMPLATE.read_text(encoding="utf-8"), cfg)
    artifact_path = out / f"{name}.artifact.html"
    page_path = out / f"{name}.html"
    artifact_path.write_text(LOCAL_ONLY_RE.sub("", page), encoding="utf-8")
    page_path.write_text(standalone(page), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    made = [("page (open locally)", page_path), ("artifact-ready page", artifact_path)]
    size = artifact_path.stat().st_size
    if size > MAX_PAGE_BYTES:
        print(f"warning: the page is {size // (1024 * 1024)} MB; artifacts must be under 16 MB. Use a smaller --before image.", file=sys.stderr)

    want = [] if a.no_wallpaper else [("wallpaper", f"{name}-wallpaper.png")]
    if a.renders:
        want += [(f"screen-{p}", f"{name}-{p}.png") for p in PRESETS]
        if a.before:
            want.append(("screen-before", f"{name}-before.png"))
    if want:
        browser = find_browser()
        if not browser:
            print("note: no Chrome, Chromium, Edge or Brave found, so no PNGs were exported. "
                  "Open the page and use 'Export wallpaper PNG' instead.", file=sys.stderr)
        else:
            for frag, fname in want:
                png = out / fname
                if screenshot(browser, page_path, frag, png):
                    made.append(("wallpaper" if frag == "wallpaper" else f"render #{frag}", png))
                else:
                    print(f"note: could not export #{frag}", file=sys.stderr)

    for label, path in made:
        print(f"{label:22} {path}")
    print(f"{'artifact size':22} {size // 1024} KB")


if __name__ == "__main__":
    main()
