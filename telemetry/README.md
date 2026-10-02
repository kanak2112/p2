# Street Intelligence — Pedestrian Telemetry Pipeline

Turns daily walk videos of the 195m footpath corridor into an interactive dashboard
with no manual editing.

## Setup (one time)

```bash
cd telemetry
pip install -r requirements.txt
```

## Daily workflow

1. Save the day's videos into `telemetry/data/raw/` named by day and direction:
   `day_01_forward.mp4`, `day_01_return.mp4`, `day_02_forward.mp4`, …
   (`.mov` / `.m4v` also work).
2. Run `python pipeline.py`. New videos are processed; ones already done are skipped
   (use `--force` to redo them all).
3. Run `python app.py` and open http://localhost:5000.

The day slider only shows days that have been processed, and each strip shows
however many nodes that walk actually produced.

### Pipeline options

| Flag | Default | Meaning |
|---|---|---|
| `--step-sec` | 2.5 | Seconds between sampled frames |
| `--motion-thresh` | 2.0 | Mean pixel change below which a sample counts as standing still and is dropped |
| `--crop-top` | 0.20 | Fraction of the frame cropped from the top (sky/background) |

If stationary moments (e.g. waiting at a crossing) still show up, raise
`--motion-thresh`; if walking frames are being dropped, lower it.

### How node positions are estimated

Only moving samples are kept, so nodes are spread evenly from 0m to 195m
(forward walk) or 195m to 0m (return walk). This assumes a roughly steady
walking pace. Each node also records its timestamp in the video (`time_s`).

### Output

`telemetry/web/data/` (git-ignored, like `data/raw/`):

- `manifest.json`: which days and directions exist, and how many nodes each has
- `day<N>_<direction>/node_###.jpg` plus `nodes.json` (`node`, `file`, `meter`, `time_s`)
