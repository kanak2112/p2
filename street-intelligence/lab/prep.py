"""Builds lab/data.js and lab/ph/*.jpg for the Street Lab artifact from data/manifest.json.

For every walk and every 10 m stretch it keeps the worst photo (highest obstruction): its score, the
estimated free width, the people count and the traced overlay. The worst photo per stretch for each
of the three walk groups (daylight A->B, daylight B->A, night B->A) is copied to lab/ph at 240 px wide.
"""
import ast, json, os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NB, OBS = 22, 1.4
def edges(path, fwd):
    """Building-side and kerb-side edge of the traced ground, averaged over the 0.70-0.85 band of the frame."""
    if len(path) < 6:
        return None
    h = len(path) // 2
    left, right = path[:h][::-1], path[h:]          # both now run top -> bottom
    def at(edge, y):
        ys = [q[1] for q in edge]; xs = [q[0] for q in edge]
        return float(np.interp(y, ys, xs))
    band = np.linspace(.70, .85, 6)
    l = float(np.mean([at(left, y) for y in band])); r = float(np.mean([at(right, y) for y in band]))
    return (round(l, 3), round(r, 3)) if fwd else (round(1 - r, 3), round(1 - l, 3))
P = lambda v: ast.literal_eval(v) if isinstance(v, str) else v

m = json.load(open(os.path.join(ROOT, "data", "manifest.json")))
walks, best = [], {}
for d in m["days"]:
    for key in ("forward", "return"):
        w = d.get(key)
        if not w:
            continue
        night = w.get("lighting") == "night"
        grp = ("n" if night else "d") + ("f" if key == "forward" else "r")
        rec = []
        for i in range(NB):
            ns = [n for n in w["nodes"] if min(NB - 1, int(n["meter"] // 10)) == i]
            if not ns:
                rec.append(None)
                continue
            n = max(ns, key=lambda n: n["obstruction"])
            ov = n.get("ov") or {}
            obs = ov.get("obs", [])
            pid = f"{d['day']}{key[0]}{i}"
            e = edges(ov.get("path", []), key == "forward") if not night and not ov.get("night") else None
            rec.append({"e": e, "o": round(n["obstruction"], 2), "g": (n.get("seg") or {}).get("gap_m"), "p": n.get("people", 0),
                        "k": obs[0][4] if obs else ("dark" if night else "none"), "ks": sorted({b[4] for b in obs}), "id": pid})
            if (grp, i) not in best or n["obstruction"] > best[(grp, i)][0]["obstruction"]:
                best[(grp, i)] = (n, w, pid, ov)
        walks.append({"day": int(d["day"]), "date": d["processed"], "dir": key, "night": night,
                      "dur": round(P(w["summary"])["duration_s"]), "s": rec,
                      "honks": [round(h["m"]) for h in P(w["honks"])], "swerves": [round(s["m"]) for s in P(w["swerves"])]})
photos = {}
for (grp, i), (n, w, pid, ov) in best.items():
    im = Image.open(os.path.join(ROOT, w["folder"], n["file"])).convert("RGB")
    im = im.resize((240, round(240 * im.height / im.width)))
    im.save(os.path.join(HERE, "ph", pid + ".jpg"), quality=70)
    photos.setdefault(grp, {})[i] = {"id": pid, "path": ov.get("path", []), "obs": ov.get("obs", []), "night": ov.get("night", False),
                                     "src": f"Day {w['folder'].split('day')[-1].split('_')[0]} · {n['file']}"}
# Existing components: what the daylight photos show in the same stretch on many walks.
day = [w for w in walks if not w["night"]]
seg = {}
for d in m["days"]:
    for key in ("forward", "return"):
        w = d.get(key)
        if w and w.get("lighting") != "night":
            for n in w["nodes"]:
                if n.get("seg"):
                    seg.setdefault(min(NB - 1, int(n["meter"] // 10)), []).append(n["seg"])
xs = {}
for (grp, i), (n, w, pid, ov) in best.items():
    pass
for d in m["days"]:
    for key in ("forward", "return"):
        w = d.get(key)
        if not w or w.get("lighting") == "night":
            continue
        for n in w["nodes"]:
            for b in (n.get("ov") or {}).get("obs", []):
                x = b[0] + b[2] / 2
                xs.setdefault((min(NB - 1, int(n["meter"] // 10)), b[4]), []).append(x if key == "forward" else 1 - x)
def share(i, k):
    rs = [w["s"][i] for w in day if w["s"][i]]
    return sum(k in r["ks"] for r in rs) / max(1, len(rs)), len(rs)
RULES = [("pole", .4, "Poles and signs"), ("plants", .4, "Greenery"), ("vehicle", .6, "Vehicles stopping or parked"), ("people", .9, "Crowding")]
existing = []
for k, th, name in RULES:
    run = []
    for i in range(NB + 1):
        s, n = share(i, k) if i < NB else (0, 0)
        veg = i < NB and k == "plants" and sum(x["vegetation"] for x in seg[i]) / len(seg[i]) >= .12
        if i < NB and (s >= th or veg):
            run.append((i, s, n))
        elif run:
            a, b = run[0][0], run[-1][0]
            x = [v for (j, _, _) in run for v in xs.get((j, k), [])]
            existing.append({"kind": k, "name": name, "from": a * 10, "to": b * 10 + 10, "share": round(sum(r[1] for r in run) / len(run), 2),
                             "walks": run[0][2], "x": round(sum(x) / len(x), 2) if x else .5})
            run = []
walled = [i for i in range(NB) if sum(x["fixed"] for x in seg[i]) / len(seg[i]) >= .1]
if walled:
    existing.append({"kind": "barrier", "name": "Underpass walls", "from": walled[0] * 10, "to": walled[-1] * 10 + 10, "share": None, "walks": None, "x": .1})
existing.append({"kind": "bins", "name": "Green bins", "from": 76, "to": 84, "share": None, "walks": None, "x": .85, "src": "walker's landmark"})
# Every object detected in the daylight photos, placed on the street where it touches the ground.
# Along the street: distance ahead of the camera from a flat-ground model (phone at chest height, 1.3 m; vertical
# field of view about 65 degrees; horizon at 0.31 of the frame height, the 5th-10th percentile of the far end of the
# traced path). Ahead means further along the route on A -> B walks and back along it on B -> A walks.
# Across the street: relative to the traced walkable path at the same image row: 0 = building-side edge,
# 1 = kerb-side edge, mirrored on B -> A walks because the buildings are then on the right of the frame.
# Boxes whose bottom edge is above 0.42 of the frame do not touch the ground near the walker (awnings, signs, far
# objects) and are left out.
CAM_H, FY, HORIZON, MIN_Y, MAX_D = 1.3, .785, .31, .42, 12.0
def ahead(y):
    return min(MAX_D, CAM_H * FY / max(.01, y - HORIZON))
def rel(path, b, fwd):
    h = len(path) // 2
    L, R = path[:h][::-1], path[h:]
    y = min(1, b[1] + b[3])
    l = float(np.interp(y, [q[1] for q in L], [q[0] for q in L])); r = float(np.interp(y, [q[1] for q in R], [q[0] for q in R]))
    u = (b[0] + b[2] / 2 - l) / max(.05, r - l)
    return u if fwd else 1 - u
dets = []
for di, d in enumerate(m["days"]):
    for key in ("forward", "return"):
        w = d.get(key)
        if not w or w.get("lighting") == "night":
            continue
        for n in w["nodes"]:
            ov = P(n.get("ov") or {})
            if ov.get("night") or len(ov.get("path", [])) < 6:
                continue
            for b in ov.get("obs", []):
                y = min(1, b[1] + b[3])
                if y < MIN_Y or (b[2] >= .95 and b[3] >= .95):
                    continue
                mm = float(n["meter"]) + (ahead(y) if key == "forward" else -ahead(y))
                dets.append([round(max(0, min(220, mm)), 1), round(max(-.6, min(1.6, rel(ov["path"], b, key == "forward"))), 2), b[4], key[0], di + 1])
for e in existing:
    if e["kind"] == "bins":
        e["u"] = [.85, .95, 1.05]
        continue
    us = sorted(u for mm, u, k, *_ in dets if (k == e["kind"] or (e["kind"] == "bins" and k in ("barrier", "pole"))) and e["from"] <= mm < e["to"])
    if us:
        q = lambda f: us[min(len(us) - 1, int(f * len(us)))]
        e["u"] = [round(q(.25), 2), round(q(.5), 2), round(q(.75), 2)]
    else:
        e["u"] = {"barrier": [-.3, -.15, 0], "bins": [.85, .95, 1.05]}.get(e["kind"], [.4, .5, .6])
# Night lighting, relative: median brightness of the walking surface (lower 45% of each night frame), divided by
# that walk's median over the whole route so phone exposure differences between walks cancel out; then the median
# across night walks for each 10 m segment. 1.0 = as bright as the route's typical night frame. Phones raise
# exposure in the dark, so this ranks segments against each other; it is not a lux reading.
lum = {}
for d in m["days"]:
    for key in ("forward", "return"):
        w = d.get(key)
        if not w or w.get("lighting") != "night":
            continue
        vals = {}
        for n in w["nodes"]:
            im = np.asarray(Image.open(os.path.join(ROOT, w["folder"], n["file"])).convert("L"), dtype=float)
            vals.setdefault(min(NB - 1, int(float(n["meter"]) // 10)), []).append(float(im[int(im.shape[0] * .55):].mean()))
        ref = float(np.median([v for vs in vals.values() for v in vs]))
        for i, vs in vals.items():
            lum.setdefault(i, []).append(float(np.median(vs)) / ref)
lit = [{"r": round(float(np.median(lum[i])), 2), "w": len(lum[i])} if i in lum else None for i in range(NB)]
out = {"corridor": m["corridor"], "walks": walks, "photos": photos, "existing": existing, "dets": dets, "lit": lit}
with open(os.path.join(HERE, "data.js"), "w") as f:
    f.write("window.LAB=" + json.dumps(out, separators=(",", ":")) + ";\n")
print(len(walks), "walks", sum(len(v) for v in photos.values()), "photos")
