"""
Clutter grid for every spot view (the one-per-second frames in spots_*.jpg), written into
data/manifest.json/.js as walk["spot_views"]["o"], ["nf"] and ["c"].

  o   walking-zone clutter of that frame, 1.0 = typical frame for walks in the same direction and light
  nf  the same for the body zone just ahead (bottom band), used for the proxemic band
  c   bitmask of a GRID_COLS x GRID_ROWS grid over the walking zone; bit set = that cell is cluttered

The walking zone and edge measure match process_day1.py (Canny edges, rows 55-100 %, columns 20-80 %),
so "o" is on the same scale as the per-frame obstruction index. The viewer draws boxes around
cluttered cells and compares cells across days from the same direction: a cell cluttered on every
day is drawn solid red (persistent), otherwise dashed amber (transient). Cells are a coarse proxy for
where clutter sits in the frame, not detected objects.

Run after process_day1.py:  python clutter_cells.py
"""
import json
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ZONE = (0.55, 1.0, 0.2, 0.8)      # top, bottom, left, right (fractions of the frame)
NEAR = (0.82, 1.0, 0.25, 0.75)
GRID_COLS, GRID_ROWS = 4, 3
CELL_THRESH = 2.2                 # cell density / typical zone density at which a cell counts as cluttered


def density(edges, box):
    h, w = edges.shape
    t, b, l, r = box
    roi = edges[int(h * t):int(h * b), int(w * l):int(w * r)]
    return float(roi.mean()) if roi.size else 0.0


def frames_of(walk):
    sv = walk.get("spot_views") or {}
    fw, fh = sv.get("size") or (0, 0)
    out = []
    for s, name in enumerate(sv.get("sheets", [])):
        sheet = cv2.imread(os.path.join(HERE, walk["folder"], name), cv2.IMREAD_GRAYSCALE)
        for k in range(min(sv["per_sheet"], len(sv["m"]) - s * sv["per_sheet"])):
            r, c = divmod(k, sv["cols"])
            out.append(sheet[r * fh:(r + 1) * fh, c * fw:(c + 1) * fw])
    return out


def main():
    with open(os.path.join(DATA, "manifest.json")) as f:
        manifest = json.load(f)
    raw = {}
    for d in manifest["days"]:
        if d.get("mock"):
            continue
        for key in ("forward", "return"):
            w = d.get(key)
            if not w or not w.get("spot_views"):
                continue
            rows = []
            for g in frames_of(w):
                e = (cv2.Canny(g, 60, 160) > 0).astype(np.float32)
                t, b, l, r = ZONE
                cells = []
                for gr in range(GRID_ROWS):
                    for gc in range(GRID_COLS):
                        cells.append(density(e, (t + (b - t) * gr / GRID_ROWS, t + (b - t) * (gr + 1) / GRID_ROWS,
                                                 l + (r - l) * gc / GRID_COLS, l + (r - l) * (gc + 1) / GRID_COLS)))
                rows.append((density(e, ZONE), density(e, NEAR), cells))
            raw[id(w)] = (w, key, w.get("lighting"), rows)

    groups = {}
    for w, key, light, rows in raw.values():
        groups.setdefault((key, light), []).append((w, rows))
    for (key, light), items in groups.items():
        zmed = max(float(np.median([r[0] for _, rows in items for r in rows])), 0.01)
        nmed = max(float(np.median([r[1] for _, rows in items for r in rows])), 0.01)
        for w, rows in items:
            sv = w["spot_views"]
            sv["o"] = [round(min(r[0] / zmed, 5.0), 2) for r in rows]
            sv["nf"] = [round(min(r[1] / nmed, 5.0), 2) for r in rows]
            sv["c"] = [sum(1 << i for i, v in enumerate(r[2]) if v / zmed >= CELL_THRESH) for r in rows]
            sv["grid"] = {"cols": GRID_COLS, "rows": GRID_ROWS, "zone": list(ZONE)}
        print(f"{key} / {light}: {len(items)} walk(s), {sum(len(r) for _, r in items)} frames")

    # Placeholder days share dicts with real days only in memory; copy the new fields across by folder.
    by_folder = {w["folder"]: w["spot_views"] for w, *_ in raw.values()}
    for d in manifest["days"]:
        if d.get("mock"):
            for key in ("forward", "return"):
                w = d.get(key)
                if w and w.get("folder") in by_folder:
                    w["spot_views"] = by_folder[w["folder"]]

    with open(os.path.join(DATA, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(DATA, "manifest.js"), "w") as f:
        f.write("window.STREET_DATA = ")
        json.dump(manifest, f)
        f.write(";\n")


if __name__ == "__main__":
    main()
