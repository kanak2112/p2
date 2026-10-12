#!/usr/bin/env python3
"""
Rough pedestrian count for every kept frame (people visible ahead), written into data/manifest.json/.js
as node["people"]. Uses OpenCV's built-in HOG pedestrian detector, which needs OpenCV 4.x
(OpenCV 5 removed it): pip install "opencv-python-headless<5".

It undercounts people who are close to the camera, partly hidden or in dense groups, so treat it
as a relative indicator of how busy a stretch is, not a footfall count.

Run after process_day1.py:  python count_people.py
"""
import json
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def main():
    if not hasattr(cv2, "HOGDescriptor"):
        raise SystemExit("This OpenCV build has no HOG detector. Install opencv-python-headless<5.")
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    path = os.path.join(DATA, "manifest.json")
    with open(path) as f:
        manifest = json.load(f)
    done = {}
    for d in manifest["days"]:
        for key in ("forward", "return"):
            w = d.get(key)
            if not w:
                continue
            if w["folder"] in done:          # placeholder days share a real day's walk
                d[key] = done[w["folder"]]
                continue
            for n in w["nodes"]:
                img = cv2.imread(os.path.join(HERE, w["folder"], n["file"]))
                rects, weights = hog.detectMultiScale(img, winStride=(8, 8), padding=(8, 8), scale=1.05)
                n["people"] = int(sum(1 for wt in np.array(weights).ravel() if wt > 0.5))
            done[w["folder"]] = w
            print(f"{w['folder']}: {sum(n['people'] for n in w['nodes'])} detections in {len(w['nodes'])} frames")
    with open(path, "w") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(DATA, "manifest.js"), "w") as f:
        f.write("window.STREET_DATA = ")
        json.dump(manifest, f)
        f.write(";\n")


if __name__ == "__main__":
    main()
