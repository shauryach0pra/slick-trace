import { Badge, Card, EmptyState, Stat, StatGrid } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Next observation: which future image would best separate the two leading
 * explanations. Reads the artifact's own recommended_window rather than
 * re-deriving it. Recommends evidence; it does not task a satellite.
 */
const hhmm = (s) => s.replace('T', ' ').replace(':00+00:00', ' UTC');

export default function NextObservationCard({ nextObs }) {
  if (!nextObs) return null;
  if (!nextObs.applicable) {
    return (
      <Card title="Next Observation" badge={<Badge>not applicable</Badge>}>
        <EmptyState>Not applicable for this incident: {nextObs.reason}</EmptyState>
      </Card>
    );
  }
  const rec = nextObs.recommended_window;
  return (
    <Card title="Next Observation" badge={<Badge tone="warning">advisory</Badge>}
          caption={`When one more image would best tell ${nextObs.hypothesis_a.vessel_key} and ${nextObs.hypothesis_b.vessel_key} apart.`}
          footnote={`${rec.schedule_status}. ${nextObs.scope_note} ${nextObs.method_note}`}>
      <StatGrid cols={3}>
        <Stat label="Recommended window" value={`+${rec.horizon_hours} h`}
              caption={`${hhmm(rec.valid_utc)}. ${C.recommended}`} />
        <Stat label="Disagreement then" value={`${Math.round(rec.disagreement_score * 100)}%`}
              caption={C.disagreement} />
        <Stat label="Predicted overlap then" value={rec.predicted_overlap_iou.toFixed(3)}
              caption={C.overlapIou} />
      </StatGrid>
      <div style={{ marginTop: 'var(--space-5)' }}>
        <div className="stat-label">Every tested window</div>
        <div className="chip-steps" role="list" style={{ marginTop: 'var(--space-2)' }}>
          {nextObs.windows.map((w) => (
            <span key={w.horizon_hours} role="listitem"
                  className={`chip${w.horizon_hours === rec.horizon_hours ? ' is-active' : ''}`}>
              +{w.horizon_hours} h · {Math.round(w.disagreement_score * 100)}%
              <span className="visually-hidden">{w.horizon_hours === rec.horizon_hours ? ' recommended' : ''}</span>
            </span>
          ))}
        </div>
        <p className="stat-caption">Hours after the image, with the disagreement at each; the recommended one is filled.</p>
      </div>
    </Card>
  );
}
