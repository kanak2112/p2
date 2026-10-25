"""
Swerves: moments the walker turned aside and back, read from the chest-mounted camera's sideways
rotation (yaw). Written into data/manifest.json/.js as walk["swerves"] = [{"t", "m", "deg"}].

Method: frames at 5 fps, 160 px wide, grey. Horizontal image shift between consecutive frames
(phase correlation) gives yaw rate; integrating gives heading. Subtracting a 4 s moving average
removes the corridor's own bends (the turn at 104 m, the underpass jog), leaving short excursions.
A swerve is an excursion of at least SWERVE_DEG that comes back within a few seconds.

Angles assume a 39 deg horizontal field of view (portrait phone, main lens), so treat them as
approximate. A chest mount turns with the torso, so a swerve means the body turned aside, which
is what a walker does to get round a parked bike or a person; looking around with the head alone
does not register.

Run after process_day1.py:  python swerves.py
"""
import json
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FPS, W = 5.0, 160
HFOV = 39.0
SWERVE_DEG = 12.0
MIN_GAP_S = 2.0
EDGE_S = 3.0


def yaw_track(path):
    cap = cv2.VideoCapture(path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(src_fps / FPS)))
    win, prev, times, rate = None, None, [], []
    i = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, fr = cap.retrieve()
            if not ok:
                break
            h, w = fr.shape[:2]
            g = cv2.cvtColor(cv2.resize(fr, (W, int(round(W * h / w)))), cv2.COLOR_BGR2GRAY).astype(np.float32)
            g = g[: int(g.shape[0] * 0.5)]          # upper half: buildings and sky, little ground flow
            if win is None:
                win = cv2.createHanningWindow(g.shape[::-1], cv2.CV_32F)
            if prev is not None:
                (dx, _), resp = cv2.phaseCorrelate(prev, g, win)
                rate.append(-dx * HFOV / W if resp > 0.05 else 0.0)   # degrees turned this step (+ = right)
                times.append(i / src_fps)
            prev = g
        i += 1
    cap.release()
    return np.array(times), np.array(rate)


def swerves(times, rate):
    if len(rate) < 10:
        return []
    heading = np.cumsum(rate)
    k = int(4 * FPS)
    base = np.convolve(np.pad(heading, (k // 2, k // 2), mode="edge"), np.ones(k) / k, mode="valid")[: len(heading)]
    hp = heading - base
    out, last = [], -1e9
    for j in range(1, len(hp) - 1):
        if abs(hp[j]) >= SWERVE_DEG and abs(hp[j]) >= abs(hp[j - 1]) and abs(hp[j]) >= abs(hp[j + 1]) and times[j] - last >= MIN_GAP_S:
            out.append((float(times[j]), float(hp[j])))
            last = times[j]
    return out


def main():
    with open(os.path.join(DATA, "manifest.json")) as f:
        manifest = json.load(f)
    for d in manifest["days"]:
        if d.get("mock"):
            continue
        for key in ("forward", "return"):
            w = d.get(key)
            if not w or not w.get("source"):
                continue
            path = os.path.join(HERE, w["source"])
            if not os.path.exists(path):
                continue
            t, r = yaw_track(path)
            sv = w["spot_views"]
            ev = [(a, deg) for a, deg in swerves(t, r) if sv["t"][0] + EDGE_S <= a <= sv["t"][-1] - EDGE_S]   # ignore setting off and arriving
            w["swerves"] = [{"t": round(a, 1), "m": round(float(np.interp(a, sv["t"], sv["m"])), 1), "deg": round(deg, 1)} for a, deg in ev]
            print(f"Day {d['day']} {key:7s} swerves {len(ev):3d}")
    by_folder = {d[k]["folder"]: d[k] for d in manifest["days"] if not d.get("mock") for k in ("forward", "return") if d.get(k)}
    for d in manifest["days"]:
        if d.get("mock"):
            for key in ("forward", "return"):
                if d.get(key) and d[key].get("folder") in by_folder:
                    d[key] = by_folder[d[key]["folder"]]
    with open(os.path.join(DATA, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(DATA, "manifest.js"), "w") as f:
        f.write("window.STREET_DATA = ")
        json.dump(manifest, f)
        f.write(";\n")


if __name__ == "__main__":
    main()
