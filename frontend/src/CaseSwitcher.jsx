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
  absent_source: 'no observed vessel is the source',
  crowded: 'crowded traffic',
};

export default function CaseSwitcher({ incidents, active, onSelect }) {
  if (!incidents?.length) return null;

  return (
    <nav className="case-switcher" aria-label="Incident cases">
      <span className="case-switcher-label">
        {incidents.length} independently generated cases
      </span>
      <ul className="case-list">
        {incidents.map((c) => {
          const unknown = c.outcome === 'unknown_source';
          const isActive = c.incident_id === active;
          return (
            <li key={c.incident_id}>
              <button
                type="button"
                className={`case-chip${isActive ? ' is-active' : ''}${unknown ? ' is-unknown' : ''}`}
                aria-current={isActive ? 'true' : undefined}
                onClick={() => onSelect(c.incident_id)}
              >
                <span className="case-chip-id">{c.incident_id.replace('case_', 'case ')}</span>
                <span className="case-chip-family">
                  {FAMILY_LABEL[c.family] ?? c.family}
                </span>
                <span className={`case-chip-outcome${unknown ? ' is-unknown' : ''}`}>
                  <span aria-hidden="true">{unknown ? '◇' : '●'}</span>{' '}
                  {unknown ? 'unknown source' : 'candidate named'}
                  <span className="visually-hidden">
                    {` — ${c.n_vessels} vessels tracked`}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
