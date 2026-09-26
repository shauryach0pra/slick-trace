import { useEffect, useState } from 'react';
import { FAMILY_LABEL } from './families';
import { findingHeadline } from './findingText';
import './overview.css';

/**
 * Mission control: every case at a glance. Each tile's finding is produced by
 * the same rule as the Case Finding card (findingText.js) from the fields
 * /api/overview copies out of each case's artifacts - nothing is summarised or
 * written here. The family says what kind of test a case is, never which vessel
 * did it; the status dot is the system's own outcome.
 */
export default function Overview({ api, onOpen }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let live = true;
    api.overview().then((r) => live && setRows(r)).catch((e) => live && setError(String(e.message ?? e)));
    return () => { live = false; };
  }, [api]);

  if (error) return <div className="ov"><div className="error-banner">Failed to load the case overview: {error}</div></div>;
  if (!rows) return <div className="ov"><div className="ov-loading">Loading cases…</div></div>;

  const named = rows.filter((r) => r.finding && !r.finding.unknown_source).length;
  const abstained = rows.filter((r) => r.finding?.unknown_source).length;
  return (
    <div className="ov">
      <header className="ov-head">
        <h1>All cases</h1>
        <p>{rows.length} cases · {named} name a vessel · {abstained} {abstained === 1 ? 'abstains' : 'abstain'}</p>
      </header>
      <div className="ov-grid">
        {rows.map((r, i) => {
          const f = r.finding;
          const unknown = f?.unknown_source;
          const differs = f && !unknown && f.nearest && f.best && f.nearest.vessel_key !== f.best.vessel_key;
          return (
            <button type="button" key={r.incident_id} className={`ov-tile${unknown ? ' is-abstain' : ''}`}
                    style={{ '--k': i }} onClick={() => onOpen(r.incident_id)}>
              <span className="ov-top">
                <span className={`ov-dot${unknown ? ' is-abstain' : f ? ' is-named' : ''}`} aria-hidden="true" />
                <span className="ov-id">{r.incident_id.replace('_', ' ')}</span>
                <span className="ov-family">{FAMILY_LABEL[r.family] ?? r.family}</span>
              </span>
              {f ? (
                <>
                  <span className="ov-finding">{findingHeadline({ unknown, nCandidates: f.n_candidates, differs })}</span>
                  <span className="ov-facts">
                    {unknown
                      ? <>best fit <b>{f.best?.mean_iou.toFixed(2) ?? '—'}</b> · below the gate of {f.abstention_iou_gate}</>
                      : <>named <b className="mono">{f.best.vessel_key}</b> · mean IoU {f.best.mean_iou.toFixed(2)}
                          {differs && <> · proximity picked <span className="mono">{f.nearest.vessel_key}</span></>}</>}
                  </span>
                </>
              ) : <span className="ov-finding is-pending">Not yet analysed.</span>}
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
