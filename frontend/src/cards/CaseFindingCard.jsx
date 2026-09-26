import { Badge, Card } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';
import { FitGauge, HowMeasured } from '../ui/viz';
import './caseFinding.css';

/**
 * Case Finding, compact: one surface with the named vessel and its fit gauge, the three facts as a
 * slim strip along its foot, and the proximity pick as a quiet line beneath. An abstention uses the
 * same layout in amber. Every value is a field of attribution_result.json,
 * naive_baseline_result.json or the case's vessels.
 */
export default function CaseFindingCard({ attribution, baseline, vessels }) {
  if (!attribution || !baseline) return null;
  const nearest = baseline.ranking[0];
  const top = attribution.ranking[0];
  const runnerUp = attribution.ranking[1];
  const unknown = attribution.unknown_source;
  const nCandidates = attribution.candidates_considered.length;
  const disc = attribution.discrimination;
  const gate = attribution.abstention_iou_gate;
  const topVessel = vessels?.find((v) => v.vessel_key === top?.vessel_key);
  const differs = !unknown && nearest && top && nearest.vessel_key !== top.vessel_key;
  const km = nearest ? (nearest.distance_deg * 111).toFixed(1) : null;
  const wins = top?.ensemble_win_count ?? 0, nVar = top?.n_ensemble ?? 0;

  const badge = unknown
    ? <Badge tone="warning">System abstains</Badge>
    : <Badge tone="accent">{differs ? 'Nearest vessel not supported' : 'Candidate named'}</Badge>;

  const stats = unknown
    ? [
        { label: 'Best fit', value: top?.mean_iou.toFixed(2) ?? '—', sub: 'mean IoU' },
        { label: 'Fit gate', value: String(gate), sub: 'to name a vessel' },
        { label: 'Short by', value: top ? (gate - top.mean_iou).toFixed(2) : '—', sub: `across ${nCandidates} candidates` },
      ]
    : [
        { label: 'Variants won', value: <>{wins}<small>/{nVar}</small></>, pips: true },
        { label: 'Lead over runner-up', value: disc?.loss_gap ?? '—', sub: disc?.discriminated === false ? `tied: under ${disc.tolerance}` : 'loss gap', warn: disc?.discriminated === false },
        { label: 'In the origin area', value: <>{topVessel?.first_entry_hours_before ?? '—'}<small> h</small></>, sub: 'before the image' },
      ];

  return (
    <Card title="Case Finding" badge={badge} className={`finding cf4${unknown ? ' is-abstain' : ''}`}>
      <div className="cf4-surface">
        <div className="cf4-top">
          <div className="cf4-main">
            <span className="cf4-eyebrow">{unknown ? 'The system abstains' : 'Forward replay names'}</span>
            <span className="cf4-key">{unknown ? 'No vessel named' : top?.vessel_key}</span>
            <span className="cf4-line">{unknown
              ? `The best of ${nCandidates} replayed candidates fits at ${top?.mean_iou.toFixed(2) ?? '—'}, below the gate of ${gate}.`
              : `Best physical fit of ${nCandidates} replayed candidates${runnerUp ? `, ahead of the runner-up at ${runnerUp.mean_iou.toFixed(2)}` : ''}.`}</span>
          </div>
          <FitGauge value={top?.mean_iou ?? 0} gate={gate} secondary={unknown ? null : runnerUp?.mean_iou ?? null}
                    tone={unknown ? 'warning' : 'accent'} size={88} />
        </div>
        <div className="cf4-stats">
          {stats.map((st) => (
            <div key={st.label} className="cf4-stat">
              <span className="cf4-stat-label">{st.label}</span>
              <span className="cf4-stat-value">{st.value}</span>
              {st.pips
                ? <span className="cf4-pips" aria-hidden="true">{Array.from({ length: nVar }, (_, i) => <i key={i} className={i < wins ? 'is-won' : ''} style={{ '--i': i }} />)}</span>
                : <span className={`cf4-stat-sub${st.warn ? ' is-warn' : ''}`}>{st.sub}</span>}
            </div>
          ))}
        </div>
      </div>

      {nearest && (
        <p className={`cf4-naive${differs ? ' is-struck' : ''}`}>
          <span className="cf4-naive-label">Proximity pick</span>
          <span className="cf4-naive-key"><span>{nearest.vessel_key}</span></span>
          <span className="cf4-naive-sub">nearest at image time, about {km} km away</span>
          <span className={`cf4-verdict${differs ? '' : unknown ? ' is-neutral' : ' is-agree'}`}>
            {differs ? 'not supported by forward replay' : unknown ? 'not named either' : 'also the best physical fit'}</span>
        </p>
      )}

      <HowMeasured>
        <dl>
          <dt>Proximity pick</dt><dd>{C.distance}</dd>
          <dt>Mean IoU</dt><dd>{C.meanIou}</dd>
          <dt>Fit gate</dt><dd>{C.fitGate}</dd>
          {!unknown && <><dt>In the origin area</dt><dd>{C.firstEntry}</dd></>}
          {!unknown && <><dt>Lead over the runner-up</dt><dd>{C.lossGap}</dd></>}
          <dt>Forcing variants</dt><dd>Every release is replayed under six forcing variants; a win is a variant in which this vessel fits best of all candidates.</dd>
        </dl>
      </HowMeasured>
    </Card>
  );
}
