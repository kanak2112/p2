"""
Soundscape layer from each walk's own audio track, written into data/manifest.json/.js.

  spot_views["db"]   loudness of each one-second spot view (1 s window centred on its time),
                     in dB relative to the median second of ALL surveyed walks (0 = typical)
  walk["honks"]      horn events: [{"t": start, video seconds, "dur": seconds, "m": camera metres}]
  walk["audio"]      {"median_dbfs": ..., "honks": count, "horn_s": total horn seconds, "honks_per_100m": ...}

Levels are relative. A phone microphone is not calibrated and phones apply automatic gain control,
so these numbers compare places along the corridor, not absolute dB(A). To compare with CPCB limits,
record 30 s next to a sound level meter at one spot and add that offset.

Horn detection: a narrow spectral peak between 1.5 and 5 kHz, at least PROM_DB above the neighbouring
frequencies, holding the same pitch for at least 150 ms, with at least two such tones at once (a horn's harmonics). Horns are steady tones; footsteps, bangs and
phone handling are broadband, and speech glides in pitch. Events less than 1 s apart merge.
Checked by eye against spectrograms of three walks: most marks sit on horns, but faint horns under\ntraffic noise are missed and one long horn can split into two events, so horn-seconds is the steadier\nmeasure. Treat both as estimates.

Run after process_day1.py:  python soundscape.py
"""
import json
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SR = 16000
HOP, WIN = 400, 800            # 25 ms hop, 50 ms window
F_LO, F_HI = 1500, 5000        # horn fundamentals and first harmonics
MED_BINS = 15                  # 300 Hz neighbourhood for the spectral baseline
PROM_DB = 12.0                 # a horn tone stands this far above neighbouring frequencies
MIN_FRAMES = 6                 # held for 6 hops = 150 ms
MIN_PARTIALS = 2               # at least two simultaneous held tones (a harmonic stack)
MERGE_S = 1.0


def audio_of(path):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def dbfs(x):
    return 10 * np.log10(np.mean(x.astype(np.float64) ** 2) + 1e-12)


def honk_times(x):
    """Horns are stationary tones: a narrow spectral peak well above the neighbouring frequencies that
    holds the same pitch for at least MIN_FRAMES hops. Footsteps, bangs and phone handling are broadband
    (no narrow peak); speech changes pitch from frame to frame."""
    n = 1 + max(0, (len(x) - WIN) // HOP)
    frames = np.lib.stride_tricks.as_strided(x, shape=(n, WIN), strides=(x.strides[0] * HOP, x.strides[0]))
    freqs = np.fft.rfftfreq(WIN, 1 / SR)
    sel = (freqs >= F_LO) & (freqs <= F_HI)
    S = 10 * np.log10(np.abs(np.fft.rfft(frames * np.hanning(WIN), axis=1))[:, sel] ** 2 + 1e-12)
    pad = np.pad(S, ((0, 0), (MED_BINS // 2, MED_BINS // 2)), mode="edge")
    base = np.median(np.lib.stride_tricks.sliding_window_view(pad, MED_BINS, axis=1), axis=2)
    peak = (S - base) >= PROM_DB
    peak &= S >= S.max(axis=1, keepdims=True) - 25          # ignore faint peaks far below the frame's loudest
    # a bin is "held" if it (or a neighbour) is a peak in each of the next MIN_FRAMES frames
    near = peak | np.roll(peak, 1, axis=1) | np.roll(peak, -1, axis=1)
    held = peak.copy()
    for k in range(1, MIN_FRAMES):
        held[:-k] &= near[k:]
        held[-k:] = False
    # horns are harmonic stacks: count held peaks that are not neighbours of each other
    distinct = held & ~np.roll(held, 1, axis=1)
    on = distinct.sum(axis=1) >= MIN_PARTIALS
    events, i = [], 0                                       # (start, end) seconds
    while i < n:
        if on[i]:
            j = i
            while j + 1 < n and on[j + 1]:
                j += 1
            events.append([(i * HOP + WIN / 2) / SR, ((j + MIN_FRAMES) * HOP + WIN / 2) / SR])
            i = j + 1
        else:
            i += 1
    merged = []
    for a, b in events:
        if merged and a - merged[-1][1] <= MERGE_S:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def main():
    with open(os.path.join(DATA, "manifest.json")) as f:
        manifest = json.load(f)
    walks = []
    for d in manifest["days"]:
        if d.get("mock"):
            continue
        for key in ("forward", "return"):
            w = d.get(key)
            if not w or not w.get("spot_views") or not w.get("source"):
                continue
            path = os.path.join(HERE, w["source"])
            if not os.path.exists(path):
                print(f"Day {d['day']} {key}: {w['source']} not found, skipped")
                continue
            x = audio_of(path)
            sv = w["spot_views"]
            secs = [dbfs(x[max(0, int((t - 0.5) * SR)):int((t + 0.5) * SR)]) if len(x) > int(t * SR) else None for t in sv["t"]]
            honks = honk_times(x)
            m_of = lambda t: float(np.interp(t, sv["t"], sv["m"]))
            w["honks"] = [{"t": round(a, 2), "dur": round(b - a, 2), "m": round(m_of(a), 1)} for a, b in honks if sv["t"][0] <= a <= sv["t"][-1]]
            walks.append((d["day"], key, w, secs))

    every = [s for *_, secs in walks for s in secs if s is not None]
    ref = float(np.median(every))
    L = manifest["corridor"]["length_m"]
    for day, key, w, secs in walks:
        w["spot_views"]["db"] = [None if s is None else round(s - ref, 1) for s in secs]
        valid = [s for s in secs if s is not None]
        w["audio"] = {"median_dbfs": round(float(np.median(valid)), 1), "ref_dbfs": round(ref, 1),
                      "honks": len(w["honks"]), "horn_s": round(sum(h["dur"] for h in w["honks"]), 1),
                      "honks_per_100m": round(len(w["honks"]) / L * 100, 1)}
        print(f"Day {day} {key:7s} {w.get('lighting', ''):8s} median {w['audio']['median_dbfs'] - ref:+5.1f} dB  "
              f"horns {len(w['honks']):3d}  horn-seconds {w['audio']['horn_s']:5.1f}")

    by_folder = {w["folder"]: w for *_, w, _ in walks}
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
