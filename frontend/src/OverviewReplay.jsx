import { useEffect, useRef, useState } from 'react';
import OutcomeIcon from './OutcomeIcon';

/**
 * A case's replay in miniature, drawn from the case's own artifacts - nothing is pre-rendered.
 * Over one loop: every vessel's track draws in across the 24 hours before the image, the leading
 * candidate in blue; from its replayed release its oil drifts (the replay timeline's own particles);
 * at the image the detected slick lights up. A case that names no vessel replays its traffic and
 * slick only. All tiles share one animation frame, pause when hidden, and draw a single still frame
 * under reduced motion.
 */

const LOOP = 9.5;                 // seconds per loop
const RUN = 6.8;                  // of which the -24 h -> image run
const HOLD = 2.2;                 // then the image moment is held
const H_BACK = 24;

// ---- data: fetched once per case, shared across mounts
const cache = new Map();
function load(api, id) {
  if (!cache.has(id)) {
    cache.set(id, Promise.all([api.case(id), api.trackDisplay(id), api.replayTimeline(id)])
      .then(([c, t, r]) => prepare(c, t, r)).catch((e) => { cache.delete(id); throw e; }));
  }
  return cache.get(id);
}

function prepare(c, t, r) {
  const acq = Date.parse(c.meta.acquired_utc);
  const hrs = (iso) => (Date.parse(iso) - acq) / 3600e3;
  const lead = r.named ? r.vessel_key : null;
  const vessels = t.vessels.map((v) => ({
    key: v.vessel_key, lead: v.vessel_key === lead,
    pts: v.display_path.map(([lon, lat, iso]) => [lon, lat, hrs(iso)]).filter((p) => p[2] >= -H_BACK - 1 && p[2] <= 0.01),
  })).filter((v) => v.pts.length > 1);
  const frames = (r.frames ?? []).map((f) => ({ h: -f.hours_before_acquisition, p: f.particles.filter((q) => q[2] !== false) }))
    .sort((a, b) => a.h - b.h);
  // the view: the slick and the replayed oil, padded, so the story is large in a small tile
  const slick = c.slick?.polygon ?? [];
  const xs = [], ys = [];
  for (const [x, y] of slick) { xs.push(x); ys.push(y); }
  for (const f of frames) for (const [x, y] of f.p) { xs.push(x); ys.push(y); }
  for (const v of vessels.filter((u) => u.lead)) for (const [x, y, h] of v.pts) if (h > -8) { xs.push(x); ys.push(y); }
  let box;
  if (xs.length) {
    const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
    const cx = (minx + maxx) / 2, cy = (miny + maxy) / 2, span = Math.max(maxx - minx, maxy - miny, 0.12) * 1.9;
    box = { cx, cy, span };
  } else {
    const b = c.meta.bbox; box = { cx: (b.min_lon + b.max_lon) / 2, cy: (b.min_lat + b.max_lat) / 2, span: b.max_lon - b.min_lon };
  }
  return { vessels, frames, slick, coast: c.geography?.coastline ?? [], areas: c.geography?.sensitive_areas ?? [], box, lead };
}

// ---- one animation frame for every tile on screen
const tiles = new Set();
let raf = 0;
function tick(now) {
  raf = 0;
  if (document.hidden) { schedule(); return; }
  const colors = readColors();
  for (const t of tiles) t(now / 1000, colors);
  schedule();
}
function schedule() { if (!raf && tiles.size) raf = requestAnimationFrame(tick); }

let colorCache = null, colorAt = 0;
function readColors() {
  const now = performance.now();
  if (colorCache && now - colorAt < 1000) return colorCache;
  const s = getComputedStyle(document.documentElement);
  const v = (n, d) => (s.getPropertyValue(n).trim() || d);
  const dark = window.matchMedia('(prefers-color-scheme: dark)').matches
    ? document.documentElement.dataset.theme !== 'light' : document.documentElement.dataset.theme === 'dark';
  colorCache = {
    dark, accent: v('--accent', '#0a84ff'),
    sea0: dark ? '#0b1622' : '#dfe9f2', sea1: dark ? '#132433' : '#eef4f9',
    coast: dark ? 'rgba(235,235,245,0.32)' : 'rgba(60,60,67,0.35)',
    area: dark ? 'rgba(48,209,88,0.10)' : 'rgba(52,199,89,0.12)', areaEdge: dark ? 'rgba(48,209,88,0.35)' : 'rgba(36,138,61,0.35)',
    track: dark ? 'rgba(235,235,245,0.30)' : 'rgba(60,60,67,0.32)', ship: dark ? 'rgba(235,235,245,0.75)' : 'rgba(60,60,67,0.7)',
    slick: dark ? 'rgba(4,8,14,0.62)' : 'rgba(28,32,40,0.30)', slickEdge: dark ? 'rgba(255,255,255,0.9)' : 'rgba(29,29,31,0.75)',
    oil: dark ? 'rgba(255,159,10,0.85)' : 'rgba(201,105,0,0.85)',
  };
  colorAt = now;
  return colorCache;
}

function posAt(pts, h) {
  if (h < pts[0][2]) return null;
  for (let i = 1; i < pts.length; i++) {
    if (pts[i][2] >= h) {
      const [x0, y0, t0] = pts[i - 1], [x1, y1, t1] = pts[i], k = t1 > t0 ? (h - t0) / (t1 - t0) : 1;
      return [x0 + (x1 - x0) * k, y0 + (y1 - y0) * k];
    }
  }
  return pts[pts.length - 1].slice(0, 2);
}

function draw(ctx, w, h, d, hour, C, imageGlow) {
  const { cx, cy, span } = d.box;
  const k = Math.cos((cy * Math.PI) / 180);
  const scale = Math.max(w / (span * k), h / span) * 0.92;
  const X = (lon) => w / 2 + (lon - cx) * k * scale, Y = (lat) => h / 2 - (lat - cy) * scale;
  const g = ctx.createLinearGradient(0, 0, 0, h); g.addColorStop(0, C.sea1); g.addColorStop(1, C.sea0);
  ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
  const poly = (pts, close) => { ctx.beginPath(); pts.forEach(([x, y], i) => (i ? ctx.lineTo(X(x), Y(y)) : ctx.moveTo(X(x), Y(y)))); if (close) ctx.closePath(); };
  for (const a of d.areas) { if (!a.polygon?.length) continue; poly(a.polygon, true); ctx.fillStyle = C.area; ctx.fill(); ctx.strokeStyle = C.areaEdge; ctx.lineWidth = 1; ctx.setLineDash([3, 3]); ctx.stroke(); ctx.setLineDash([]); }
  if (d.coast.length) { poly(d.coast, false); ctx.strokeStyle = C.coast; ctx.lineWidth = 1.2; ctx.stroke(); }
  // the slick: a quiet outline until the image moment, then lit
  if (d.slick.length) {
    poly(d.slick, true); ctx.fillStyle = C.slick; ctx.fill();
    ctx.lineWidth = 1 + imageGlow * 0.6; ctx.strokeStyle = C.slickEdge; ctx.globalAlpha = 0.28 + imageGlow * 0.72;
    if (imageGlow < 0.5) ctx.setLineDash([4, 3]);
    ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
  }
  // tracks so far; the lead last, on top
  const order = [...d.vessels].sort((a, b) => a.lead - b.lead);
  for (const v of order) {
    const seen = v.pts.filter((p) => p[2] <= hour);
    if (seen.length < 1) continue;
    const head = posAt(v.pts, hour);
    ctx.beginPath(); seen.forEach(([x, y], i) => (i ? ctx.lineTo(X(x), Y(y)) : ctx.moveTo(X(x), Y(y))));
    if (head) ctx.lineTo(X(head[0]), Y(head[1]));
    ctx.strokeStyle = v.lead ? C.accent : C.track; ctx.lineWidth = v.lead ? 2.2 : 1;
    if (v.lead) { ctx.shadowColor = C.accent; ctx.shadowBlur = 8; }
    ctx.stroke(); ctx.shadowBlur = 0;
    if (head) {
      ctx.beginPath(); ctx.arc(X(head[0]), Y(head[1]), v.lead ? 3.6 : 2.2, 0, Math.PI * 2);
      ctx.fillStyle = v.lead ? C.accent : C.ship; ctx.fill();
      if (v.lead) { ctx.beginPath(); ctx.arc(X(head[0]), Y(head[1]), 7 + 2 * Math.sin(hour * 3), 0, Math.PI * 2); ctx.strokeStyle = C.accent; ctx.globalAlpha = 0.45; ctx.lineWidth = 1.2; ctx.stroke(); ctx.globalAlpha = 1; }
    }
  }
  // the replayed oil, between its frames
  const F = d.frames;
  if (F.length && hour >= F[0].h) {
    let i = 0; while (i < F.length - 1 && F[i + 1].h <= hour) i++;
    const a = F[i], b = F[Math.min(i + 1, F.length - 1)], t = b.h > a.h ? Math.min(1, (hour - a.h) / (b.h - a.h)) : 0;
    ctx.fillStyle = C.oil;
    const n = Math.min(a.p.length, b.p.length);
    for (let j = 0; j < n; j++) {
      const x = a.p[j][0] + (b.p[j][0] - a.p[j][0]) * t, y = a.p[j][1] + (b.p[j][1] - a.p[j][1]) * t;
      ctx.fillRect(X(x) - 0.9, Y(y) - 0.9, 1.8, 1.8);
    }
  }
}

const hourLabel = (h) => (h > -0.5 ? 'Image' : `−${Math.ceil(-h)} h`);

export default function ReplayTile({ api, row, index, onOpen, active }) {
  const canvas = useRef(null);
  const timeRef = useRef(null);
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const f = row.finding;
  const unknown = f?.unknown_source;

  useEffect(() => {
    let live = true;
    load(api, row.incident_id).then((d) => live && setData(d)).catch(() => live && setFailed(true));
    return () => { live = false; };
  }, [api, row.incident_id]);

  useEffect(() => {
    const el = canvas.current;
    if (!el || !data || !active) return undefined;
    const ctx = el.getContext('2d');
    let lastLabel = '';
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const paint = (sec, C) => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = el.clientWidth, h = el.clientHeight;
      if (!w || !h) return;
      if (el.width !== Math.round(w * dpr) || el.height !== Math.round(h * dpr)) { el.width = Math.round(w * dpr); el.height = Math.round(h * dpr); }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      let hour = 0, glow = 1, fade = 1;
      if (!reduce) {
        const p = (sec + index * 0.38) % LOOP;
        if (p < RUN) { const e = p / RUN; hour = -H_BACK + H_BACK * (1 - (1 - e) ** 1.6); glow = 0; }
        else if (p < RUN + HOLD) { hour = 0; glow = Math.min(1, (p - RUN) / 0.35); }
        else { hour = 0; fade = Math.max(0, 1 - (p - RUN - HOLD) / (LOOP - RUN - HOLD)); }
      }
      ctx.globalAlpha = 1;
      draw(ctx, w, h, data, hour, C, glow);
      if (fade < 1) { ctx.fillStyle = C.sea0; ctx.globalAlpha = 1 - fade; ctx.fillRect(0, 0, w, h); ctx.globalAlpha = 1; }
      const label = hourLabel(hour);
      if (label !== lastLabel && timeRef.current) { timeRef.current.textContent = label; timeRef.current.classList.toggle('is-image', label === 'Image'); lastLabel = label; }
    };
    if (reduce) { paint(0, readColors()); return undefined; }
    tiles.add(paint); schedule();
    return () => { tiles.delete(paint); };
  }, [data, active, index]);

  return (
    <button type="button" className={`ov-tile ov-replay${unknown ? ' is-abstain' : ''}`} style={{ '--k': index }}
            onClick={() => onOpen(row.incident_id)} aria-label={`${row.incident_id.replace('case_', 'Case ')} replay - open case`}>
      <canvas ref={canvas} className="ovr-canvas" aria-hidden="true" />
      {!data && <span className="ovr-wait">{failed ? 'Replay unavailable' : 'Loading replay…'}</span>}
      <span className="ovr-top">
        {f && <OutcomeIcon abstain={unknown} />}
        <span className="ov-id">{row.incident_id.replace('case_', 'Case ')}</span>
        <span ref={timeRef} className="ovr-time">−24 h</span>
      </span>
      <span className="ovr-cap">
        {!f ? 'Not yet analysed'
          : unknown ? 'No vessel named'
            : <>Lead <b className="mono">{f.best.vessel_key}</b>{f.nearest && f.nearest.vessel_key !== f.best.vessel_key ? ' · not the nearest' : ''}</>}
      </span>
      <span className="ov-open">Open case →</span>
    </button>
  );
}
