# Street Intelligence Map: developer spec

App: `map.html` (open it from this folder so `data/manifest.js` and the frame sheets load). Build a deployable copy with `python build_site.py` (writes `site/`).
Figma: P2 file, section "Street Intelligence · Pedestrian map v2 (clickable)".

The prototype is the behaviour reference. Every number it shows is computed in the browser from
`data/manifest.js`; nothing is hard-coded except the map outline and the landmark names.

## Data

`window.STREET_DATA` (written by `process_day1.py` and the other pipeline scripts).

| Field | Meaning |
| --- | --- |
| `corridor.length_m` | 220. Chainage runs from A (R.K. Chouhan, 0 m) to B (Amratlal G. Vasani, 220 m). |
| `corridor.landmarks` | Chainage of the green bins (80), the turn onto the highway service road (104), the underpass walkway (162 to 191). |
| `days[].day`, `days[].processed` | Survey day number and upload date. The pilot videos lost their recording dates, so upload date stands in for the date filter. |
| `days[].forward / return` | One walk A → B / B → A. `lighting` is `daylight` or `night`; `summary.duration_s` is the walk time. |
| `walk.nodes[]` | One kept photo every 3 s: `meter` (chainage), `t`, `obstruction`, `near_field`, `cell` (index in `frames.jpg`), `seg` (segmentation shares). |
| `walk.frame_sheet` | `frames.jpg`, 10 columns, 338 × 600 px cells. |
| `walk.spot_views` | 1 fps samples with `c` (clutter bitmask on a 4 × 3 grid over the walking zone) and `grid`. Used for the red clutter boxes. |
| `walk.swerves[]` | `{t, m, deg}`: turns of 12° or more that come back within seconds. |
| `walk.honks[]` | `{t, dur, m}`: detected horns. |

## Rules

All rules work on 10 m stretches (22 of them), on the walks that pass the current filters.

- **Worst photo**: for each walk, the node in the stretch with the highest `obstruction`.
- **Blocked**: worst photo `obstruction ≥ 1.4`. Share = blocked walks / walks with a photo in the stretch.
- **Proxemic band** of the worst photo: `near_field ≥ 1.4` → intimate (< 0.8 m); else `obstruction ≥ 1.4` → social (0.8–1.2 m); else clear (≥ 1.2 m).
- **Room to walk (estimate)**: mean over walks of 0.6 m (intimate), 1.0 m (social), 1.5 m (clear). Between stretch centres it is eased with a cosine. Always labelled as estimated until tape measurements exist.
- **Usual band**: the most frequent band; ties go to the worse band.
- **Fewer than 3 walks** in a direction: show the counts but say "too few to judge".

### Layers (colour scale: teal `#1AA6C0`, amber `#F5B014`, dark red `#9F1D1D`, grey `#AEB4AA` = no walks)

| Layer | Value per stretch | Teal | Amber | Dark red |
| --- | --- | --- | --- | --- |
| Blocked | blocked share | < 1/3 | 1/3 to 2/3 | > 2/3 |
| Room | usual band | clear | social | intimate |
| Crowding | mean `seg.people`, daylight photos only | < 0.10 | 0.10 to 0.20 | > 0.20 |
| Swerves | swerves per walk | < 0.25 | 0.25 to 0.5 | > 0.5 |
| Horns | horn-seconds per walk | < 0.6 | 0.6 to 1.0 | > 1.0 |

Shade and lighting are not offered until the capture standard records them.

### Filters

- **Date range**: Last 24 hours, 7 days, 30 days, year, all survey days, or custom (pick survey days). Ranges count back from the latest walk. Options with no walks are disabled; options with 1–2 walks say so.
- **Light**: any, daylight, night. All night walks were B → A; the UI says so wherever light is compared.
- Changing a filter recomputes every stretch, the map colours, the strip, the ribbon, the photos and the Ask answers.

### Directions

- Modes and when a stretch is flagged (direction-specific counts):
  - Walk: blocked share > 2/3.
  - Wheelchair: blocked share > 2/3, or usual band intimate or social.
  - Pram: blocked share > 2/3, or usual band intimate.
- Consecutive flagged stretches merge into one span. Time is the median walk time in that direction.
- The opposite footpath is listed as not recorded, with a Record action.

### Walk mode

- Position advances at the median walking speed for the direction, times the chosen speed (1×, 4×, 10×). The strip is scrubbable.
- The corridor view is drawn in perspective, 60 m ahead. The walking channel is as wide as the room-to-walk estimate and is coloured by band. Obstacle zones fill the rest of a schematic 2 m footpath, 65 % on the shop side.
- Banner: the next landmark manoeuvre. Warning: the next stretch within 60 m blocked on more than 2 in 3 walks in this direction, with its count, main cause (largest daylight segmentation share above 10 %) and usual band.

### Photos and overlays

- Each tile crops the walk's `frames.jpg` at the worst photo's `cell`.
- Overlay: the walking channel trapezoid (22,100 → 78,100 → 57,60 → 43,60 in % of the frame), filled and stroked in the band colour. When the band is not clear, red boxes mark clutter cells from the nearest spot view (within 2 s).
- Badge: the band's width range. Tapping a tile opens a larger view with the obstruction and near-field values and the segmentation shares.

### Ask

Ask runs fixed questions whose answers are computed from the current filters: pram route, worst stretches, daylight vs night, swerves, horns. Free text is matched to those questions by keyword. Nothing is generated by a language model.

## Screens

Explore (map, zoom, layers, strip, readout) · Search (stretch, landmark or metre) · Footpath stretch (date and light filters, verdict, strip, room to walk, photos with overlays, blocked by, swerves, horns, day and night, About these numbers, save, share) · Date range · Light · Layers · Blocked spots · Ask · Directions · Steps · Walk (preview) · Contribute (record the opposite footpath, check a photo) · You (saved stretches, walks) · Record (capture checklist).

Saved stretches, the chosen layer and photo checks are kept in the browser (localStorage).

## Deploy

1. `python build_site.py` copies `map.html` to `site/index.html` with `data/manifest.js` and the 15 photo sheets (about 21 MB).
2. Upload `site/` to any static host (GitHub Pages, Netlify, Cloudflare Pages, S3). There is no server code.
3. Rebuild after each new walk is processed.

## Not built yet

Map tiles and geocoding, accounts, upload, live location (walk mode is a preview at the median walking pace), and Live View.
