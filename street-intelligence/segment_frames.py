"""
What blocks the footpath: semantic segmentation of every kept frame, written into data/manifest.json/.js
as node["seg"].

Model: DeepLab v3 (Xception65) trained on Cityscapes, Google's published frozen graph:
  https://storage.googleapis.com/download.tensorflow.org/models/deeplabv3_cityscapes_train_2018_02_06.tar.gz
Unpack it and pass the .pb with --model. Needs:  pip install tensorflow-cpu

Per frame, inside the walking zone (rows 55-100 %, columns 20-80 %, the zone the obstruction score uses):
  people    person + rider
  vehicles  car, truck, bus, motorcycle, bicycle (parked or moving)
  fixed     pole, sign, traffic light, fence, wall
and over the whole frame: sky, vegetation.
  gap_m     free width at the 4 m look-ahead line: the widest run of pixels that are not a person, vehicle,
            pole, wall, building or vegetation, overlapping the central third of the frame (median over
            a 17-row band). Converted to metres with an ASSUMED camera (1.3 m high, 10 deg down, 65 deg
            vertical field of view), so it is uncalibrated; gap_edge = the run reaches the frame edge, so
            the real gap may be wider (portrait frames span only about 3 m at 4 m).

What the 50-frame test showed: people and vehicles segment well in daylight; night frames are unreliable;
the model does NOT recognise unkerbed Mumbai footpaths as "sidewalk" (it calls them road), so no
footpath-vs-road measure is attempted here. The viewer uses daylight frames only.

Slow on CPU (~14 s a frame). Resumable: frames that already have "seg" are skipped, and the manifest is
saved after every walk.  python segment_frames.py --model path/to/frozen_inference_graph.pb
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
ZONE = (0.55, 1.0, 0.2, 0.8)
GROUPS = {"people": [11, 12], "vehicles": [13, 14, 15, 16, 17, 18], "fixed": [3, 4, 5, 6, 7]}
WHOLE = {"sky": [10], "vegetation": [8, 9]}
BLOCK = [2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18]
CAM_H, PITCH_DEG, VFOV_DEG, LOOK, BAND = 1.3, 10.0, 65.0, 4.0, 8


def row_and_mpp(H):
    f = (H / 2) / np.tan(np.radians(VFOV_DEG / 2))
    below = np.degrees(np.arctan(CAM_H / LOOK)) - PITCH_DEG
    z = LOOK * np.cos(np.radians(PITCH_DEG)) + CAM_H * np.sin(np.radians(PITCH_DEG))
    return int(round(H / 2 + f * np.tan(np.radians(below)))), z / f


def free_gap(seg, y, W):
    widths = []
    for yy in range(max(0, y - BAND), min(seg.shape[0], y + BAND + 1)):
        free = ~np.isin(seg[yy], BLOCK)
        best, run = (0, None), None
        for x in range(W + 1):
            f = x < W and free[x]
            if f and run is None:
                run = x
            if not f and run is not None:
                a, b = run, x - 1
                run = None
                if b >= W // 3 and a <= 2 * W // 3 and b - a + 1 > best[0]:
                    best = (b - a + 1, (a, b))
        widths.append(best)
    return sorted(widths, key=lambda r: r[0])[len(widths) // 2]


def share(seg, box, cls):
    H, W = seg.shape
    t, b, l, r = box
    return float(np.isin(seg[int(H * t):int(H * b), int(W * l):int(W * r)], cls).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="DeepLab v3 Cityscapes frozen_inference_graph.pb")
    args = ap.parse_args()
    import tensorflow as tf
    g = tf.Graph()
    with g.as_default():
        gd = tf.compat.v1.GraphDef()
        with open(args.model, "rb") as f:
            gd.ParseFromString(f.read())
        tf.import_graph_def(gd, name="")
    sess = tf.compat.v1.Session(graph=g)

    path = os.path.join(DATA, "manifest.json")
    with open(path) as f:
        manifest = json.load(f)

    def save():
        with open(path, "w") as f:
            json.dump(manifest, f, indent=1)
        with open(os.path.join(DATA, "manifest.js"), "w") as f:
            f.write("window.STREET_DATA = ")
            json.dump(manifest, f)
            f.write(";\n")

    for d in manifest["days"]:
        if d.get("mock"):
            continue
        for key in ("forward", "return"):
            w = d.get(key)
            if not w or not w.get("frame_sheet"):
                continue
            todo = [n for n in w["nodes"] if "seg" not in n]
            if not todo:
                continue
            fs = w["frame_sheet"]
            sheet = Image.open(os.path.join(HERE, w["folder"], fs["file"])).convert("RGB")
            fw, fh = fs["size"]
            for n in todo:
                j = n.get("cell", n["i"])
                r, c = divmod(j, fs["cols"])
                im = np.asarray(sheet.crop((c * fw, r * fh, (c + 1) * fw, (r + 1) * fh)))
                seg = sess.run("SemanticPredictions:0", {"ImageTensor:0": im[None]})[0].astype(np.uint8)
                y, mpp = row_and_mpp(fh)
                px, run = free_gap(seg, y, fw)
                rec = {k: round(share(seg, ZONE, v), 3) for k, v in GROUPS.items()}
                rec.update({k: round(share(seg, (0, 1, 0, 1), v), 3) for k, v in WHOLE.items()})
                rec["gap_m"] = round(px * mpp, 2)
                rec["gap_edge"] = bool(run and (run[0] == 0 or run[1] == fw - 1))
                n["seg"] = rec
            save()
            print(f"Day {d['day']} {key}: {len(todo)} frames segmented")

    # placeholder days share walks by folder
    by_folder = {d[k]["folder"]: d[k] for d in manifest["days"] if not d.get("mock") for k in ("forward", "return") if d.get(k)}
    for d in manifest["days"]:
        if d.get("mock"):
            for key in ("forward", "return"):
                if d.get(key) and d[key].get("folder") in by_folder:
                    d[key] = by_folder[d[key]["folder"]]
    save()


if __name__ == "__main__":
    main()
