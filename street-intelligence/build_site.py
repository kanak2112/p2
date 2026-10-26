"""
Build a deployable copy of the pedestrian map into site/.

  python build_site.py            # writes site/index.html, site/data/manifest.js and the 15 photo sheets

Upload the site/ folder to any static host (GitHub Pages, Netlify, Cloudflare Pages, S3). No server code.
"""
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "site")


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "data"))
    shutil.copy(os.path.join(HERE, "map.html"), os.path.join(OUT, "index.html"))
    shutil.copy(os.path.join(HERE, "data", "manifest.js"), os.path.join(OUT, "data", "manifest.js"))
    with open(os.path.join(HERE, "data", "manifest.json")) as f:
        manifest = json.load(f)
    n = 0
    for d in manifest["days"]:
        if d.get("mock"):
            continue
        for key in ("forward", "return"):
            w = d.get(key)
            if not w or not w.get("frame_sheet"):
                continue
            src = os.path.join(HERE, w["folder"], w["frame_sheet"]["file"])
            dst = os.path.join(OUT, w["folder"], w["frame_sheet"]["file"])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)
            n += 1
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(OUT) for f in fs)
    print(f"site/ ready: {n} photo sheets, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
