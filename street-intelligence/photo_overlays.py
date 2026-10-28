"""
Photo overlays traced from each photo, written into data/manifest.json/.js as node["ov"]:

  path   the walkable ground ahead, as a polygon [[x, y], ...] in fractions of the frame (0-1)
  obs    obstacles on or beside that path, [[x, y, w, h, kind], ...] in fractions of the frame;
         kind is "people", "vehicle", "pole", "barrier" or "plants"
  night  true for a low-light photo (night walks, the underpass): segmentation labels a dark floor as
         anything, so the path comes from texture and colour instead (ground_by_look), the viewer draws
         it dashed, and no obstacle boxes are given

Both come from semantic segmentation (DeepLab v3, Cityscapes; the same model segment_frames.py uses).

  Ground   road + sidewalk + terrain. The model calls Mumbai's unkerbed footpaths "road", so ground is
           treated as one class.
  Path     traced from the bottom of the frame upwards: on each pixel row, the run of ground that
           continues the run below it (most overlap). The trace stops where the run disappears or
           narrows to a sliver, so the polygon follows the free ground the walker actually had,
           around parked bikes, people and kerbs, instead of a fixed trapezoid.
  Obstacles  connected regions of people, vehicles, poles/signs, fences/walls and vegetation that
           sit below the path's far end and touch the path or the band 8 % of the frame width
           either side of it. Crowds are split at the gaps between people. The five largest are kept.

By default only the photos the viewer shows are processed: for each walk and each 10 m stretch, the
photo with the highest obstruction. --all does every kept photo. Segmentation is cached as PNG label
maps in --cache, so changing the geometry rules re-runs in seconds:

  python photo_overlays.py --model path/to/frozen_inference_graph.pb --cache seg_cache
"""
import argparse
import json
import os

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
STRETCH_M = 10
GROUND = [0, 1, 9]
KINDS = {"people": [11, 12], "vehicle": [13, 14, 15, 16, 17, 18], "pole": [5, 6, 7],
         "barrier": [3, 4], "plants": [8]}
MIN_RUN = 0.06          # a path row narrower than this (fraction of width) ends the trace
MIN_OBS = 0.004         # obstacle area, fraction of the frame
SIDE = 0.08             # band either side of the path where obstacles still count
SAMPLES = 14            # polygon vertices per side
DARK = 70               # mean grey level below which a photo counts as dark (night, underpass)


def ground_by_look(im):
    """For dark photos, where segmentation labels the floor as anything (vegetation, truck): the floor is
    the low-texture area with the colour of the patch just ahead of the walker's feet. Brick walls and
    railings are textured, so they drop out."""
    H, W = im.shape[:2]
    lab = cv2.cvtColor(im, cv2.COLOR_RGB2LAB)
    lab[..., 0] = cv2.createCLAHE(3.0, (8, 8)).apply(lab[..., 0])
    L = lab[..., 0]
    tex = cv2.blur(np.abs(cv2.Sobel(L, cv2.CV_32F, 1, 0, ksize=3)) + np.abs(cv2.Sobel(L, cv2.CV_32F, 0, 1, ksize=3)), (15, 15))
    feet = (slice(int(H * 0.88), H), slice(W // 3, 2 * W // 3))
    smooth = tex < np.percentile(tex[feet], 70) * 1.6
    b = cv2.GaussianBlur(lab, (9, 9), 0).astype(np.int16)
    ref = np.median(b[feet].reshape(-1, 3), 0)
    col = (np.abs(b[..., 0] - ref[0]) < 40) & (np.abs(b[..., 1] - ref[1]) < 10) & (np.abs(b[..., 2] - ref[2]) < 10)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    return cv2.morphologyEx((smooth & col).astype(np.uint8), cv2.MORPH_CLOSE, k) > 0


def load_model(path):
    import tensorflow as tf
    g = tf.Graph()
    with g.as_default():
        gd = tf.compat.v1.GraphDef()
        with open(path, "rb") as f:
            gd.ParseFromString(f.read())
        tf.import_graph_def(gd, name="")
    sess = tf.compat.v1.Session(graph=g)
    return lambda im: sess.run("SemanticPredictions:0", {"ImageTensor:0": im[None]})[0].astype(np.uint8)


def shown_nodes(walk):
    worst = {}
    for n in walk["nodes"]:
        b = int(n["meter"] // STRETCH_M)
        if b not in worst or n["obstruction"] > worst[b]["obstruction"]:
            worst[b] = n
    return list(worst.values())


def runs(row):
    d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0] - 1))


def trace_path(ground):
    H, W = ground.shape
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    g = cv2.morphologyEx(ground.astype(np.uint8), cv2.MORPH_OPEN, k)
    g = cv2.morphologyEx(g, cv2.MORPH_CLOSE, k).astype(bool)
    minw = MIN_RUN * W
    start, prev = None, None
    for y in range(H - 1, int(H * 0.6), -1):          # first usable row in the bottom 40 %
        cand = [r for r in runs(g[y]) if r[1] - r[0] >= minw]
        if cand:
            prev = min(cand, key=lambda r: abs((r[0] + r[1]) / 2 - W / 2) - (r[1] - r[0]) * 0.25)
            start = y
            break
    if start is None:
        return None
    rows = {start: prev}
    for y in range(start - 1, -1, -1):
        best, ov = None, 0
        for a, b in runs(g[y]):
            o = min(b, prev[1]) - max(a, prev[0])
            if o > ov:
                best, ov = (a, b), o
        if best is None or best[1] - best[0] < max(4, minw * 0.35):
            break
        rows[y] = prev = best
    ys = sorted(rows)
    if len(ys) < H * 0.08:
        return None
    left = np.array([rows[y][0] for y in ys], float)
    right = np.array([rows[y][1] for y in ys], float)
    k = max(3, len(ys) // 25) | 1                      # smooth ragged mask edges
    pad = k // 2
    left = np.array([np.median(left[max(0, i - pad):i + pad + 1]) for i in range(len(ys))])
    right = np.array([np.median(right[max(0, i - pad):i + pad + 1]) for i in range(len(ys))])
    idx = np.linspace(0, len(ys) - 1, SAMPLES).round().astype(int)
    top, bottom = ys[0], ys[-1]
    bottom = H - 1 if bottom >= H - 4 else bottom
    L = [(left[i] / W, ys[i] / H) for i in idx]
    R = [(right[i] / W, ys[i] / H) for i in idx]
    poly = L[::-1] + R                                  # bottom-left, up the left edge, down the right
    poly = [(x, 1.0 if y * H >= H - 4 else y) for x, y in poly]
    return {"poly": [[round(x, 3), round(y, 3)] for x, y in poly], "rows": rows, "top": top}


def split_columns(mask, x0, W):
    """A crowd or a row of parked bikes segments as one region: split it at the dips in its column profile
    (the gaps between people), where a column holds well under the pixels of the columns either side."""
    w = mask.shape[1]
    if w < 0.15 * W:
        return [(0, w)]
    prof = np.convolve(mask.sum(0).astype(float), np.ones(5) / 5, "same")
    reach, cuts = max(4, int(0.05 * W)), [0]
    for c in range(reach, w - reach):
        lo = prof[c]
        if lo == prof[c - reach:c + reach + 1].min() and c - cuts[-1] >= 0.06 * W:
            if lo < 0.6 * min(prof[:c].max(), prof[c + 1:].max()):
                cuts.append(c)
    cuts.append(w)
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if b - a >= 0.02 * W]


def pieces(seg, cls, W, people=False):
    m = np.isin(seg, cls).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    for i in range(1, n):
        x, y, w, h, area = st[i]
        sub = lab[y:y + h, x:x + w] == i
        for a, b in split_columns(sub, x, W):
            part = sub[:, a:b]
            rows = np.where(part.any(1))[0]
            if len(rows):
                yield x + a, y + rows[0], b - a, rows[-1] - rows[0] + 1, int(part.sum())


def obstacles(seg, path):
    H, W = seg.shape
    out = []
    top = path["top"] if path else int(H * 0.45)
    rows = path["rows"] if path else {}
    for kind, cls in KINDS.items():
        for x, y, w, h, area in pieces(seg, cls, W, kind == "people"):
            if area < MIN_OBS * H * W or y + h < top:
                continue
            ys = [yy for yy in range(max(y, top), y + h) if yy in rows]
            if rows and ys:
                near = any(x <= rows[yy][1] + SIDE * W and x + w >= rows[yy][0] - SIDE * W for yy in ys[::4])
            else:
                near = x < 0.85 * W and x + w > 0.15 * W
            if near:
                out.append((area, [round(x / W, 3), round(y / H, 3), round(w / W, 3), round(h / H, 3), kind]))
    return [b for _, b in sorted(out, key=lambda t: -t[0])[:5]]


def is_dark(im, night):
    grey = cv2.cvtColor(im, cv2.COLOR_RGB2GRAY)
    return bool(night or grey[grey.shape[0] // 2:].mean() < DARK)   # the ground half: underpasses count too


def trace(im, seg, dark):
    p = trace_path(ground_by_look(im) if dark else np.isin(seg, GROUND))
    return {"path": p["poly"] if p else [], "obs": [] if dark else obstacles(seg, p), "night": dark}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="DeepLab v3 Cityscapes frozen_inference_graph.pb (needed for photos not yet cached)")
    ap.add_argument("--cache", default=os.path.join(HERE, "seg_cache"))
    ap.add_argument("--all", action="store_true", help="every kept photo, not just the ones the viewer shows")
    ap.add_argument("--segment-only", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.cache, exist_ok=True)
    path = os.path.join(DATA, "manifest.json")
    with open(path) as f:
        manifest = json.load(f)
    seen, work = set(), []
    for d in manifest["days"]:
        for key in ("forward", "return"):
            w = d.get(key)
            if not w or w["folder"] in seen:
                continue
            seen.add(w["folder"])
            for n in (w["nodes"] if args.all else shown_nodes(w)):
                work.append((w, n))
    model = None
    for k, (w, n) in enumerate(work):
        im = np.asarray(Image.open(os.path.join(HERE, w["folder"], n["file"])).convert("RGB"))
        dark = is_dark(im, w.get("lighting") == "night")
        cp = os.path.join(args.cache, w["folder"].replace("/", "_") + "_" + n["file"].replace(".jpg", ".png"))
        if dark:
            seg = None                      # not used for low-light photos
        elif os.path.exists(cp):
            seg = np.asarray(Image.open(cp))
        else:
            if model is None:
                if not args.model:
                    raise SystemExit("--model is needed: %s is not cached" % cp)
                model = load_model(args.model)
            seg = model(im)
            Image.fromarray(seg).save(cp)
            print(f"{k + 1}/{len(work)} {w['folder']} {n['file']}", flush=True)
        if args.segment_only:
            continue
        n["ov"] = trace(im, seg, dark)
    if args.segment_only:
        return
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(DATA, "manifest.js"), "w") as f:
        f.write("window.STREET_DATA = ")
        json.dump(manifest, f)
        f.write(";\n")
    print(f"{len(work)} photos traced")


if __name__ == "__main__":
    main()
