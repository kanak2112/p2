"""
Street Intelligence — interactive dashboard.

Run `python app.py` after `python pipeline.py` and open http://localhost:5000.
Reads web/data/manifest.json and each day's nodes.json, so the day slider and
photo strips reflect whatever has actually been processed.
"""
import os

from flask import Flask, render_template_string, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "web", "data")

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Street Intelligence: Micro-Spatial Pedestrian Diagnostic Tool</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0e0e10; color: #e1e1e6; padding: 24px; }
        header { display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: flex-end; margin-bottom: 24px; border-bottom: 1px solid #27272a; padding-bottom: 16px; }
        h1 { font-size: 22px; font-weight: 600; letter-spacing: -0.5px; }
        .meta { font-size: 13px; color: #a1a1aa; margin-top: 4px; }
        .badge { background: #27272a; border: 1px solid #3f3f46; color: #38bdf8; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }

        .toolbar { background: #18181b; border: 1px solid #27272a; border-radius: 10px; padding: 16px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 32px; align-items: center; }
        .control-group { display: flex; flex-direction: column; gap: 6px; }
        label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: #a1a1aa; font-weight: 600; }
        input[type=range] { accent-color: #38bdf8; cursor: pointer; width: 220px; }
        .mode-btn { padding: 6px 12px; background: #27272a; color: #fff; border: 1px solid transparent; border-radius: 4px; cursor: pointer; font-size: 12px; }
        .mode-btn.active { background: #ef4444; font-weight: 600; }
        .mode-btn.active.raw { background: #38bdf8; color: #0e0e10; }

        .corridor-container { background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 20px; }
        .channel-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #38bdf8; margin-bottom: 10px; display: flex; justify-content: space-between; }

        .photo-strip { display: flex; gap: 6px; overflow-x: auto; padding-bottom: 12px; min-height: 60px; }
        .node-card { flex: 0 0 180px; position: relative; border-radius: 6px; overflow: hidden; border: 2px solid #27272a; background: #000; transition: all 0.2s; }
        .node-card:hover, .node-card.linked { border-color: #38bdf8; transform: translateY(-2px); }
        .node-card img { width: 100%; height: 210px; object-fit: cover; display: block; }
        .node-tag { position: absolute; bottom: 6px; left: 6px; background: rgba(0,0,0,0.75); color: #fff; font-family: monospace; font-size: 10px; padding: 2px 6px; border-radius: 4px; }
        .empty { color: #71717a; font-size: 13px; padding: 20px 0; }

        .axis-meter { position: relative; height: 36px; background: #09090b; border: 1px solid #27272a; border-radius: 6px; margin: 12px 0; display: flex; justify-content: space-between; align-items: center; padding: 0 16px; font-family: monospace; font-size: 11px; color: #71717a; }
        .axis-cursor { position: absolute; top: 0; bottom: 0; width: 2px; background: #38bdf8; display: none; }

        /* Proxemic overlay mode */
        .proxemic-grid .node-card::after { content: ""; position: absolute; inset: 0; background: linear-gradient(to top, rgba(239,68,68,0.3) 0%, rgba(234,179,8,0.15) 40%, transparent 70%); pointer-events: none; }
    </style>
</head>
<body>

    <header>
        <div>
            <h1>Street Intelligence — <span id="lengthTitle">195</span>m Footpath Corridor</h1>
            <p class="meta">Longitudinal Spatial Telemetry | M.Des Stage 2 Diagnostic Platform</p>
        </div>
        <div class="badge">Target: Civic Advocates &amp; Urban Planners</div>
    </header>

    <div class="toolbar">
        <div class="control-group">
            <label id="sliderLabel">Temporal Scrubber</label>
            <div style="display: flex; align-items: center; gap: 12px;">
                <input type="range" id="daySlider" min="0" max="0" value="0" oninput="selectDay(this.value)">
                <span id="dayVal" style="font-weight: 700; color: #38bdf8; font-size: 14px;">—</span>
            </div>
        </div>

        <div class="control-group">
            <label>Substrate Overlay Mode</label>
            <div style="display: flex; gap: 8px;">
                <button id="rawBtn" class="mode-btn raw active" onclick="toggleProxemics(false)">Raw Photo Substrate</button>
                <button id="gridBtn" class="mode-btn" onclick="toggleProxemics(true)">Hall's Proxemic Grid</button>
            </div>
        </div>
    </div>

    <div class="corridor-container" id="mainContainer">
        <div class="channel-title">
            <span id="fwdTitle">↑ Northbound Track (Forward Walk)</span>
            <span style="color: #a1a1aa; font-weight: 400; font-size: 11px;">Subjective Viewpoint A</span>
        </div>
        <div class="photo-strip" id="forwardStrip"></div>

        <div class="axis-meter" id="axis"><div class="axis-cursor" id="axisCursor"></div></div>

        <div class="channel-title">
            <span id="retTitle">↓ Southbound Track (Return Walk)</span>
            <span style="color: #a1a1aa; font-weight: 400; font-size: 11px;">Subjective Viewpoint B</span>
        </div>
        <div class="photo-strip" id="returnStrip"></div>
    </div>

    <script>
        let manifest = { corridor_length: 195, days: [] };

        async function init() {
            try {
                const res = await fetch('/data/manifest.json', { cache: 'no-store' });
                if (res.ok) manifest = await res.json();
            } catch (e) { /* no data yet */ }

            const L = manifest.corridor_length;
            document.getElementById('lengthTitle').innerText = L;
            document.getElementById('fwdTitle').innerText = `↑ Northbound Track (Forward Walk: 0m → ${L}m)`;
            document.getElementById('retTitle').innerText = `↓ Southbound Track (Return Walk: ${L}m → 0m)`;

            const axis = document.getElementById('axis');
            for (let i = 0; i <= 8; i++) {
                const s = document.createElement('span');
                s.innerText = Math.round(L * i / 8) + 'm';
                axis.appendChild(s);
            }

            const days = manifest.days;
            const slider = document.getElementById('daySlider');
            if (!days.length) {
                document.getElementById('sliderLabel').innerText = 'Temporal Scrubber (no data yet)';
                slider.disabled = true;
                showEmpty('forwardStrip'); showEmpty('returnStrip');
                return;
            }
            slider.max = days.length - 1;
            document.getElementById('sliderLabel').innerText =
                `Temporal Scrubber (Day ${days[0].day} – ${days[days.length - 1].day})`;
            selectDay(0);
        }

        function showEmpty(id) {
            document.getElementById(id).innerHTML =
                '<div class="empty">No processed walk yet. Add videos to telemetry/data/raw/ and run <code>python pipeline.py</code>.</div>';
        }

        function selectDay(idx) {
            const entry = manifest.days[idx];
            document.getElementById('dayVal').innerText = 'Day ' + String(entry.day).padStart(2, '0');
            loadChannel('forwardStrip', `day${entry.day}_forward`, entry.forward);
            loadChannel('returnStrip', `day${entry.day}_return`, entry.return);
        }

        async function loadChannel(elementId, folder, count) {
            const el = document.getElementById(elementId);
            if (!count) { showEmpty(elementId); return; }
            let nodes = [];
            try {
                const res = await fetch(`/data/${folder}/nodes.json`, { cache: 'no-store' });
                nodes = await res.json();
            } catch (e) { showEmpty(elementId); return; }

            el.innerHTML = '';
            for (const n of nodes) {
                const card = document.createElement('div');
                card.className = 'node-card';
                card.dataset.meter = n.meter;
                card.innerHTML = `
                    <img src="/data/${folder}/${n.file}" loading="lazy" alt="Spatial node at ${n.meter}m">
                    <div class="node-tag">${Math.round(n.meter)}m · ${n.time_s}s</div>`;
                card.addEventListener('mouseenter', () => highlightMeter(n.meter, card));
                card.addEventListener('mouseleave', () => highlightMeter(null));
                el.appendChild(card);
            }
        }

        // Spatial hover: show position on the axis and highlight the nearest node in the other track.
        function highlightMeter(meter, source) {
            const cursor = document.getElementById('axisCursor');
            document.querySelectorAll('.node-card.linked').forEach(c => c.classList.remove('linked'));
            if (meter === null) { cursor.style.display = 'none'; return; }

            const axis = document.getElementById('axis');
            const pad = 16, w = axis.clientWidth - pad * 2;
            cursor.style.left = (pad + w * meter / manifest.corridor_length) + 'px';
            cursor.style.display = 'block';

            const other = source.parentElement.id === 'forwardStrip' ? 'returnStrip' : 'forwardStrip';
            let best = null, bestD = Infinity;
            document.querySelectorAll(`#${other} .node-card`).forEach(c => {
                const d = Math.abs(parseFloat(c.dataset.meter) - meter);
                if (d < bestD) { bestD = d; best = c; }
            });
            if (best) {
                best.classList.add('linked');
                best.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            }
        }

        function toggleProxemics(enable) {
            document.getElementById('mainContainer').classList.toggle('proxemic-grid', enable);
            document.getElementById('gridBtn').classList.toggle('active', enable);
            document.getElementById('rawBtn').classList.toggle('active', !enable);
        }

        init();
    </script>
</body>
</html>
"""


@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)


@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory(DATA_DIR, filename)


if __name__ == '__main__':
    print("Launching Street Intelligence Diagnostic Dashboard at http://localhost:5000")
    app.run(port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
