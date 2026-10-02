import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { FAMILY_LABEL, FAMILY_STORY } from './families';
import OutcomeIcon from './OutcomeIcon';
import ReplayTile from './OverviewReplay';
import { LOOP_S } from './replayPlay';
import ArchitecturePanel from './OverviewArchitecture';
import './overview.css';

// the overview's three views: every case as text, every case replayed, and how the system works
const VIEWS = [
  { value: 'replays', label: 'Replays' },
  { value: 'cases', label: 'Cases' },
  { value: 'architecture', label: 'Architecture' },
];
const VIEW_KEY = 'slicktrace-overview-view';
function readView() {
  try { const v = sessionStorage.getItem(VIEW_KEY); return VIEWS.some((o) => o.value === v) ? v : VIEWS[0].value; } catch { return VIEWS[0].value; }
}

/**
 * Fit each Cases tile's text to the tile: the outcome always shows whole, and the context gets as many
 * whole lines as the space left over allows - never a half-visible line. Re-measured on every resize,
 * since the room depends on both the tile's height and its width.
 */
function useFitStories(grid, active) {
  useLayoutEffect(() => {
    const el = grid.current;
    if (!el || !active) return undefined;
    const fit = () => {
      for (const t of el.querySelectorAll('.ov-tile')) {
        const ctx = t.querySelector('.ov-ctx'), out = t.querySelector('.ov-out'), top = t.querySelector('.ov-top');
        if (!ctx || !out || !top) continue;
        const cs = getComputedStyle(t), lh = parseFloat(getComputedStyle(ctx).lineHeight) || 20;
        const room = t.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom)
          - top.offsetHeight - parseFloat(cs.rowGap || cs.gap || 8) - out.offsetHeight - 14;
        ctx.style.setProperty('--ctx-lines', String(Math.max(1, Math.floor(room / lh))));
      }
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  });
}

/** A macOS segmented control - the same recessed track and sliding raised thumb as the appearance control. */
function ViewSwitch({ value, onChange }) {
  const i = Math.max(0, VIEWS.findIndex((o) => o.value === value));
  const move = (d) => onChange(VIEWS[(i + d + VIEWS.length) % VIEWS.length].value);
  return (
    <div className="ov-switch" role="radiogroup" aria-label="Overview view" style={{ '--i': i, '--n': VIEWS.length }}
         onKeyDown={(e) => { if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); move(1); } if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); move(-1); } }}>
      <span className="ov-switch-thumb" aria-hidden="true" />
      {VIEWS.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={o.value === value} tabIndex={o.value === value ? 0 : -1}
                className="ov-switch-seg" onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

/**
 * Mission control: every case at a glance. Each tile's finding is produced by
 * the same rule as the Case Finding card (findingText.js) from the fields
 * /api/overview copies out of each case's artifacts - nothing is summarised or
 * written here. The family says what kind of test a case is, never which vessel
 * did it; the status dot is the system's own outcome.
 */
/**
 * One paragraph per case: what the case tests (its family's design), this case's
 * own facts - vessels tracked and replayed, the nearest vessel at image time and
 * how far - and then what forward replay concluded. Every figure is a field of
 * /api/overview; the distance uses 0.01° ≈ 1.1 km, as the app states elsewhere.
 */
function caseStory(r) {
  const f = r.finding;
  const design = FAMILY_STORY[r.family] ?? FAMILY_LABEL[r.family] ?? '';
  if (!f) return { context: design, outcome: ' Not yet analysed.' };
  const km = f.nearest ? (f.nearest.distance_deg * 111).toFixed(1) : null;
  const facts = ` Here, ${r.n_vessels} vessels were tracked and ${f.n_candidates} were replayed`
    + (f.nearest ? `; the nearest at image time was ${f.nearest.vessel_key}, about ${km} km away.` : '.');
  const b = f.best;
  let outcome;
  if (f.unknown_source) {
    outcome = ` No vessel was named: the best fit, ${b ? b.mean_iou.toFixed(2) : '—'}, is below the ${f.abstention_iou_gate} gate.`;
  } else {
    const how = `(fit ${b.mean_iou.toFixed(2)}, best under ${b.ensemble_win_count} of ${b.n_ensemble} forcing variants)`;
    outcome = f.nearest && f.nearest.vessel_key !== b.vessel_key
      ? ` Forward replay named ${b.vessel_key} ${how}, not the nearest vessel.`
      : ` Forward replay named ${b.vessel_key} ${how}, which was also the nearest vessel.`;
  }
  // the context can shorten to fit a small tile; the outcome always shows in full
  return { context: design + facts, outcome };
}

/**
 * The replays' one time base: seconds into the loop, advanced every frame (as the case page's Play is),
 * so the maps move as smoothly as they do there. Each tile turns it into its own hour. Under reduced
 * motion it is null, and every tile rests on its image.
 */
function useReplayLoop(active) {
  const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const [sec, setSec] = useState(reduce ? null : 0);
  useEffect(() => {
    if (!active || reduce) return undefined;
    let raf = 0;
    const start = performance.now();
    const step = (now) => { setSec(((now - start) / 1000) % LOOP_S); raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [active, reduce]);
  return sec;
}

export default function Overview({ api, onOpen, family = 'all', chips = null }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [view, setViewState] = useState(readView);
  const gridRef = useRef(null);
  const clock = useReplayLoop(view === 'replays');
  const [mapMode, setMapMode] = useState(null);
  useFitStories(gridRef, rows && view === 'cases');
  const setView = (v) => { setViewState(v); try { sessionStorage.setItem(VIEW_KEY, v); } catch { /* private mode */ } };
  useEffect(() => {
    let live = true;
    api.overview().then((r) => live && setRows(r)).catch((e) => live && setError(String(e.message ?? e)));
    return () => { live = false; };
  }, [api]);

  if (error) return <div className="ov"><div className="error-banner">Failed to load the case overview: {error}</div></div>;
  if (!rows) return <div className="ov"><div className="ov-loading">Loading cases…</div></div>;

  const shown = family === 'all' ? rows : rows.filter((r) => r.family === family);
  const named = shown.filter((r) => r.finding && !r.finding.unknown_source).length;
  const abstained = shown.filter((r) => r.finding?.unknown_source).length;
  const sub = view === 'architecture' ? 'From a satellite image to a ranked, evidenced lead'
    : `${shown.length === rows.length ? `${rows.length} cases` : `${shown.length} of ${rows.length} cases`} · ${named} ${named === 1 ? 'names' : 'name'} a vessel · ${abstained} ${abstained === 1 ? 'abstains' : 'abstain'}`
      + (view === 'replays' ? ' · each replayed at 1x from 24 h before to 24 h after the image' : '');
  return (
    <div className={`ov is-${view}`}>
      <header className="ov-head">
        <div className="ov-titles">
          <h1>{view === 'architecture' ? 'How it works' : 'All cases'}</h1>
          <p>{sub}</p>
        </div>
        <ViewSwitch value={view} onChange={setView} />
      </header>
      {view !== 'architecture' && (
        <div className="ov-bar">
          {chips}
        </div>
      )}
      <div className="ov-stage">
        {view === 'architecture' ? <ArchitecturePanel /> : (
          <div className="ov-grid" ref={gridRef}>
            {shown.map((r, i) => {
              if (view === 'replays') return <ReplayTile key={r.incident_id} api={api} row={r} index={i} clock={clock} onOpen={onOpen} onMode={i === 0 ? setMapMode : undefined} />;
              const f = r.finding;
              const unknown = f?.unknown_source;
              return (
                <button type="button" key={r.incident_id} className={`ov-tile${unknown ? ' is-abstain' : ''}`}
                        style={{ '--k': i }} onClick={() => onOpen(r.incident_id)}>
                  <span className="ov-top">
                    {f && <OutcomeIcon abstain={unknown} />}
                    <span className="ov-id">{r.incident_id.replace('case_', 'Case ')}</span>
                  </span>
                  {/* the scenario, this case's facts and what happened, in one paragraph */}
                  {(() => { const st = caseStory(r); return (
                    <span className="ov-story"><span className="ov-ctx">{st.context}</span><span className="ov-out">{st.outcome}</span></span>
                  ); })()}
                  <span className="ov-open">Open case →</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
      <p className="ov-foot">Findings are physical consistency under tested assumptions: investigative leads, not proof of
        responsibility. Every case is synthetic.
        {view === 'replays' && mapMode === 'imagery' && <span className="ov-credit"> Basemap: Powered by Esri | Esri, Maxar, Earthstar Geographics, and the GIS User Community.</span>}</p>
    </div>
  );
}
