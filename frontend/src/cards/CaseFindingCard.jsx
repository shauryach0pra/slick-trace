import { Badge, Card } from '../ui/primitives';
import { FitGauge, HowMeasured } from '../ui/viz';
import './caseFinding.css';
import { findingHeadline } from '../findingText';
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

  const runnerIou = runnerUp?.mean_iou ?? null;
  const wins = top?.ensemble_win_count ?? 0, nVar = top?.n_ensemble ?? 0;
  return (
    <Card title="Case Finding" badge={badge} className={`finding cf${unknown ? ' is-abstain' : ''}`}>
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
          </div>
        </div>
      )}

      {/* the abstain statement above already says it; the sentence is for a named result */}
      {!unknown && <p className="cf-headline">{findingHeadline({ unknown, nCandidates, differs })}</p>}

      {/* the comparison, as one picture: what proximity picks, then what the physics supports */}
      <div className="cf-hero">
        <div className={`cf-side cf-naive${differs ? ' is-struck' : ''}`}>
          <span className="cf-eyebrow">Proximity pick</span>
          <span className="cf-key"><span>{nearest?.vessel_key}</span></span>
          <span className="cf-sub">nearest when imaged · {nearest?.distance_deg.toFixed(3)}°</span>
          {differs && <span className="cf-verdict">not supported by forward replay</span>}
          {!unknown && !differs && <span className="cf-verdict is-agree">also the best physical fit</span>}
        </div>
        <div className="cf-bridge" aria-hidden="true">
          <span className="cf-bridge-line" /><span className="cf-bridge-label">physics check</span><span className="cf-bridge-line" />
        </div>
        <div className="cf-side cf-replay">
          <FitGauge value={top?.mean_iou ?? 0} gate={gate} secondary={unknown ? null : runnerIou}
                    tone={unknown ? 'warning' : 'accent'} />
          <div className="cf-replay-text">
            <span className="cf-eyebrow">{unknown ? 'Forward replay · best fit' : 'Forward replay names'}</span>
            <span className="cf-key is-lead">{unknown ? 'No vessel' : top?.vessel_key}</span>
            <span className="cf-sub">{unknown
              ? <>best {top?.mean_iou.toFixed(2)} is below the gate of {gate}</>
              : <>gate {gate}{runnerIou != null ? <> · runner-up {runnerIou.toFixed(2)}</> : null}</>}</span>
            {!unknown && nVar > 0 && (
              <span className="cf-pips" aria-label={`best under ${wins} of ${nVar} forcing variants`}>
                {Array.from({ length: nVar }, (_, i) => <i key={i} className={i < wins ? 'is-won' : ''} style={{ '--i': i }} />)}
                <span>best under {wins} of {nVar} forcing variants</span>
              </span>
            )}
          </div>
        </div>
      </div>

      {!unknown && (
        <div className="cf-chips">
          {topVessel?.first_entry_hours_before != null && (
            <span className="cf-chip"><i className="cf-ico is-clock" aria-hidden="true" />Inside the origin area {topVessel.first_entry_hours_before} h before</span>
          )}
          {disc?.discriminated === true && (
            <span className="cf-chip"><i className="cf-ico is-gap" aria-hidden="true" />Clear of the runner-up · gap {disc.loss_gap}</span>
          )}
          {disc?.discriminated === false && (
            <span className="cf-chip is-warn"><i className="cf-ico is-gap" aria-hidden="true" />Tied with the runner-up · gap {disc.loss_gap} under {disc.tolerance}</span>
          )}
        </div>
      )}

      <p className="cf-foot">{unknown
        ? 'Declining is the output when no replayed release fits well enough; the source may be outside the data.'
        : 'A lead for an analyst, not proof of responsibility.'}</p>
      <HowMeasured>
        <dl>
          <dt>Proximity pick</dt><dd>{C.distance}</dd>
          <dt>Mean IoU</dt><dd>{C.meanIou}</dd>
          <dt>Fit gate</dt><dd>{C.fitGate}</dd>
          {!unknown && <><dt>Inside the origin area</dt><dd>{C.firstEntry}</dd></>}
          {!unknown && <><dt>Loss gap</dt><dd>{C.lossGap}</dd></>}
          <dt>Forcing variants</dt><dd>Every release is replayed under six forcing variants; the pips count those in which this vessel fits best of all candidates.</dd>
        </dl>
      </HowMeasured>
    </Card>
  );
}
