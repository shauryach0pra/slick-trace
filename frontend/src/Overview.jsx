import { useEffect, useState } from 'react';
import { FAMILY_LABEL, FAMILY_STORY } from './families';
import OutcomeIcon from './OutcomeIcon';
import './overview.css';

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
  if (!f) return `${design} Not yet analysed.`;
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
  return design + facts + outcome;
}

export default function Overview({ api, onOpen, family = 'all', chips = null }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
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
  return (
    <div className="ov">
      <header className="ov-head">
        <h1>All cases</h1>
        <p>{shown.length === rows.length ? `${rows.length} cases` : `${shown.length} of ${rows.length} cases`} · {named} {named === 1 ? 'names' : 'name'} a vessel · {abstained} {abstained === 1 ? 'abstains' : 'abstain'}</p>
      </header>
      {chips}
      <div className="ov-grid">
        {shown.map((r, i) => {
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
              <span className="ov-story">{caseStory(r)}</span>
              <span className="ov-open">Open case →</span>
            </button>
          );
        })}
      </div>
      <p className="ov-foot">Findings are physical consistency under tested assumptions: investigative leads, not proof of
        responsibility. Every case is synthetic.</p>
    </div>
  );
}
