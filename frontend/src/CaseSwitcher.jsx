/**
 * Case switcher across the full generated benchmark.
 *
 * Showing one case invites the cherry-picking objection and cannot answer it.
 * Every case is reachable here, labelled with its family and its outcome, so
 * a reviewer can go straight to the absent-source cases and watch the system
 * decline to name anyone.
 */

const FAMILY_LABEL = {
  decoy: 'nearest vessel is a decoy',
  moving_discharge: 'discharge while under way',
  absent_source: 'source not in the scene',
  crowded: 'crowded traffic',
  along_track_ribbon: 'ribbon laid along track',
};

export default function CaseSwitcher({ incidents, active, onSelect }) {
  if (!incidents?.length) return null;

  return (
    <nav className="case-switcher" aria-label="Incident cases">
      <span className="case-switcher-label">
        Cases
      </span>
      <ul className="case-list">
        {incidents.map((c) => {
          const unknown = c.outcome === 'unknown_source';
          const isActive = c.incident_id === active;
          return (
            <li key={c.incident_id}>
              <button
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
    </nav>
  );
}
