import { Badge, BarList, CaptionList, Card, EmptyState } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * One ranked list, parameterized by kind:
 *   "baseline"  proximity to the slick at image time, every vessel (lower = nearer)
 *   "replay"    forward-replay mean IoU, candidates only (higher = better fit),
 *               with the fit gate drawn on every bar
 *
 * The badges say how the two relate, never "right" or "wrong": the interface
 * has no ground truth to judge either.
 */
export default function CandidateRankingCard({ kind, attribution, baseline }) {
  if (kind === 'baseline') {
    if (!baseline) return null;
    const relation = !attribution ? null
      : attribution.unknown_source ? 'forward replay names no one'
        : baseline.top_candidate_id === attribution.top_candidate_id
          ? 'agrees with forward replay' : 'disagrees with forward replay';
    return (
      <Card title="Proximity Baseline"
            badge={relation && <Badge>{relation}</Badge>}
            caption={C.baselineMethod}>
        <BarList label="Distance from each vessel to the slick at image time"
                 rows={baseline.ranking.map((r) => ({ key: r.vessel_key, value: r.distance_deg }))}
                 format={(v) => `${v.toFixed(3)}°`} highlightKey={baseline.top_candidate_id} />
        <p className="card-foot">{C.distance} Shorter bar is nearer; the nearest is highlighted.</p>
      </Card>
    );
  }

  if (!attribution) return null;
  const unknown = attribution.unknown_source;
  return (
    <Card title="Forward-Replay Ranking"
          badge={<Badge tone={unknown ? 'warning' : 'accent'}>{unknown ? 'abstained' : 'named'}</Badge>}
          caption={C.replayMethod}>
      {attribution.ranking.length === 0 ? (
        <EmptyState>No candidate survived historical filtering, so none was replayed.</EmptyState>
      ) : (
        <BarList label="Mean IoU of each candidate's best replayed release"
                 rows={attribution.ranking.map((r) => ({
                   key: r.vessel_key, value: r.mean_iou,
                   sub: `${r.ensemble_win_count}/${r.n_ensemble}`,
                 }))}
                 max={1} format={(v) => v.toFixed(3)}
                 marker={{ value: attribution.abstention_iou_gate, label: `fit gate ${attribution.abstention_iou_gate}` }}
                 highlightKey={unknown ? null : attribution.top_candidate_id} />
      )}
      <CaptionList items={[
        ['Bar: mean IoU', C.meanIou],
        [`Tick: fit gate ${attribution.abstention_iou_gate}`, C.fitGate],
        [`n/${attribution.n_ensemble_variants}`, C.variants],
      ]} />
    </Card>
  );
}
