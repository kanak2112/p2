"""Builds lab/data.js and lab/ph/*.jpg for the Street Lab artifact from data/manifest.json.

For every walk and every 10 m stretch it keeps the worst photo (highest obstruction): its score, the
estimated free width, the people count and the traced overlay. The worst photo per stretch for each
of the three walk groups (daylight A->B, daylight B->A, night B->A) is copied to lab/ph at 240 px wide.
"""
import ast, json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NB, OBS = 22, 1.4
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
            rec.append({"o": round(n["obstruction"], 2), "g": (n.get("seg") or {}).get("gap_m"), "p": n.get("people", 0),
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
out = {"corridor": m["corridor"], "walks": walks, "photos": photos}
with open(os.path.join(HERE, "data.js"), "w") as f:
    f.write("window.LAB=" + json.dumps(out, separators=(",", ":")) + ";\n")
print(len(walks), "walks", sum(len(v) for v in photos.values()), "photos")
