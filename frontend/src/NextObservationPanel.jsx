import MetricInfo from './MetricInfo';

/**
 * Next-observation advisor (masterplan p.12).
 *
 * Ranks future windows by how much the top two hypotheses disagree. The
 * interface recommends evidence; it does not claim to task satellites, and
 * every window carries its schedule status verbatim from the server.
 */
export default function NextObservationPanel({ nextObs }) {
  if (!nextObs) return null;

  if (!nextObs.applicable) {
    return (
      <div className="panel">
        <div className="panel-head"><h2>Next observation</h2></div>
        <p className="empty-state">
          Not applicable for this incident: {nextObs.reason ?? 'no competing hypothesis pair'}
        </p>
      </div>
    );
  }

  const best = nextObs.windows.reduce(
    (a, b) => (b.disagreement_score > a.disagreement_score ? b : a),
    nextObs.windows[0],
  );

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Next observation</h2>
        <span className="tag tag-amber">hypothetical</span>
      </div>

      <p className="frag-headline">
        Separating <strong>{nextObs.hypothesis_a.vessel_key}</strong> from{' '}
        <strong>{nextObs.hypothesis_b.vessel_key}</strong> — current IoU gap{' '}
        {nextObs.current_ambiguity.mean_iou_gap.toFixed(3)}
        <MetricInfo metric="disagreement" />
      </p>

      <div className="frag-steps" role="list">
        {nextObs.windows.map((w) => (
          <span
            key={w.horizon_hours}
            role="listitem"
            className={`frag-step${w === best ? ' is-active' : ''}`}
          >
            +{w.horizon_hours} h — {(w.disagreement_score * 100).toFixed(0)}%
            {w === best && <span aria-hidden="true"> ★</span>}
            <span className="visually-hidden">
              {w === best ? ' most discriminating window' : ''}
            </span>
          </span>
        ))}
      </div>

      <p className="frag-outcome">
        Most discriminating tested window is <strong>+{best.horizon_hours} h</strong>{' '}
        ({best.valid_utc}), where the two hypotheses overlap at IoU{' '}
        {best.predicted_overlap_iou.toFixed(3)}.
      </p>

      <p className="ranking-caption">
        {best.schedule_status}. This recommends where evidence would be most
        informative; it does not task an acquisition.
      </p>
    </div>
  );
}
