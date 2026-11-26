#!/usr/bin/env python3
"""Crop app banners out of a TV screenshot, using the matching `tvkit ui-dump` XML for exact positions.

Run it on a screenshot of the TV's Apps screen, so the user's own installed banners become
`logo` images in the mockup. They stay on this computer; never commit them to a repository.

usage: crop_tiles.py SCREENSHOT.png UI.xml OUTDIR "App label=file-name" ...
  e.g. crop_tiles.py apps.png ui.xml ~/.tvkit/redesign/x/logos "Netflix=netflix" "YouTube=youtube"

Labels are the tiles' content descriptions as `tvkit ui-dump` prints them. Uses sips (macOS) or
ImageMagick (Linux and Windows). Stdlib only.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


def crop_cmd(src, out, x, y, w, h):
    if shutil.which("sips"):
        return ["sips", "--cropToHeightWidth", str(h), str(w), "--cropOffset", str(y), str(x), src, "--out", out]
    tool = shutil.which("magick") or shutil.which("convert")
    if tool:
        return [tool, src, "-crop", f"{w}x{h}+{x}+{y}", "+repage", out]
    sys.exit("crop_tiles: needs sips (macOS) or ImageMagick (magick/convert)")


def main():
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    png, xml_path, outdir = sys.argv[1:4]
    wanted = dict(arg.split("=", 1) for arg in sys.argv[4:])
    pathlib.Path(outdir).expanduser().mkdir(parents=True, exist_ok=True)
    found = set()
    for node in ET.parse(xml_path).getroot().iter("node"):
        desc = node.get("content-desc", "")
        if desc not in wanted or desc in found:
            continue
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds", "")))
        name = re.sub(r"[^A-Za-z0-9_-]+", "-", wanted[desc]).strip("-") or "logo"
        out = str(pathlib.Path(outdir).expanduser() / f"{name}.png")
        r = subprocess.run(crop_cmd(png, out, x1, y1, x2 - x1, y2 - y1), capture_output=True, text=True)
        found.add(desc)
        print(f"{'ok' if r.returncode == 0 else 'FAILED':6} {desc:16} {x2 - x1}x{y2 - y1}  {out}")
    for desc in sorted(set(wanted) - found):
        print(f"missing {desc} (not on this screen; focus its row and capture again)")


if __name__ == "__main__":
    main()
