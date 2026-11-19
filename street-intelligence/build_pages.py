"""Builds the public website in ../docs for GitHub Pages: the map, the atlas, the data page and the review form.

    python build_pages.py

Then in the repository settings: Pages > Deploy from a branch > this branch, folder /docs.
The site is fully static. Nothing here depends on the hosting platform used while developing.
"""
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "docs")
LAB = os.path.join(HERE, "lab")
PED = os.path.join(HERE, "pedmap")

HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style></head><body>\n')


def clean(html):
    html = re.sub(r'<meta name="claude:[^"]*"[^>]*>\s*', "", html)
    html = html.replace("window.claude", "window.__host")
    html = html.replace("../lab/", "")
    # site names: the map is the home page, the atlas moves to atlas.html
    html = html.replace('"index.html"', '"@@ATLAS@@"').replace("'index.html'", "'@@ATLAS@@'")
    html = html.replace('"map.html"', '"index.html"').replace("'map.html'", "'index.html'")
    html = html.replace("@@ATLAS@@", "atlas.html")
    assert "claude" not in html.lower(), "platform reference left in page"
    return html


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "review"))
    for src, dst in (("map.html", "index.html"), ("index.html", "atlas.html"), ("data.html", "data.html")):
        with open(os.path.join(PED, src), encoding="utf-8") as f:
            page = clean(f.read())
        with open(os.path.join(OUT, dst), "w", encoding="utf-8") as f:
            f.write(page)
    for name in ("data.js", "sat.jpg", "sat-nolabels.jpg", "sat-hi.jpg", "sat-hi-nolabels.jpg"):
        shutil.copy(os.path.join(LAB, name), OUT)
    shutil.copytree(os.path.join(LAB, "ph"), os.path.join(OUT, "ph"))
    # the review sidebar is part of the public map only; it opens with ?review=1
    with open(os.path.join(PED, "review-panel.html"), encoding="utf-8") as f:
        panel = f.read()
    with open(os.path.join(OUT, "index.html"), encoding="utf-8") as f:
        page = f.read()
    assert page.count("</body>") == 1
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page.replace("</body>", panel + "\n</body>"))
    with open(os.path.join(OUT, "review", "index.html"), "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8"><title>Pedestrian Map Review</title>'
                '<meta http-equiv="refresh" content="0; url=../?review=1"><a href="../?review=1">Open the review</a>\n')
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print("built", OUT)


if __name__ == "__main__":
    main()
