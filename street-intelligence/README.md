# Street Intelligence

Longitudinal pedestrian diagnostic for a 220 m footpath corridor on Jijamata Rd / Old Nagardas Rd, Andheri East, Mumbai (M.Des Stage 2).

**Live prototype:** https://claude.ai/artifact/KEzQkQaU9v47sxLaw9jbG3
Always republish to this URL; do not create a new artifact.

## Run

```bash
pip install opencv-python pillow numpy
python process_day1.py            # reads point_a_to_b.mp4 and point_b_to_a.mp4
```

Then open `index.html` in a browser (double-click works; no server needed).

For later survey days:

```bash
python process_day1.py --day 2 --forward day2_a_to_b.mp4 --return day2_b_to_a.mp4
```

Days 1–7 without footage are filled with placeholder copies so the day slider works.
Placeholders are labelled in the page and are never counted as evidence.

## What is measured, and what is estimated

| Item | How | Confidence |
|---|---|---|
| Stops | ≥1.5 s with almost no frame-to-frame motion | High |
| Slowdowns | ≥2 s below ~55% of normal walking motion | Medium |
| Spot shown (m) | Camera position ± look-ahead (default 5 m, slider 2–8 m): A→B frames show the ground ahead, B→A frames the ground behind in corridor terms | Tune per landmark |
| Frame position (m) | Pinned to map landmarks (landmarks.json), walking time between them; later days matched to Day 1 by appearance | ±10 m roughly |
| Obstruction index | Edge density in the walking zone vs. the walk's typical frame; ≥1.4 = obstructed | Image proxy: reacts to vehicles, stalls, crowds, also busy paving |
| Body zone (<0.8 m) | Same measure in the bottom band of the frame | Image proxy, not a distance measurement |
| Persistence | Share of surveyed days a 10 m spot is obstructed; static ≥85%, needs ≥3 days | Real days only |

## Benchmarks in the evidence summary

- **100 m continuous walk without obstacles**: Neural City, *State of Indian Streets 2026*
  (reported: 5.5% of Mumbai roads meet it).
- **12-second uninterrupted walk**: set by the study team. No published WRI India source
  was found; add the citation in `index.html` (`BENCH`) before sending.
