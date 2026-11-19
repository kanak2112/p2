"""How many walks are enough? Resamples the daytime walks and measures how far each stretch's findings move
from what all walks say.

For n walks drawn at random (2000 draws per n), per 10 m stretch:
  width   median clear width of the sampled walks vs the median of all walks (stretches with widths)
  blocked share of sampled walks blocked (obstruction >= 1.4) vs all walks; and whether the stretch is
          'blocked on most walks' (> half) in both
  worst   whether 80-90 m (the green bins) is among the three most-blocked stretches
Writes lab/convergence.json and prints a table.
"""
import json, os, random, re, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "data.js"), encoding="utf-8").read()
m = re.search(r"window\.LAB\s*=\s*(\{.*?\});\s*(?:window\.|$)", src, re.S)
LAB = json.loads(m.group(1))
OBS = 1.4
walks = [w for w in LAB["walks"] if not w["night"] and not w.get("part")]
NB = len(walks[0]["s"])
stretches = range(NB)


def find(ws):
    width, share = {}, {}
    for i in stretches:
        recs = [w["s"][i] for w in ws if w["s"][i]]
        if not recs:
            continue
        g = [r["g"] for r in recs if r.get("g") not in (None, 0)]
        if g:
            width[i] = st.median(g)
        share[i] = sum(r["o"] >= OBS for r in recs) / len(recs)
    return width, share


W, B = find(walks)
most = {i for i, v in B.items() if v > .5}
rng = random.Random(7)
rows = []
for n in (1, 3, 5, 8, 12, 16, len(walks)):
    werr, within, berr, agree, worst = [], [], [], [], []
    for _ in range(2000 if n < len(walks) else 1):
        ws = rng.sample(walks, n)
        w, b = find(ws)
        e = [abs(w[i] - W[i]) for i in w if i in W]
        werr.append(st.mean(e)); within.append(sum(x <= .2 for x in e) / len(e))
        berr.append(st.mean(abs(b[i] - B[i]) for i in b if i in B))
        agree.append(sum((b.get(i, 0) > .5) == (i in most) for i in B) / len(B))
        top3 = sorted(b, key=lambda i: -b[i])[:3]
        worst.append(8 in top3)
    rows.append({"n": n, "width_err_m": round(st.mean(werr), 2), "width_within_0_2m": round(st.mean(within), 2),
                 "blocked_share_err": round(st.mean(berr), 2), "most_walks_agree": round(st.mean(agree), 2),
                 "bins_in_top3": round(st.mean(worst), 2)})
out = {"daytime_walks": len(walks), "stretches": len(B), "rows": rows}
json.dump(out, open(os.path.join(HERE, "convergence.json"), "w"), indent=1)
print(f"{len(walks)} daytime walks, {len(B)} stretches")
print("n   width err  within 0.2m  blocked err  'most' agrees  bins top-3")
for r in rows:
    print(f"{r['n']:<3} {r['width_err_m']:>6.2f} m   {r['width_within_0_2m']:>6.0%}      {r['blocked_share_err']:>6.2f}       {r['most_walks_agree']:>6.0%}       {r['bins_in_top3']:>6.0%}")
