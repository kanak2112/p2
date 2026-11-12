"""
Where the light is at night, from the night walk photos (all four night walks go B to A).

Per photo: bright blobs (every channel above 240 on a half-size image) above the walking surface are light
sources: street lamps, tube lights in the underpass, lit shop signs and fronts. A blob counts as one the walker
is about to pass when it is large, or close to the top or the sides of the frame. Its strength is its area.
Each photo is placed at its metre along the route (the photo point, already shifted 4 m ahead).

Across walks: near-light strength is smoothed along the route (2 m) and divided by how densely the walks were
photographed there, so the result does not simply follow the photo spacing. Local peaks above a floor are the
places where a walker passes a light. Positions are good to a few metres; this is not a lamp survey and not lux.

    python lab/lights.py      ->  appends window.LAB.lights to lab/data.js (and writes lab/lights.json)
"""
import json, os, re, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
m = json.load(open(os.path.join(ROOT, "data", "manifest.json")))
L = 220.0

def blobs(mask):
    H, W = mask.shape; lab = np.zeros((H, W), np.int32); out = []; k = 0
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if lab[y0, x0]: continue
        k += 1; st = [(y0, x0)]; lab[y0, x0] = k; pts = []
        while st:
            y, x = st.pop(); pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = k; st.append((yy, xx))
        p = np.array(pts); out.append((len(p), p[:, 0].mean() / H, p[:, 1].mean() / W))
    return out

pts = []   # (metre, near-light strength, walk)
cover = [] # (metre, walk)
for d in m["days"]:
    for key in ("forward", "return"):
        w = d.get(key)
        if not w or w.get("lighting") != "night": continue
        for n in w["nodes"]:
            im = Image.open(os.path.join(ROOT, w["folder"], n["file"])).convert("RGB")
            im = im.resize((im.width // 2, im.height // 2)); a = np.asarray(im)
            mask = (a.min(axis=2) > 240); mask[int(.72 * mask.shape[0]):] = False   # above the walking surface
            near = 0.0
            for area, cy, cx in blobs(mask):
                if area < 4: continue
                if area >= 60 or cy < .3 or cx < .14 or cx > .86: near += min(area, 400)
            pts.append((float(n["meter"]), near, d["day"])); cover.append((float(n["meter"]), d["day"]))

xs = np.arange(0, L + .5, .5)
def smooth(vals):
    acc = np.zeros_like(xs)
    for mm, v in vals: acc += v * np.exp(-.5 * ((xs - mm) / 2.0) ** 2)
    return acc
num = smooth([(p[0], p[1]) for p in pts]); den = smooth([(c[0], 1.0) for c in cover])
s = np.where(den > .25, num / np.maximum(den, 1e-6), 0)
floor = max(40.0, float(np.percentile(s[s > 0], 40))) if (s > 0).any() else 40.0
peaks = []
for i in range(1, len(xs) - 1):
    if s[i] >= floor and s[i] >= s[i - 1] and s[i] > s[i + 1] and all(abs(xs[i] - q[0]) >= 5 for q in peaks):
        peaks.append((float(xs[i]), float(s[i])))
mx = max([p[1] for p in peaks] or [1])
lights = [{"m": round(p[0], 1), "s": round(p[1] / mx, 2)} for p in peaks]
json.dump(lights, open(os.path.join(HERE, "lights.json"), "w"))
dj = os.path.join(HERE, "data.js"); t = open(dj).read()
t = re.sub(r"\nwindow\.LAB\.lights=.*$", "", t.rstrip("\n"), flags=re.S) + "\nwindow.LAB.lights=" + json.dumps(lights) + ";\n"
open(dj, "w").write(t)
print(len(pts), "night photos,", len(lights), "lights:", [l["m"] for l in lights])
