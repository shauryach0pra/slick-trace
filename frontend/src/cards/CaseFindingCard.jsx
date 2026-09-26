import { Badge, Card } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';
import { FitGauge, HowMeasured } from '../ui/viz';
import './caseFinding.css';

/**
 * Case Finding: who forward replay names and how strongly, at a glance. A hero
 * with the named vessel beside its fit gauge; three facts as tiles; the
 * proximity pick on its own row, set aside where replay does not support it.
 * When the system abstains, it says so as a decision. Every value is a field of
 * attribution_result.json, naive_baseline_result.json or the case's vessels.
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

  return (
    <Card title="Case Finding" badge={badge} className={`finding cf2${unknown ? ' is-abstain' : ''}`}>
      {unknown && (
        // A deliberate outcome, drawn as one - keyed on the system's own output
        // (unknown_source), never on the case's family.
        <div className="abstain-block" role="status">
          <div className="abstain-head">
            <svg className="abstain-mark" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" /><path d="M5.5 10h9" /></svg>
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
                      style={{ left: `${Math.max(0, Math.min(1, r.mean_iou)) * 100}%` }} title={`${r.vessel_key}: mean IoU ${r.mean_iou.toFixed(3)}`} />
              ))}
            </div>
            <div className="gate-scale">
              <span style={{ left: 0 }}>0</span><span className="is-gate" style={{ left: `${gate * 100}%` }}>gate {gate}</span><span style={{ left: '100%' }}>1</span>
            </div>
          </div>
        </div>
      )}

      <div className="cf2-hero">
        <div className="cf2-main">
          <span className="cf2-eyebrow">{unknown ? 'Forward replay' : 'Forward replay names'}</span>
          <span className="cf2-key">{unknown ? 'No vessel named' : top?.vessel_key}</span>
          <span className="cf2-why">{unknown
            ? `The best of ${nCandidates} replayed candidates fits at ${top?.mean_iou.toFixed(2) ?? '—'}, below the gate of ${gate}.`
            : `The best physical fit of ${nCandidates} replayed candidates${runnerUp ? `, ahead of the runner-up at ${runnerUp.mean_iou.toFixed(2)}` : ''}.`}</span>
        </div>
        <FitGauge value={top?.mean_iou ?? 0} gate={gate} secondary={unknown ? null : runnerUp?.mean_iou ?? null}
                  tone={unknown ? 'warning' : 'accent'} size={132} />
      </div>

      {!unknown && (
        <div className="cf2-tiles">
          <div className="cf2-tile">
            <span className="cf2-tile-label">Forcing variants won</span>
            <span className="cf2-tile-big">{wins}<small>/{nVar}</small></span>
            <span className="cf2-pips" aria-hidden="true">{Array.from({ length: nVar }, (_, i) => <i key={i} className={i < wins ? 'is-won' : ''} style={{ '--i': i }} />)}</span>
          </div>
          <div className="cf2-tile">
            <span className="cf2-tile-label">Lead over the runner-up</span>
            <span className="cf2-tile-big">{disc?.loss_gap ?? '—'}</span>
            <span className={`cf2-tile-sub${disc?.discriminated === false ? ' is-warn' : ''}`}>
              {disc?.discriminated === false ? `tied: under ${disc.tolerance}` : 'loss gap, clearly separated'}</span>
          </div>
          <div className="cf2-tile">
            <span className="cf2-tile-label">Inside the origin area</span>
            <span className="cf2-tile-big">{topVessel?.first_entry_hours_before ?? '—'}<small> h</small></span>
            <span className="cf2-tile-sub">before the image</span>
          </div>
        </div>
      )}

      {nearest && (
        <div className={`cf2-naive${differs ? ' is-struck' : ''}`}>
          <span className="cf2-naive-label">Proximity pick</span>
          <span className="cf2-naive-key"><span>{nearest.vessel_key}</span></span>
          <span className="cf2-naive-sub">nearest at image time, about {km} km away{differs ? ' · not supported by forward replay'
            : unknown ? ' · not named either' : ' · also the best physical fit'}</span>
        </div>
      )}

      <p className="cf2-foot">{unknown
        ? 'Declining is the output when no replayed release fits well enough; the source may be outside the data.'
        : 'A lead for an analyst, not proof of responsibility.'}</p>
      <HowMeasured>
        <dl>
          <dt>Proximity pick</dt><dd>{C.distance}</dd>
          <dt>Mean IoU</dt><dd>{C.meanIou}</dd>
          <dt>Fit gate</dt><dd>{C.fitGate}</dd>
          {!unknown && <><dt>Inside the origin area</dt><dd>{C.firstEntry}</dd></>}
          {!unknown && <><dt>Lead over the runner-up</dt><dd>{C.lossGap}</dd></>}
          <dt>Forcing variants</dt><dd>Every release is replayed under six forcing variants; a win is a variant in which this vessel fits best of all candidates.</dd>
        </dl>
      </HowMeasured>
    </Card>
  );
}
