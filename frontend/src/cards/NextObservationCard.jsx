import { Badge, Card, EmptyState } from '../ui/primitives';
import { HowMeasured } from '../ui/viz';
import './nextObservation.css';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Next observation: which future image would best separate the two leading
 * explanations. Reads the artifact's own recommended_window rather than
 * re-deriving it. Recommends evidence; it does not task a satellite.
 */
const hhmm = (s) => s.replace('T', ' ').replace(':00+00:00', ' UTC');

// closing: shown as the last card of a case, framed as what to check next
export default function NextObservationCard({ nextObs, closing = false }) {
  const frame = closing ? { eyebrow: 'What to check next', className: 'is-closing' } : {};
  if (!nextObs) return null;
  if (!nextObs.applicable) {
    return (
      <Card title="Next Observation" badge={<Badge>Not applicable here</Badge>} {...frame}>
        <EmptyState>Not applicable for this incident: {nextObs.reason}</EmptyState>
      </Card>
    );
  }
  const rec = nextObs.recommended_window;
  const A = nextObs.hypothesis_a.vessel_key, B = nextObs.hypothesis_b.vessel_key;
  return (
    <Card title="Next Observation" badge={<Badge tone="warning">Advisory only</Badge>} {...frame}
          caption={`When one more image would best tell ${A} and ${B} apart.`}>
      <div className="no">
        <div className="no-hero">
          <span className="no-eyebrow">Recommended window</span>
          <span className="no-big">+{rec.horizon_hours}<small> h</small></span>
          <span className="no-time">{hhmm(rec.valid_utc)}</span>
          <div className="no-pair">
            <span className="no-vs"><b className="mono">{A}</b><em>vs</em><b className="mono">{B}</b></span>
            <span className="no-facts"><b>{Math.round(rec.disagreement_score * 100)}%</b> disagreement · <b>{rec.predicted_overlap_iou.toFixed(2)}</b> overlap</span>
          </div>
        </div>
        <figure className="no-fig">
          <figcaption>How differently the two explanations predict the slick, hours after the image</figcaption>
          <div className="no-bars" role="img"
               aria-label={`Disagreement by window: ${nextObs.windows.map((w) => `plus ${w.horizon_hours} hours ${Math.round(w.disagreement_score * 100)} percent`).join(', ')}; recommended plus ${rec.horizon_hours} hours`}>
            <span className="no-origin" aria-hidden="true"><i />image</span>
            {nextObs.windows.map((w, i) => {
              const on = w.horizon_hours === rec.horizon_hours;
              return (
                <div key={w.horizon_hours} className={`no-col${on ? ' is-on' : ''}`} style={{ '--i': i }}>
                  {on && <span className="no-sat" aria-hidden="true"><svg viewBox="0 0 20 20"><path d="M4 8h4v4H4zM12 8h4v4h-4zM8 9.5h4v1H8z" /><path d="M10 12v4" className="no-beam" /></svg></span>}
                  <span className="no-val">{Math.round(w.disagreement_score * 100)}%</span>
                  <span className="no-track"><i style={{ '--h': w.disagreement_score }} /></span>
                  <span className="no-lab">+{w.horizon_hours} h</span>
                </div>
              );
            })}
          </div>
        </figure>
      </div>
      <p className="no-foot">Recommends which evidence would be most telling; it does not task a satellite.</p>
      <HowMeasured>
        <dl>
          <dt>Recommended window</dt><dd>{C.recommended}</dd>
          <dt>Disagreement</dt><dd>{C.disagreement}</dd>
          <dt>Predicted overlap</dt><dd>{C.overlapIou}</dd>
          <dt>Schedule</dt><dd>{rec.schedule_status}.</dd>
          <dt>What this is and is not</dt><dd>{nextObs.scope_note} {nextObs.method_note}</dd>
        </dl>
      </HowMeasured>
    </Card>
  );
}
