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

  const badge = unknown
    ? <Badge tone="warning">Unknown source</Badge>
    : <Badge tone="accent">{differs ? 'Nearest vessel not supported' : 'Candidate named'}</Badge>;

  return (
    <Card title="Case Finding" badge={badge} className="finding">
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
            <Stat label="Best fit, not named" value={`mean IoU ${top?.mean_iou.toFixed(3)}`}
                  caption={`Gate ${attribution.abstention_iou_gate}. ${C.fitGate}`} />
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
          ? 'A source vessel may have left the scene before the image. Declining to name one is the correct output here.'
          : 'A ranking reflects physical consistency under tested assumptions: an investigative lead, not proof of responsibility.'}
      </p>
    </Card>
  );
}
