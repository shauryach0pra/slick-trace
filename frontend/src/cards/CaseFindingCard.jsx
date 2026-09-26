import { Badge, Card, Stat } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * The finding, stated before the evidence.
 *
 * Wording stays neutral: the proximity pick is "not supported by forward
 * replay", never "wrong" or struck through, because the interface has no
 * ground truth to call anything wrong. On an abstention it says so plainly.
 */
export default function CaseFindingCard({ attribution, baseline, vessels }) {
  if (!attribution || !baseline) return null;

  const nearest = baseline.ranking[0];
  const top = attribution.ranking[0];
  const runnerUp = attribution.ranking[1];
  const unknown = attribution.unknown_source;
  const nCandidates = attribution.candidates_considered.length;
  const disc = attribution.discrimination;
  const topVessel = vessels?.find((v) => v.vessel_key === top?.vessel_key);
  const differs = !unknown && nearest && top && nearest.vessel_key !== top.vessel_key;

  const gate = attribution.abstention_iou_gate;
  const badge = unknown
    ? <Badge tone="warning">System abstains</Badge>
    : <Badge tone="accent">{differs ? 'Nearest vessel not supported' : 'Candidate named'}</Badge>;

  return (
    <Card title="Case Finding" badge={badge} className={`finding${unknown ? ' is-abstain' : ''}`}>
      {unknown && (
        // A deliberate outcome, drawn as one: the statement, and every candidate's fit
        // against the gate, so it is visible that none reaches it. Keyed on the
        // system's own output (unknown_source), never on the case's family.
        <div className="abstain-block" role="status">
          <div className="abstain-head">
            <svg className="abstain-mark" viewBox="0 0 20 20" aria-hidden="true">
              <circle cx="10" cy="10" r="8" /><path d="M5.5 10h9" />
            </svg>
            <span>
              <strong>The system abstains</strong>
              <em>No candidate's replayed release meets the fit gate, so no vessel is named.</em>
            </span>
          </div>
          <div className="gate-meter" aria-label={`Mean IoU of each replayed candidate against the fit gate of ${gate}`}>
            <div className="gate-track">
              <span className="gate-zone" style={{ left: `${gate * 100}%` }}><i>would be named</i></span>
              <span className="gate-tick" style={{ left: `${gate * 100}%` }} />
              {attribution.ranking.map((r) => (
                <span key={r.vessel_key} className={`gate-dot${r === top ? ' is-best' : ''}`}
                      style={{ left: `${Math.max(0, Math.min(1, r.mean_iou)) * 100}%` }}
                      title={`${r.vessel_key}: mean IoU ${r.mean_iou.toFixed(3)}`} />
              ))}
            </div>
            <div className="gate-scale">
              <span style={{ left: 0 }}>0</span>
              <span className="is-gate" style={{ left: `${gate * 100}%` }}>gate {gate}</span>
              <span style={{ left: '100%' }}>1</span>
            </div>
            <p className="gate-caption">
              {attribution.ranking.length} candidate{attribution.ranking.length === 1 ? '' : 's'} replayed; the best reaches a
              mean IoU of {top?.mean_iou.toFixed(3) ?? '—'}.
            </p>
          </div>
        </div>
      )}
      <p className="finding-line">
        {unknown
          ? `No vessel is named. Forward replay tested ${nCandidates} candidate vessel${nCandidates === 1 ? '' : 's'}, and none fit the observed slick well enough to reach the gate.`
          : differs
            ? 'The nearest vessel is not supported by forward replay; the best physical fit is another vessel.'
            : 'The nearest vessel is also the best physical fit under forward replay.'}
      </p>

      <div className="finding-compare">
        <div className={`finding-side${differs || unknown ? ' is-muted' : ''}`}>
          <div className="finding-side-label">Proximity baseline picks</div>
          <Stat mono label="Nearest at image time" value={nearest?.vessel_key}
                caption={`${nearest?.distance_deg.toFixed(3)}° from the slick. ${C.distance}`} />
        </div>
        <span className="finding-arrow" aria-hidden="true">→</span>
        <div className="finding-side">
          <div className="finding-side-label">Forward replay</div>
          {unknown ? (
            <Stat label="No vessel named" value={`best fit ${top?.mean_iou.toFixed(3) ?? '—'}`}
                  caption={`Below the gate of ${gate}. ${C.fitGate}`} />
          ) : (
            <Stat mono label="Best physical fit" value={top?.vessel_key}
                  caption={`Mean IoU ${top?.mean_iou.toFixed(3)}${runnerUp ? ` against ${runnerUp.mean_iou.toFixed(3)} for the runner-up` : ''}. ${C.meanIou}`} />
          )}
        </div>
      </div>

      {!unknown && topVessel?.first_entry_hours_before != null && (
        <p className="card-caption" style={{ marginTop: 'var(--space-3)', marginBottom: 0 }}>
          Inside the origin area {topVessel.first_entry_hours_before} h before the image. {C.firstEntry}
        </p>
      )}
      {!unknown && disc?.discriminated === false && (
        <p className="card-caption" style={{ marginTop: 'var(--space-2)', marginBottom: 0 }}>
          The top two are not separated: loss gap {disc.loss_gap}, under {disc.tolerance}. {C.lossGap}
        </p>
      )}

      <p className="finding-note">
        {unknown
          ? 'Declining is what the system does when no candidate’s replayed release fits the slick well enough. The source may be outside the data — for example, a vessel that left the scene before the image.'
          : 'A ranking reflects physical consistency under tested assumptions: an investigative lead, not proof of responsibility.'}
      </p>
    </Card>
  );
}
