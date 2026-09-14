/**
 * Case switcher, laid out as a macOS Finder sidebar.
 *
 * Showing one case invites the cherry-picking objection and cannot answer it.
 * Every case is reachable here, listed as a "folder" under a Cases disclosure,
 * labelled with its family and its outcome, so a reviewer can go straight to
 * the absent-source cases and watch the system decline to name anyone.
 */

import { useState } from 'react';

const FAMILY_LABEL = {
  decoy: 'nearest vessel is a decoy',
  moving_discharge: 'discharge while under way',
  absent_source: 'source not in the scene',
  crowded: 'crowded traffic',
  along_track_ribbon: 'ribbon laid along track',
};

function FolderIcon({ active }) {
  return (
    <svg className="fico" viewBox="0 0 20 16" aria-hidden="true">
      <path
        d="M1 3.2c0-.9.7-1.6 1.6-1.6h4.1c.5 0 1 .2 1.3.6l.9 1h7.5c.9 0 1.6.7 1.6 1.6v7.4c0 .9-.7 1.6-1.6 1.6H2.6C1.7 15.2 1 14.5 1 13.6V3.2z"
        fill={active ? 'var(--teal)' : 'currentColor'}
        opacity={active ? 0.95 : 0.55}
      />
    </svg>
  );
}

export default function CaseSwitcher({ incidents, active, onSelect }) {
  const [open, setOpen] = useState(true);
  if (!incidents?.length) return null;

  return (
    <nav className="sidebar" aria-label="Incident cases">
      <div className="sidebar-section">
        <button
          type="button"
          className="sidebar-head"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <span className={`disclosure${open ? ' is-open' : ''}`} aria-hidden="true">›</span>
          <span className="sidebar-head-title">Cases</span>
          <span className="sidebar-count">{incidents.length}</span>
        </button>

        {open && (
          <ul className="finder-list">
            {incidents.map((c) => {
              const unknown = c.outcome === 'unknown_source';
              const isActive = c.incident_id === active;
              return (
                <li key={c.incident_id}>
                  <button
                    type="button"
                    className={`finder-row${isActive ? ' is-active' : ''}`}
                    aria-current={isActive ? 'true' : undefined}
                    onClick={() => onSelect(c.incident_id)}
                    title={FAMILY_LABEL[c.family] ?? c.family}
                  >
                    <FolderIcon active={isActive} />
                    <span className="finder-row-body">
                      <span className="finder-row-name">
                        {c.incident_id.replace('case_', 'case ')}
                      </span>
                      <span className="finder-row-sub">
                        {FAMILY_LABEL[c.family] ?? c.family}
                      </span>
                    </span>
                    <span
                      className={`finder-row-dot${unknown ? ' is-unknown' : ''}`}
                      aria-hidden="true"
                    >
                      {unknown ? '◇' : '●'}
                    </span>
                    <span className="visually-hidden">
                      {unknown ? 'unknown source' : 'candidate named'}
                      {` — ${c.n_vessels} vessels tracked`}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </nav>
  );
}
