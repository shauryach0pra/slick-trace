import { Badge, Card } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';
import { FitGauge, HowMeasured } from '../ui/viz';
import './caseFinding.css';

/**
 * Case Finding, as Apple would say it: the finding as a sentence, beside its fit gauge, then the
 * evidence as a short list of rows, each led by a small symbol - supporting (a check), against (a
 * cross) or a caution. Every value is a field of attribution_result.json,
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
  const fit = top?.mean_iou ?? 0;

  const badge = unknown
    ? <Badge tone="warning">No vessel named</Badge>
    : <Badge tone="accent">{differs ? 'Nearest vessel ruled out' : 'Nearest vessel confirmed'}</Badge>;

  // the evidence, one row each: kind is 'for' (a check), 'against' (a cross) or 'caution'
  const rows = unknown ? [
    { kind: 'caution', text: <>The best fit reaches <b>{fit.toFixed(2)}</b>, short of the <b>{gate}</b> gate by <b>{(gate - fit).toFixed(2)}</b></> },
    { kind: 'caution', text: <>None of the <b>{nCandidates}</b> replayed candidates recreates the slick well enough</> },
    runnerUp && { kind: 'caution', text: <>The next-best candidate fits at only <b>{runnerUp.mean_iou.toFixed(2)}</b></> },
    nearest && { kind: 'against', text: <>The nearest vessel, <b className="mono">{nearest.vessel_key}</b>, {km} km away, isn’t named either</> },
  ] : [
    { kind: 'for', text: <>Best fit under <b>{wins} of {nVar}</b> forcing variants</> },
    disc && (disc.discriminated === false
      ? { kind: 'caution', text: <>Close to the runner-up: loss gap <b>{disc.loss_gap}</b>, within {disc.tolerance}</> }
      : { kind: 'for', text: <>Clearly ahead of the runner-up, with a loss gap of <b>{disc.loss_gap}</b></> }),
    topVessel?.first_entry_hours_before != null && { kind: 'for', text: <>Inside the origin area <b>{topVessel.first_entry_hours_before} h</b> before the image</> },
    nearest && (differs
      ? { kind: 'against', text: <>The nearest vessel, <b className="mono">{nearest.vessel_key}</b>, {km} km away, isn’t supported</> }
      : { kind: 'for', text: <>It is also the nearest vessel, {km} km away</> }),
  ];

  return (
    <Card title="Case Finding" badge={badge} className={`finding cf6${unknown ? ' is-abstain' : ''}`}>
      <div className="cf6-hero">
        <div className="cf6-say">
          <h3 className="cf6-headline">{unknown
            ? <><em>No vessel</em> fits the slick well enough to be named.</>
            : <><em className="mono">{top?.vessel_key}</em> is the best physical fit.</>}</h3>
          <p className="cf6-sub">{unknown
            ? `Forward replay tested ${nCandidates} candidates; the source may not be in the data.`
            : `Forward replay tested ${nCandidates} candidates${runnerUp ? `; the runner-up fits at ${runnerUp.mean_iou.toFixed(2)}` : ''}.`}</p>
        </div>
        <FitGauge value={fit} gate={gate} secondary={unknown ? null : runnerUp?.mean_iou ?? null}
                  tone={unknown ? 'warning' : 'accent'} size={96} />
      </div>

      <ul className="cf6-list">
        {rows.filter(Boolean).map((r, i) => (
          <li key={i} className={`cf6-row is-${r.kind}`} style={{ '--i': i }}>
            <span className="cf6-sym" aria-hidden="true">
              <svg viewBox="0 0 16 16">{r.kind === 'for' ? <path d="M4.6 8.3l2.2 2.2 4.6-4.9" />
                : r.kind === 'against' ? <path d="M5.3 5.3l5.4 5.4M10.7 5.3l-5.4 5.4" />
                : <path d="M8 4.6v4.3M8 11.3v.1" />}</svg>
            </span>
            <span className="cf6-text">{r.text}</span>
          </li>
        ))}
      </ul>

      <HowMeasured>
        <dl>
          <dt>Best physical fit</dt><dd>{C.meanIou}</dd>
          <dt>Fit gate</dt><dd>{C.fitGate}</dd>
          <dt>Forcing variants</dt><dd>Every release is replayed under six forcing variants; a win is a variant in which this vessel fits best of all candidates.</dd>
          {!unknown && <><dt>Loss gap</dt><dd>{C.lossGap}</dd></>}
          {!unknown && <><dt>Origin area</dt><dd>{C.firstEntry}</dd></>}
          <dt>Nearest vessel</dt><dd>{C.distance}</dd>
        </dl>
      </HowMeasured>
    </Card>
  );
}
