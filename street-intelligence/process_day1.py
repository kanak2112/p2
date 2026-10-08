#!/usr/bin/env python3
"""
Street Intelligence: video-to-spatial-substrate pipeline.

Turns a day's two corridor walks into step-sampled frames plus measurements
that index.html reads:

    point_a_to_b.mp4  ->  data/day1_forward/frame_000.jpg ...   (0 m -> 300 m)
    point_b_to_a.mp4  ->  data/day1_return/frame_000.jpg ...    (300 m -> 0 m)
    data/manifest.json and data/manifest.js

How it works
  1. The video is probed every 0.5 s. Each probe is compared with the previous
     one; when the picture barely changes, the walker is standing still.
     Still spells of 1.5 s or more are recorded as stops (time and position).
     Spells of 2 s or more at under ~55% of normal walking motion are recorded
     as slowdowns (edging past a hawker, a crowd); these are less certain.
  2. A frame is kept every `--step` seconds of *walking* time, so stops never
     produce duplicate frames.
  3. Position along the corridor is estimated from walking time, assuming a
     steady pace while moving (stops excluded). It is an estimate, not GPS.
     Later days are then lined up with the first surveyed day by matching
     frames on appearance, so the same spot gets the same metre across days.
  4. Each kept frame gets two image measures (proxies, not object detection):
       obstruction  edge density in the walking zone (lower-middle of frame),
                    relative to this walk's median. ~1.0 = typical for this walk.
       near_field   the same measure in the bottom band, roughly the space
                    within ~1 m of the walker's body.

Usage
  python process_day1.py                      # Day 1 from the two default videos
  python process_day1.py --day 2 --forward d2_a_to_b.mp4 --return d2_b_to_a.mp4

Days 1-7 without real footage are filled with placeholder copies of the most
recent real day (marked "mock" in the manifest) so the 7-day slider works.
Process a real day later and its placeholder is replaced.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import sys

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PROBE_SEC = 0.5
MIN_STOP_SEC = 1.5
SLOW_RATIO = 0.55   # motion below this share of the walk's median = slowdown
MIN_SLOW_SEC = 2.0
SCHEDULE_DAYS = 7


def small_gray(frame):
    h, w = frame.shape[:2]
    g = cv2.cvtColor(cv2.resize(frame, (160, max(1, round(160 * h / w)))), cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(g, (5, 5), 0)


def iter_probes(cap, every):
    """Yield (probe_index, frame_index, frame) for every `every`-th frame."""
    f = p = 0
    while True:
        if f % every == 0:
            ok, frame = cap.read()
            if not ok:
                return
            yield p, f, frame
            p += 1
        elif not cap.grab():
            return
        f += 1


def analyse_motion(path, motion_thresh):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"Could not open '{path}'. Check the file name and that it is a video OpenCV can read.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    every = max(1, round(fps * PROBE_SEC))
    scores, frames_idx, prev = [], [], None
    for _, f, frame in iter_probes(cap, every):
        g = small_gray(frame)
        scores.append(float(np.mean(cv2.absdiff(g, prev))) if prev is not None else float("inf"))
        frames_idx.append(f)
        prev = g
    cap.release()
    if len(scores) < 2:
        sys.exit(f"'{path}' is too short to process.")

    s = np.array(scores)
    s[0] = s[1]
    s = np.array([np.median(s[max(0, i - 1):i + 2]) for i in range(len(s))])  # damp single-probe spikes
    thresh = motion_thresh if motion_thresh is not None else max(0.8, 0.35 * float(np.median(s)))
    still = s < thresh

    # Only still spells of MIN_STOP_SEC or longer count as stops.
    min_run = int(np.ceil(MIN_STOP_SEC / PROBE_SEC))
    i = 0
    while i < len(still):
        if still[i]:
            j = i
            while j < len(still) and still[j]:
                j += 1
            if j - i < min_run:
                still[i:j] = False
            i = j
        else:
            i += 1
    # Slowdowns: sustained low motion that is not a full stop (e.g. edging past a hawker or through a crowd).
    slow = (s < SLOW_RATIO * float(np.median(s))) & ~still
    min_slow = int(np.ceil(MIN_SLOW_SEC / PROBE_SEC))
    i = 0
    while i < len(slow):
        if slow[i]:
            j = i
            while j < len(slow) and slow[j]:
                j += 1
            if j - i < min_slow:
                slow[i:j] = False
            i = j
        else:
            i += 1
    times = np.array(frames_idx) / fps
    return {"fps": fps, "every": every, "times": times, "still": still, "slow": slow, "thresh": thresh,
            "duration": float(times[-1] + PROBE_SEC)}


def edge_density(gray, top, bottom, left, right):
    h, w = gray.shape
    roi = gray[int(h * top):int(h * bottom), int(w * left):int(w * right)]
    return float(np.mean(cv2.Canny(roi, 60, 160) > 0))


def process_walk(path, out_dir, direction, length_m, step_s, height, motion_thresh):
    print(f"\n{os.path.basename(path)} -> {os.path.relpath(out_dir, HERE)}  ({direction})")
    m = analyse_motion(path, motion_thresh)
    times, still = m["times"], m["still"]
    n = len(times)

    # Walking time accumulated up to each probe (a probe interval counts if the walker was moving).
    moving = np.zeros(n)
    for i in range(1, n):
        moving[i] = moving[i - 1] + (0.0 if still[i] else times[i] - times[i - 1])
    total_moving = moving[-1] or 1.0

    def metre(i):
        p = moving[i] / total_moving
        return round((p if direction == "forward" else 1 - p) * length_m, 1)

    # Pick node probes: one every step_s of walking time, plus the end of the walk.
    picks, nxt = [], 0.0
    for i in range(n):
        if not still[i] and moving[i] >= nxt:
            picks.append(i)
            nxt = moving[i] + step_s
    last_moving = max((i for i in range(n) if not still[i]), default=n - 1)
    if picks and moving[last_moving] - moving[picks[-1]] > step_s / 2:
        picks.append(last_moving)

    def runs(flags):
        out, i = [], 0
        while i < n:
            if flags[i]:
                j = i
                while j < n and flags[j]:
                    j += 1
                out.append({"t": round(float(times[i]), 1), "duration_s": round(float(times[min(j, n - 1)] - times[i] + PROBE_SEC), 1),
                            "meter": metre(i)})
                i = j
            else:
                i += 1
        return out

    stops = runs(still)
    slowdowns = runs(m["slow"])

    # Uninterrupted walking stretches between stops.
    stretches, start = [], 0
    for st in stops + [None]:
        end_i = n - 1 if st is None else int(np.searchsorted(times, st["t"]))
        secs = float(moving[end_i] - moving[start])
        if secs > 0:
            stretches.append({"seconds": round(secs, 1), "meters": round(secs / total_moving * length_m, 1),
                              "from_m": metre(start), "to_m": metre(end_i)})
        if st is not None:
            start = min(n - 1, int(np.searchsorted(times, st["t"] + st["duration_s"])))

    # Second pass: save picked frames and measure them.
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        if name.startswith("frame_") and name.endswith(".jpg"):
            os.remove(os.path.join(out_dir, name))
    wanted = {i: k for k, i in enumerate(picks)}
    cap = cv2.VideoCapture(path)
    nodes = []
    for p, _, frame in iter_probes(cap, m["every"]):
        if p not in wanted:
            continue
        k = wanted[p]
        h, w = frame.shape[:2]
        out_w = max(1, round(w * height / h))
        rgb = cv2.cvtColor(cv2.resize(frame, (out_w, height), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        fname = f"frame_{k:03d}.jpg"
        Image.fromarray(rgb).save(os.path.join(out_dir, fname), "JPEG", quality=80, optimize=True, progressive=True)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        nodes.append({"i": k, "file": fname, "meter": metre(p), "t": round(float(times[p]), 1),
                      "_obs": edge_density(gray, 0.55, 1.0, 0.2, 0.8),
                      "_near": edge_density(gray, 0.82, 1.0, 0.25, 0.75)})
    cap.release()

    # Express measures relative to this walk's median, so lighting differences between days matter less.
    for key, out in (("_obs", "obstruction"), ("_near", "near_field")):
        med = max(float(np.median([nd[key] for nd in nodes])), 0.02)  # floor: plain paving has few edges
        for nd in nodes:
            nd[out] = round(min(nd.pop(key) / med, 5.0), 2)

    summary = {
        "duration_s": round(m["duration"], 1),
        "walking_s": round(float(total_moving), 1),
        "stops": len(stops),
        "stopped_s": round(sum(s["duration_s"] for s in stops), 1),
        "slowdowns": len(slowdowns),
        "slowed_s": round(sum(s["duration_s"] for s in slowdowns), 1),
        "longest_uninterrupted_s": max((s["seconds"] for s in stretches), default=0),
        "longest_uninterrupted_m": max((s["meters"] for s in stretches), default=0),
        "motion_threshold": round(float(m["thresh"]), 2),
        "frame_size": [out_w, height] if nodes else None,
    }
    print(f"  {len(nodes)} frames kept, {len(stops)} stops ({summary['stopped_s']} s), "
          f"{len(slowdowns)} slowdowns ({summary['slowed_s']} s), "
          f"longest uninterrupted walk {summary['longest_uninterrupted_s']} s / {summary['longest_uninterrupted_m']} m")
    return {"folder": f"data/{os.path.basename(out_dir)}", "source": os.path.basename(path),
            "nodes": nodes, "stops": stops, "slowdowns": slowdowns, "stretches": stretches, "summary": summary}


def frame_signature(path):
    """Coarse appearance of the upper 60% of a frame (buildings, awnings, signs), normalised for brightness."""
    g = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g[:int(g.shape[0] * 0.6)], (12, 20), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    return (g - g.mean()) / (g.std() + 1e-6)


def align_to_reference(walk, ref):
    """
    Re-estimate frame positions by matching this walk's frames to a reference walk of the same direction
    (dynamic time warping on frame appearance). Walking-time positions drift with pace; the reference
    day's positions become the common scale, so the same spot lines up across days.
    """
    A = np.array([frame_signature(os.path.join(HERE, ref["folder"], n["file"])) for n in ref["nodes"]])
    B = np.array([frame_signature(os.path.join(HERE, walk["folder"], n["file"])) for n in walk["nodes"]])
    cost = 1 - (B @ A.T) / A.shape[1]
    n, k = cost.shape
    D = np.full((n + 1, k + 1), np.inf)
    D[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(1, k + 1):
            D[i, j] = cost[i - 1, j - 1] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    i, j, match = n, k, {}
    while i > 0 and j > 0:
        match.setdefault(i - 1, []).append(j - 1)
        step = int(np.argmin([D[i - 1, j - 1], D[i - 1, j], D[i, j - 1]]))
        i, j = (i - 1, j - 1) if step == 0 else (i - 1, j) if step == 1 else (i, j - 1)

    forward = ref["nodes"][-1]["meter"] > ref["nodes"][0]["meter"]
    metres = [float(np.mean([ref["nodes"][j]["meter"] for j in match[a]])) for a in range(n)]
    metres = list(np.maximum.accumulate(metres) if forward else np.minimum.accumulate(metres))
    for nd, m in zip(walk["nodes"], metres):
        nd["meter_time"] = nd["meter"]
        nd["meter"] = round(m, 1)
    # Remap stops and slowdowns through video time.
    ts = [nd["t"] for nd in walk["nodes"]]
    for key in ("stops", "slowdowns"):
        for e in walk.get(key, []):
            e["meter"] = round(float(np.interp(e["t"], ts, metres)), 1)
    walk["aligned_to"] = ref["folder"]
    shifts = [abs(nd["meter"] - nd["meter_time"]) for nd in walk["nodes"]]
    print(f"  aligned to {ref['folder']}: median shift {np.median(shifts):.1f} m, max {max(shifts):.1f} m")


def link_or_copy(src, dst):
    if os.path.islink(dst):
        os.remove(dst)
    elif os.path.isdir(dst):
        shutil.rmtree(dst)
    try:
        os.symlink(os.path.relpath(src, os.path.dirname(dst)), dst, target_is_directory=True)
    except (OSError, NotImplementedError):
        shutil.copytree(src, dst)


def main():
    ap = argparse.ArgumentParser(description="Process one day's corridor walks into frames and measurements.")
    ap.add_argument("--day", type=int, default=1)
    ap.add_argument("--forward", default="point_a_to_b.mp4", help="forward walk video (0 m -> end)")
    ap.add_argument("--return", dest="ret", default="point_b_to_a.mp4", help="return walk video (end -> 0 m)")
    ap.add_argument("--length", type=float, default=300.0, help="corridor length in metres")
    ap.add_argument("--step", type=float, default=3.0, help="seconds of walking between kept frames")
    ap.add_argument("--height", type=int, default=600, help="output frame height in px")
    ap.add_argument("--motion-thresh", type=float, default=None,
                    help="mean pixel change below which the walker counts as still (default: automatic)")
    ap.add_argument("--corridor-name", default="Point A to Point B")
    args = ap.parse_args()

    def resolve(p):
        return p if os.path.isabs(p) or os.path.exists(p) else os.path.join(HERE, p)

    os.makedirs(DATA, exist_ok=True)
    manifest_path = os.path.join(DATA, "manifest.json")
    manifest = {"days": []}
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)

    day = {"day": args.day, "mock": False, "processed": dt.date.today().isoformat()}
    for key, video, direction in (("forward", args.forward, "forward"), ("return", args.ret, "return")):
        path = resolve(video)
        if not os.path.exists(path):
            print(f"\nSkipping {direction} walk: '{video}' not found.")
            continue
        out = os.path.join(DATA, f"day{args.day}_{direction}")
        if os.path.islink(out):
            os.remove(out)
        day[key] = process_walk(path, out, direction, args.length, args.step, args.height, args.motion_thresh)
    if "forward" not in day and "return" not in day:
        sys.exit("No videos processed. Put point_a_to_b.mp4 and point_b_to_a.mp4 next to this script.")

    for key in ("forward", "return"):  # a real day without this direction must not keep an old placeholder link
        stale = os.path.join(DATA, f"day{args.day}_{key}")
        if key not in day and os.path.islink(stale):
            os.remove(stale)

    real = {d["day"]: d for d in manifest.get("days", []) if not d.get("mock")}
    for key in ("forward", "return"):  # line this day up with the first surveyed day of the same direction
        refs = [r for r in sorted(real) if r != args.day and key in real[r] and not real[r][key].get("aligned_to")]
        if key in day and refs and min(refs) < args.day:
            align_to_reference(day[key], real[min(refs)][key])
    real[args.day] = day

    # Fill days 1..7 that have no footage with copies of the latest earlier real day (or the first real day).
    days = []
    for n in sorted(set(range(1, SCHEDULE_DAYS + 1)) | set(real)):
        if n in real:
            days.append(real[n])
            continue
        mock = {"day": n, "mock": True}
        for key in ("forward", "return"):
            have = [r for r in real if key in real[r]]
            if not have:
                continue
            src_n = max([r for r in have if r < n], default=min(have))
            mock[key] = real[src_n][key]  # same frames and measures; image paths point at the real folder
            mock.setdefault("source_day", src_n)
            link_or_copy(os.path.join(DATA, f"day{src_n}_{key}"), os.path.join(DATA, f"day{n}_{key}"))
        days.append(mock)

    manifest = {
        "corridor": {"name": args.corridor_name, "city": "Mumbai", "length_m": args.length, "step_s": args.step},
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "days": days,
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(DATA, "manifest.js"), "w") as f:  # lets index.html load data when opened as a file
        f.write("window.STREET_DATA = ")
        json.dump(manifest, f)
        f.write(";\n")

    mocks = [d["day"] for d in days if d.get("mock")]
    print(f"\nManifest written: {len(days) - len(mocks)} real day(s)"
          + (f", placeholder copies for days {', '.join(map(str, mocks))}" if mocks else "")
          + ".\nOpen index.html in your browser.")


if __name__ == "__main__":
    main()
