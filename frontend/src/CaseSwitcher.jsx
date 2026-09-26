import { useLayoutEffect, useRef, useState } from 'react';
import { FAMILY_LABEL, FAMILY_SHORT } from './families';
import OutcomeIcon from './OutcomeIcon';
import './caseSwitcher.css';

/**
 * The case list as a macOS source list: grouped by family (what kind of test a
 * case is), each group collapsible; every row shows the system's own outcome -
 * a vessel named, or an abstention - the vessel it named and its fit, from the
 * same /api/overview fields as the overview grid. One selection travels to the
 * active row. The family never says which vessel did it; the outcome is the
 * system's, right or wrong.
 */
const FAMILY_ICON = {
  decoy: <><circle cx="6" cy="8" r="3.2" /><circle cx="11" cy="8" r="3.2" strokeDasharray="1.6 1.4" /></>,
  moving_discharge: <><path d="M2.5 8h9" /><path d="M9 5l3 3-3 3" /><path d="M2.5 11.5q1.5-1 3 0t3 0" /></>,
  absent_source: <circle cx="8" cy="8" r="5" strokeDasharray="2 1.8" />,
  crowded: <><circle cx="5" cy="5.5" r="1.4" /><circle cx="10.5" cy="5" r="1.4" /><circle cx="7.5" cy="10.5" r="1.4" /><circle cx="12" cy="10" r="1.4" /><circle cx="4" cy="10.5" r="1.4" /></>,
  along_track_ribbon: <path d="M2 10q2-5 4 0t4 0 4-3" />,
};

export default function CaseSwitcher({ incidents, active, onSelect, summaries = {} }) {
  const wrapRef = useRef(null);
  const rowRefs = useRef({});
  const [box, setBox] = useState(null);
  const [ready, setReady] = useState(false);
  const [closed, setClosed] = useState({});

  useLayoutEffect(() => {
    const measure = () => {
      const row = rowRefs.current[active];
      // no active row - on the overview, or inside a collapsed group: no selection
      if (!row || !wrapRef.current || row.closest('.sl-group.is-closed')) { setBox(null); return; }
      setBox({ y: row.getBoundingClientRect().top - wrapRef.current.getBoundingClientRect().top, h: row.offsetHeight });
    };
    measure();
    const id = requestAnimationFrame(() => setReady(true));
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    if (ro && wrapRef.current) ro.observe(wrapRef.current);
    // groups animate their height: measure again when that animation ends
    const wrap = wrapRef.current;
    wrap?.addEventListener('transitionend', measure);
    return () => { cancelAnimationFrame(id); ro?.disconnect(); wrap?.removeEventListener('transitionend', measure); };
  }, [active, incidents, closed]);

  if (!incidents?.length) return null;
  const groups = [];
  for (const c of incidents) {
    let g = groups.find((x) => x.family === c.family);
    if (!g) { g = { family: c.family, cases: [] }; groups.push(g); }
    g.cases.push(c);
  }

  return (
    <nav className="case-switcher sl" aria-label="Incident cases">
      <div className="sl-section"><span>Cases</span><span className="sl-count">{incidents.length}</span></div>
      <div className="case-list-wrap sl-wrap" ref={wrapRef}>
        <span className={`case-highlight${ready && box ? ' is-ready' : ''}`}
              style={box ? { '--y': `${box.y}px`, '--h': `${box.h}px` } : undefined} aria-hidden="true" />
        {groups.map((g) => {
          const isClosed = !!closed[g.family];
          return (
            <div key={g.family} className={`sl-group${isClosed ? ' is-closed' : ''}`}>
              <button type="button" className="sl-group-head" aria-expanded={!isClosed}
                      onClick={() => setClosed((s) => ({ ...s, [g.family]: !s[g.family] }))} title={FAMILY_LABEL[g.family] ?? g.family}>
                <svg className="sl-fam" viewBox="0 0 16 16" aria-hidden="true">{FAMILY_ICON[g.family] ?? <circle cx="8" cy="8" r="4" />}</svg>
                <span className="sl-group-name">{FAMILY_SHORT[g.family] ?? g.family}</span>
                {/* the chevron sits just before the count, so every count shares one right edge */}
                <span className="sl-chev" aria-hidden="true" />
                <span className="sl-count">{g.cases.length}</span>
              </button>
              <div className="sl-rows"><ul className="case-list">
                {g.cases.map((c) => {
                  const f = summaries[c.incident_id];
                  const unknown = f ? f.unknown_source : c.outcome === 'unknown_source';
                  const isActive = c.incident_id === active;
                  return (
                    <li key={c.incident_id}>
                      <button ref={(el) => { rowRefs.current[c.incident_id] = el; }} type="button"
                              className={`case-item sl-row${isActive ? ' is-active' : ''}`} aria-current={isActive ? 'true' : undefined}
                              onClick={() => onSelect(c.incident_id)}>
                        <OutcomeIcon abstain={unknown} />
                        <span className="case-text">
                          <span className="case-id">{c.incident_id.replace('case_', 'Case ')}</span>
                          <span className="case-description">{f ? (unknown ? 'No vessel named' : f.best?.vessel_key) : (FAMILY_LABEL[c.family] ?? c.family)}</span>
                        </span>
                        <span className="visually-hidden">{unknown ? ', outcome: no vessel named' : ', outcome: a vessel named'}</span>
                      </button>
                    </li>
                  );
                })}
              </ul></div>
            </div>
          );
        })}
      </div>
      <div className="sl-legend" aria-hidden="true">
        <span><i className="sl-outcome is-named"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" /><path d="M5.2 8.2l2 2 3.8-4.2" /></svg></i>vessel named</span>
        <span><i className="sl-outcome is-abstain"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" /><path d="M4 12L12 4" /></svg></i>abstains</span>
      </div>
    </nav>
  );
}
