import { useState } from 'react'
import {
  MapPin,
  Sliders,
  ShieldCheck,
  AlertTriangle,
  Camera,
  Map,
  ChevronDown,
  Layers,
  Loader2,
  CheckCircle2,
} from 'lucide-react'

type Tab = 'map' | 'capture'
type MapLayer = 'nolli' | 'map'
type CaptureStatus = 'idle' | 'uploading' | 'done'

const TIME_MARKS = ['6 AM', '9 AM', '12 PM', '4 PM', '8 PM', '10 PM']

function StreetSvg({ layer }: { layer: MapLayer }) {
  if (layer === 'nolli') {
    return (
      <svg
        viewBox="0 0 390 600"
        preserveAspectRatio="xMidYMid slice"
        className="h-full w-full"
        role="img"
        aria-label="Nolli figure-ground map of IC Colony street"
      >
        <rect x="0" y="0" width="390" height="600" fill="#020617" />
        <rect x="0" y="0" width="120" height="600" fill="#f8fafc" />
        <rect x="270" y="0" width="120" height="600" fill="#f8fafc" />
        <rect x="60" y="40" width="45" height="90" fill="#020617" />
        <rect x="60" y="160" width="45" height="70" fill="#020617" />
        <rect x="60" y="260" width="45" height="110" fill="#020617" />
        <rect x="60" y="400" width="45" height="90" fill="#020617" />
        <rect x="285" y="60" width="50" height="100" fill="#020617" />
        <rect x="285" y="190" width="50" height="80" fill="#020617" />
        <rect x="285" y="300" width="50" height="120" fill="#020617" />
        <rect x="285" y="450" width="50" height="90" fill="#020617" />
        <rect x="150" y="280" width="90" height="16" rx="2" fill="#f8fafc" />
      </svg>
    )
  }

  return (
    <svg
      viewBox="0 0 390 600"
      preserveAspectRatio="xMidYMid slice"
      className="h-full w-full"
      role="img"
      aria-label="Top-down street map of IC Colony with footpaths and obstacles"
    >
      <rect x="0" y="0" width="390" height="600" fill="#0f172a" />

      {/* road */}
      <rect x="120" y="0" width="150" height="600" fill="#1e293b" />
      <line
        x1="195"
        y1="0"
        x2="195"
        y2="600"
        stroke="#475569"
        strokeWidth="2"
        strokeDasharray="14 12"
      />

      {/* footpaths */}
      <rect x="60" y="0" width="60" height="600" fill="#334155" />
      <rect x="270" y="0" width="60" height="600" fill="#334155" />

      {/* building footprints (left) */}
      <rect x="0" y="20" width="60" height="100" fill="#475569" stroke="#64748b" />
      <rect x="0" y="150" width="60" height="80" fill="#475569" stroke="#64748b" />
      <rect x="0" y="260" width="60" height="130" fill="#475569" stroke="#64748b" />
      <rect x="0" y="420" width="60" height="100" fill="#475569" stroke="#64748b" />

      {/* building footprints (right) */}
      <rect x="330" y="50" width="60" height="110" fill="#475569" stroke="#64748b" />
      <rect x="330" y="200" width="60" height="90" fill="#475569" stroke="#64748b" />
      <rect x="330" y="330" width="60" height="130" fill="#475569" stroke="#64748b" />
      <rect x="330" y="500" width="60" height="80" fill="#475569" stroke="#64748b" />

      {/* crosswalk */}
      <g fill="#e2e8f0">
        <rect x="120" y="330" width="12" height="30" />
        <rect x="140" y="330" width="12" height="30" />
        <rect x="160" y="330" width="12" height="30" />
        <rect x="180" y="330" width="12" height="30" />
        <rect x="200" y="330" width="12" height="30" />
        <rect x="220" y="330" width="12" height="30" />
        <rect x="240" y="330" width="12" height="30" />
        <rect x="260" y="330" width="12" height="30" />
      </g>

      {/* obstacle nodes on the footpath */}
      <circle cx="88" cy="90" r="7" fill="#f43f5e" stroke="#fecdd3" strokeWidth="1.5" />
      <circle cx="95" cy="210" r="7" fill="#f43f5e" stroke="#fecdd3" strokeWidth="1.5" />
      <circle cx="85" cy="470" r="7" fill="#f43f5e" stroke="#fecdd3" strokeWidth="1.5" />
      <circle cx="300" cy="140" r="7" fill="#f59e0b" stroke="#fde68a" strokeWidth="1.5" />
      <circle cx="300" cy="400" r="7" fill="#f43f5e" stroke="#fecdd3" strokeWidth="1.5" />

      {/* current user position */}
      <circle cx="195" cy="470" r="9" fill="#6366f1" stroke="#c7d2fe" strokeWidth="2" />
      <circle cx="195" cy="470" r="16" fill="none" stroke="#6366f1" strokeWidth="1.5" opacity="0.4" />
    </svg>
  )
}

function MetricCard({
  label,
  value,
  tone = 'default',
}: {
  label: string
  value: string
  tone?: 'default' | 'danger'
}) {
  return (
    <div className="flex flex-1 flex-col gap-0.5 rounded-xl bg-slate-800/60 px-3 py-2">
      <span className="text-[10px] uppercase tracking-wide text-slate-400">{label}</span>
      <span
        className={
          tone === 'danger'
            ? 'text-base font-semibold text-red-400'
            : 'text-base font-semibold text-slate-100'
        }
      >
        {value}
      </span>
    </div>
  )
}

function ComplianceAccordion() {
  const [open, setOpen] = useState(false)

  return (
    <div className="mt-3 shrink-0 rounded-xl border border-slate-800 bg-slate-900/60">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2.5"
      >
        <span className="flex items-center gap-2 text-xs font-medium text-slate-200">
          <ShieldCheck size={14} className="text-indigo-400" />
          IRC Statutory Compliance Details
        </span>
        <ChevronDown
          size={16}
          className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && (
        <div className="space-y-2 border-t border-slate-800 px-3 py-2.5 text-xs text-slate-300">
          <div className="flex items-start gap-2">
            <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-400" />
            <p>
              <span className="font-semibold text-slate-100">IRC 103 — Footpath Width.</span>{' '}
              Minimum clear width of 180 cm required for unobstructed pedestrian movement.
              Measured usable width at this segment is 94 cm.
            </p>
          </div>
          <div className="flex items-start gap-2">
            <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-400" />
            <p>
              <span className="font-semibold text-slate-100">Obstruction sources.</span>{' '}
              Parked two-wheelers, an electrical junction box, and encroaching vendor stalls
              reduce the effective corridor.
            </p>
          </div>
          <div className="flex items-start gap-2">
            <ShieldCheck size={14} className="mt-0.5 shrink-0 text-emerald-400" />
            <p>
              <span className="font-semibold text-slate-100">Remediation status.</span>{' '}
              Flagged to ward engineer on 12 Sep. Re-survey scheduled after 30 days.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

function MapTab() {
  const [layer, setLayer] = useState<MapLayer>('map')
  const [hour, setHour] = useState(12)

  return (
    <div className="absolute inset-0 z-0">
      <div className="absolute inset-0 z-0">
        <StreetSvg layer={layer} />
      </div>

      <div className="absolute top-3 right-3 z-10 flex gap-1 rounded-full bg-slate-900/80 p-1 backdrop-blur-md border border-slate-800">
        <button
          type="button"
          onClick={() => setLayer('nolli')}
          className={`flex items-center gap-1 rounded-full px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
            layer === 'nolli'
              ? 'bg-indigo-500 text-white'
              : 'text-slate-300 hover:text-white'
          }`}
        >
          <Layers size={12} />
          Nolli
        </button>
        <button
          type="button"
          onClick={() => setLayer('map')}
          className={`flex items-center gap-1 rounded-full px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
            layer === 'map'
              ? 'bg-indigo-500 text-white'
              : 'text-slate-300 hover:text-white'
          }`}
        >
          <Map size={12} />
          Map
        </button>
      </div>

      <div className="absolute bottom-0 inset-x-0 z-20 p-4 bg-slate-900/95 backdrop-blur-md border-t border-slate-800 rounded-t-2xl">
        <div className="flex gap-2">
          <MetricCard label="Usable Width" value="94 cm" />
          <MetricCard label="IRC Target" value="180 cm" />
          <MetricCard label="Deficit" value="-86 cm" tone="danger" />
        </div>

        <div className="mt-4 shrink-0">
          <div className="mb-1 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-medium text-slate-300">
              <Sliders size={13} className="text-indigo-400" />
              Time-of-day obstruction
            </span>
            <span className="text-xs font-semibold text-indigo-300">{hour}:00</span>
          </div>
          <input
            type="range"
            min="6"
            max="22"
            step="1"
            value={hour}
            onChange={(e) => setHour(Number(e.target.value))}
            className="w-full accent-indigo-500 cursor-pointer h-2 bg-slate-800 rounded-lg"
          />
          <div className="flex justify-between text-[10px] text-slate-400 mt-1">
            {TIME_MARKS.map((mark) => (
              <span key={mark}>{mark}</span>
            ))}
          </div>
        </div>

        <ComplianceAccordion />
      </div>
    </div>
  )
}

function CaptureTab() {
  const [status, setStatus] = useState<CaptureStatus>('idle')
  const [progress, setProgress] = useState(0)

  const startWalk = () => {
    if (status !== 'idle') return
    setStatus('uploading')
    setProgress(0)

    let value = 0
    const timer = setInterval(() => {
      value += 8 + Math.random() * 10
      if (value >= 100) {
        value = 100
        clearInterval(timer)
        setProgress(100)
        setStatus('done')
        setTimeout(() => {
          setStatus('idle')
          setProgress(0)
        }, 1800)
        return
      }
      setProgress(value)
    }, 180)
  }

  return (
    <div className="relative h-full bg-black flex flex-col justify-between p-6">
      <div className="flex shrink-0 items-start gap-2 rounded-xl bg-slate-900/80 px-3 py-2.5 text-[11px] leading-snug text-slate-200 border border-slate-800">
        <span>🔒</span>
        <span>
          On-Device WASM Anonymization Active — Faces &amp; License Plates blurred locally
          before upload.
        </span>
      </div>

      <div className="relative flex flex-1 items-center justify-center">
        <div className="relative h-64 w-56">
          <div className="absolute inset-0 rounded-lg border-2 border-indigo-400/70" />
          <div className="absolute left-1/2 top-0 h-4 w-px -translate-x-1/2 bg-indigo-400/70" />
          <div className="absolute left-1/2 bottom-0 h-4 w-px -translate-x-1/2 bg-indigo-400/70" />
          <div className="absolute top-1/2 left-0 w-4 h-px -translate-y-1/2 bg-indigo-400/70" />
          <div className="absolute top-1/2 right-0 w-4 h-px -translate-y-1/2 bg-indigo-400/70" />
          <div className="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap text-[10px] font-medium tracking-wide text-indigo-300">
            Frame Path Bounds
          </div>
        </div>
      </div>

      <div className="flex shrink-0 flex-col items-center gap-3">
        {status === 'uploading' && (
          <div className="w-full max-w-[220px]">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full rounded-full bg-indigo-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-1.5 flex items-center justify-center gap-1 text-[11px] text-slate-300">
              <Loader2 size={12} className="animate-spin" />
              Anonymizing &amp; uploading…
            </p>
          </div>
        )}
        {status === 'done' && (
          <p className="flex items-center gap-1.5 text-xs font-medium text-emerald-400">
            <CheckCircle2 size={14} />
            Walk logged successfully
          </p>
        )}

        <button
          type="button"
          onClick={startWalk}
          disabled={status !== 'idle'}
          className="flex h-16 w-16 items-center justify-center rounded-full bg-red-600 shadow-lg shadow-red-600/30 ring-4 ring-red-600/20 disabled:opacity-50 active:scale-95 transition-transform"
          aria-label="Start Pocket Walk"
        >
          <div className="h-6 w-6 rounded-sm bg-white" />
        </button>
        <span className="text-[11px] font-medium text-slate-400">Start Pocket Walk</span>
      </div>
    </div>
  )
}

export default function CitizenUI() {
  const [activeTab, setActiveTab] = useState<Tab>('map')

  return (
    <div className="w-[390px] h-[844px] overflow-hidden relative flex flex-col bg-slate-950 text-slate-100 rounded-[40px] border-[8px] border-slate-800 shadow-2xl">
      <header className="h-14 shrink-0 flex items-center justify-between px-4 border-b border-slate-800 bg-slate-950">
        <div className="flex items-center gap-1.5">
          <MapPin size={16} className="text-indigo-400" />
          <span className="text-sm font-semibold">IC Colony</span>
        </div>
        <div className="flex items-center gap-1 rounded-full bg-red-500/15 border border-red-500/40 px-2.5 py-1">
          <AlertTriangle size={12} className="text-red-400" />
          <span className="text-[10px] font-semibold text-red-400">FAIL: IRC 103</span>
        </div>
      </header>

      <main className="flex-1 relative overflow-hidden">
        {activeTab === 'map' ? <MapTab /> : <CaptureTab />}
      </main>

      <nav className="h-16 z-30 shrink-0 flex justify-around items-center bg-slate-950/90 border-t border-slate-800 backdrop-blur-md">
        <button
          type="button"
          onClick={() => setActiveTab('map')}
          className={`flex flex-col items-center gap-0.5 px-6 py-1.5 ${
            activeTab === 'map' ? 'text-indigo-400' : 'text-slate-500'
          }`}
        >
          <Map size={20} />
          <span className="text-[10px] font-medium">Explore</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('capture')}
          className={`flex flex-col items-center gap-0.5 px-6 py-1.5 ${
            activeTab === 'capture' ? 'text-indigo-400' : 'text-slate-500'
          }`}
        >
          <Camera size={20} />
          <span className="text-[10px] font-medium">Log Walk</span>
        </button>
      </nav>
    </div>
  )
}
