import { useLayoutEffect, useRef, useState } from 'react';
import { FAMILY_LABEL } from './families';

/**
 * Case switcher across the full generated benchmark.
 *
 * Showing one case invites the cherry-picking objection and cannot answer it.
 * Every case is reachable here, labelled with its family and its outcome, so
 * a reviewer can go straight to the absent-source cases and watch the system
 * decline to name anyone.
 *
 * The selection is one element that travels to the active row, as in a macOS
 * source list, rather than each row swapping its own colour. It is measured
 * from the row itself, so it follows any change in row height or font size.
 */


export default function CaseSwitcher({ incidents, active, onSelect }) {
  const wrapRef = useRef(null);
  const rowRefs = useRef({});
  const [box, setBox] = useState(null);
  const [ready, setReady] = useState(false);

  useLayoutEffect(() => {
    const measure = () => {
      const row = rowRefs.current[active];
      // no active row - on the overview, or filtered out of the list: no selection
      if (!row || !wrapRef.current) { setBox(null); return; }
      setBox({ y: row.offsetTop, h: row.offsetHeight });
    };
    measure();
    // Enable the slide only after the first placement, so the selection does
    // not travel in from the top on load.
    const id = requestAnimationFrame(() => setReady(true));
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    if (ro && wrapRef.current) ro.observe(wrapRef.current);
    return () => { cancelAnimationFrame(id); ro?.disconnect(); };
  }, [active, incidents]);

  if (!incidents?.length) return null;

  return (
    <nav className="case-switcher" aria-label="Incident cases">
      <span className="case-switcher-label">
        Cases
      </span>
      <div className="case-list-wrap" ref={wrapRef}>
        <span
          className={`case-highlight${ready && box ? ' is-ready' : ''}`}
          style={box ? { '--y': `${box.y}px`, '--h': `${box.h}px` } : undefined}
          aria-hidden="true"
        />
        <ul className="case-list">
          {incidents.map((c) => {
            const unknown = c.outcome === 'unknown_source';
            const isActive = c.incident_id === active;
            return (
              <li key={c.incident_id}>
                <button
                  ref={(el) => { rowRefs.current[c.incident_id] = el; }}
                  type="button"
                  className={`case-item${isActive ? ' is-active' : ''}`}
                  aria-current={isActive ? 'true' : undefined}
                  onClick={() => onSelect(c.incident_id)}
                >
                  <span
                    className={`case-indicator ${unknown ? 'indicator-unknown' : 'indicator-known'}`}
                    aria-hidden="true"
                  />
                  <span className="case-text">
                    <span className="case-id">{c.incident_id.replace('case_', 'case ')}</span>
                    <span className="case-description">
                      {FAMILY_LABEL[c.family] ?? c.family}
                    </span>
                  </span>
                  <span className="visually-hidden">
                    {unknown ? ', outcome: source not identified' : ', outcome: source identified'}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
