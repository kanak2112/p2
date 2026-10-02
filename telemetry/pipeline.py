"""
Street Intelligence — video processing pipeline.

Drop raw walk videos into telemetry/data/raw/ named

    day_01_forward.mp4   day_01_return.mp4
    day_02_forward.mp4   ...

then run `python pipeline.py`. Every video is step-sampled into JPEG "nodes"
under telemetry/web/data/day<N>_<direction>/ with a nodes.json, and a
manifest.json describing all processed days is written for the dashboard.
"""
import argparse
import json
import os
import re

import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
OUT_DIR = os.path.join(BASE_DIR, "web", "data")

CORRIDOR_LENGTH_M = 195.0
VIDEO_PATTERN = re.compile(r"^day_(\d+)_(forward|return)\.(mp4|mov|m4v)$", re.IGNORECASE)


def extract_step_sampled_frames(video_path, output_dir, direction="forward", step_sec=2.5,
                                min_motion_thresh=2.0, crop_top=0.20,
                                corridor_length=CORRIDOR_LENGTH_M):
    """
    Ingests raw walker video, samples one frame every `step_sec` seconds, skips
    samples where the walker was stationary (e.g. waiting at a crosswalk), and
    crops the top `crop_top` fraction (sky/background) to focus on the ground plane.

    Node positions are spread evenly across the corridor, since only moving
    samples are kept. Return walks run from corridor_length back to 0m.
    """
    os.makedirs(output_dir, exist_ok=True)
    for name in os.listdir(output_dir):  # clear nodes from a previous run
        if name.startswith("node_") and name.endswith(".jpg"):
            os.remove(os.path.join(output_dir, name))

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, int(round(fps * step_sec)))

    frame_count = 0
    files = []
    times = []
    last_kept_gray = None

    print(f"Processing '{video_path}'...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % frame_interval == 0:
            # Compare against the last *kept* frame on a small blurred copy,
            # so sensor noise doesn't count as motion.
            small = cv2.resize(frame, (160, 90))
            gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
            moving = (last_kept_gray is None or
                      float(np.mean(cv2.absdiff(gray, last_kept_gray))) >= min_motion_thresh)

            if moving:
                last_kept_gray = gray
                h = frame.shape[0]
                cropped = frame[int(h * crop_top):, :]

                filename = f"node_{len(files):03d}.jpg"
                cv2.imwrite(os.path.join(output_dir, filename), cropped,
                            [cv2.IMWRITE_JPEG_QUALITY, 85])
                files.append(filename)
                times.append(round(frame_count / fps, 2))

        frame_count += 1

    cap.release()

    n = len(files)
    metadata = []
    for i, (filename, t) in enumerate(zip(files, times)):
        progress = i / (n - 1) if n > 1 else 0.0
        meter = progress * corridor_length
        if direction == "return":
            meter = corridor_length - meter
        metadata.append({"node": i, "file": filename, "meter": round(meter, 1), "time_s": t})

    with open(os.path.join(output_dir, "nodes.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Done! Extracted {n} spatial nodes to '{output_dir}'.")
    return metadata


def build_manifest(out_dir=OUT_DIR):
    """Scan processed folders and write manifest.json: {"days": [{"day": 1, "forward": n, "return": n}, ...]}."""
    days = {}
    if os.path.isdir(out_dir):
        for name in os.listdir(out_dir):
            m = re.match(r"^day(\d+)_(forward|return)$", name)
            nodes_path = os.path.join(out_dir, name, "nodes.json")
            if not m or not os.path.isfile(nodes_path):
                continue
            with open(nodes_path) as f:
                count = len(json.load(f))
            day = int(m.group(1))
            days.setdefault(day, {"day": day, "forward": 0, "return": 0})[m.group(2)] = count

    manifest = {"corridor_length": CORRIDOR_LENGTH_M, "days": [days[d] for d in sorted(days)]}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Step-sample daily walk videos into dashboard nodes.")
    parser.add_argument("--raw-dir", default=RAW_DIR, help="folder containing day_XX_<direction>.mp4 files")
    parser.add_argument("--step-sec", type=float, default=2.5, help="seconds between sampled frames")
    parser.add_argument("--motion-thresh", type=float, default=2.0,
                        help="mean pixel difference below which a sample counts as stationary")
    parser.add_argument("--crop-top", type=float, default=0.20, help="fraction of frame height to crop from the top")
    parser.add_argument("--force", action="store_true", help="reprocess videos that already have output")
    args = parser.parse_args()

    os.makedirs(args.raw_dir, exist_ok=True)
    videos = sorted(n for n in os.listdir(args.raw_dir) if VIDEO_PATTERN.match(n))
    if not videos:
        print(f"No videos found in '{args.raw_dir}'. Expected names like day_01_forward.mp4.")

    for name in videos:
        m = VIDEO_PATTERN.match(name)
        day, direction = int(m.group(1)), m.group(2).lower()
        out = os.path.join(OUT_DIR, f"day{day}_{direction}")
        src = os.path.join(args.raw_dir, name)
        nodes_json = os.path.join(out, "nodes.json")
        if (not args.force and os.path.isfile(nodes_json)
                and os.path.getmtime(nodes_json) >= os.path.getmtime(src)):
            print(f"Skipping '{name}' (already processed; use --force to redo).")
            continue
        extract_step_sampled_frames(src, out, direction=direction, step_sec=args.step_sec,
                                    min_motion_thresh=args.motion_thresh, crop_top=args.crop_top)

    manifest = build_manifest()
    print(f"Manifest updated: {len(manifest['days'])} day(s) available.")


if __name__ == "__main__":
    main()
