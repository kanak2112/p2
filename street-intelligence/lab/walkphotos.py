"""Exports one photo per walk per 10 m stretch, for the map's photos-by-walk strip and timeline.

For every walk and stretch it takes the same photo as lab/data.js (the most obstructed one), writes it to
lab/wph/<id>.jpg at 200 px wide, and writes lab/wph.js with the traced walkable ground and the detected
obstacle boxes of each photo:  window.WPH = { "<id>": { p: [[x, y], ...], o: [[x, y, w, h, kind], ...] } }
Coordinates are fractions of the frame. Night photos have no traced ground.

    python lab/walkphotos.py
"""
import json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "wph")
NB = 22
r3 = lambda v: round(float(v), 3)

m = json.load(open(os.path.join(ROOT, "data", "manifest.json")))
os.makedirs(OUT, exist_ok=True)
meta = {}
for d in m["days"]:
    for key in ("forward", "return"):
        w = d.get(key)
        if not w:
            continue
        night = w.get("lighting") == "night"
        for i in range(NB):
            ns = [n for n in w["nodes"] if min(NB - 1, int(n["meter"] // 10)) == i]
            if not ns:
                continue
            n = max(ns, key=lambda n: n["obstruction"])
            ov = n.get("ov") or {}
            pid = f"{d['day']}{key[0]}{i}"
            dst = os.path.join(OUT, pid + ".jpg")
            if not os.path.exists(dst):
                im = Image.open(os.path.join(ROOT, w["folder"], n["file"])).convert("RGB")
                im.resize((200, round(200 * im.height / im.width))).save(dst, quality=62)
            path = [] if night or ov.get("night") else [[r3(x), r3(y)] for x, y in ov.get("path", [])]
            obs = [[r3(b[0]), r3(b[1]), r3(b[2]), r3(b[3]), b[4]] for b in ov.get("obs", [])]
            meta[pid] = {"p": path, "o": obs}
with open(os.path.join(HERE, "wph.js"), "w") as f:
    f.write("window.WPH=" + json.dumps(meta, separators=(",", ":")) + ";\n")
print(len(meta), "photos")
