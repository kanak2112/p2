"""
How lit the footpath is at night, along the route, from the night walk photos (all four night walks go B to A).

Per photo: the mean brightness of the upper two thirds of the frame, where street lamps, the underpass tube lights and
lit shopfronts are, divided by that walk's median so that differences in phone exposure between walks cancel out.
Each photo is placed 3 m before its metre, since the light it sees is ahead of the walker (towards A).

Along the route: photos are smoothed with a 3 m window every 2 m and divided by the route's median, so 1.0 is a
typical night stretch, above 1 brighter, below 1 darker. Relative, not lux, and not lamp positions.

    python lab/lights.py      ->  appends window.LAB.lightp to lab/data.js (and writes lab/lights.json)
"""
import json, os, re
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
m = json.load(open(os.path.join(ROOT, "data", "manifest.json")))
L, STEP, AHEAD = 220, 2, 3.0

rows = []
for d in m["days"]:
    for key in ("forward", "return"):
        w = d.get(key)
        if not w or w.get("lighting") != "night": continue
        vals = []
        for n in w["nodes"]:
            a = np.asarray(Image.open(os.path.join(ROOT, w["folder"], n["file"])).convert("L").resize((169, 300)), float)
            vals.append((float(n["meter"]) - (AHEAD if key == "return" else -AHEAD), float(a[:200].mean())))
        med = float(np.median([v for _, v in vals]))
        rows += [(mm, v / med) for mm, v in vals]

xs = np.arange(0, L + 1, STEP)
num = np.zeros(len(xs)); den = np.zeros(len(xs))
for mm, v in rows:
    wgt = np.exp(-.5 * ((xs - mm) / 3.0) ** 2); num += wgt * v; den += wgt
prof = num / np.maximum(den, 1e-6)
prof = prof / np.median(prof)
out = {"step": STEP, "v": [round(float(v), 3) for v in prof], "photos": len(rows)}
json.dump(out, open(os.path.join(HERE, "lights.json"), "w"))
dj = os.path.join(HERE, "data.js"); t = open(dj).read()
t = re.sub(r"\nwindow\.LAB\.light[sp]?=.*?;(?=\n|$)", "", t.rstrip("\n"), flags=re.S) + "\nwindow.LAB.lightp=" + json.dumps(out) + ";\n"
open(dj, "w").write(t)
print(len(rows), "night photos; darkest 10 m:", sorted(range(0, L, 10), key=lambda m0: prof[m0 // STEP:(m0 + 10) // STEP + 1].mean())[:4])
