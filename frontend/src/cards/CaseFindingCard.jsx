import { useEffect, useState } from 'react';
import { Badge, Card } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';
import { HowMeasured } from '../ui/viz';
import { useCountUp } from '../ui/useCountUp';
import { useInView } from '../ui/useInView';
import './caseFinding.css';

/**
 * Case Finding as one designed object, in the manner of a macOS widget: a hero
 * with the answer on the left and Fitness-style rings on the right, then the
 * proximity pick on a slim strip. A named case is blue: the outer ring is the
 * fit, with the gate marked, and the inner ring the forcing variants won. An
 * abstention is amber: the outer ring is the best fit and the inner ring the
 * gate it needed, so the shortfall is visible. Every value is a field of
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
  const wins = top?.ensemble_win_count ?? 0, nVar = top?.n_ensemble ?? 6;
  const fit = top?.mean_iou ?? 0;

  const badge = unknown
    ? <Badge tone="warning">System abstains</Badge>
    : <Badge tone="accent">{differs ? 'Nearest vessel not supported' : 'Candidate named'}</Badge>;

  const rings = unknown
    ? [{ v: fit, label: 'Best fit', value: fit.toFixed(2), tone: 'amber' },
       { v: gate, label: 'Gate to name', value: String(gate), tone: 'sand' }]
    : [{ v: fit, label: 'Fit', value: fit.toFixed(2), sub: `mean IoU · gate ${gate}`, tone: 'blue', mark: gate },
       { v: nVar ? wins / nVar : 0, label: 'Variants won', value: `${wins}/${nVar}`, sub: 'forcing variants', tone: 'teal' }];

  return (
    <Card title="Case Finding" badge={badge} className={`finding cf3${unknown ? ' is-abstain' : ''}`}>
      <div className="cf3-hero">
        <span className="cf3-glow" aria-hidden="true" />
        <div className="cf3-main">
          <span className="cf3-eyebrow">{unknown ? 'The system abstains' : 'Forward replay names'}</span>
          <span className="cf3-key">{unknown ? 'No vessel named' : top?.vessel_key}</span>
          <span className="cf3-line">{unknown
            ? `The best of ${nCandidates} replayed candidates fits at ${fit.toFixed(2)} — short of the ${gate} gate by ${(gate - fit).toFixed(2)}.`
            : `The best physical fit of ${nCandidates} replayed candidates${runnerUp ? `, ahead of the runner-up at ${runnerUp.mean_iou.toFixed(2)}` : ''}.`}</span>
          {!unknown && (
            <span className="cf3-chips">
              {topVessel?.first_entry_hours_before != null && <span className="cf3-chip">Inside the origin area {topVessel.first_entry_hours_before} h before</span>}
              {disc?.discriminated === true && <span className="cf3-chip">Clear of the runner-up · gap {disc.loss_gap}</span>}
              {disc?.discriminated === false && <span className="cf3-chip is-warn">Tied with the runner-up · gap {disc.loss_gap}</span>}
            </span>
          )}
        </div>
        <div className="cf3-side">
          <Rings rings={rings} />
          <div className="cf3-legend">
            {rings.map((r) => (
              <div key={r.label} className={`cf3-leg tone-${r.tone}`}>
                <i />
                <span className="cf3-leg-text"><em>{r.label}</em><b><Count text={r.value} /></b>{r.sub && <small>{r.sub}</small>}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {nearest && (
        <div className={`cf3-strip${differs ? ' is-struck' : ''}`}>
          <svg className="cf3-pin" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="2.4" /><circle cx="8" cy="8" r="5.6" /></svg>
          <span className="cf3-strip-label">Proximity pick</span>
          <span className="cf3-strip-key"><span>{nearest.vessel_key}</span></span>
          <span className="cf3-strip-sub">nearest at image time · about {km} km away</span>
          <span className={`cf3-verdict${differs ? '' : unknown ? ' is-neutral' : ' is-agree'}`}>
            {differs ? 'not supported by forward replay' : unknown ? 'not named either' : 'also the best physical fit'}</span>
        </div>
      )}

      <p className="cf3-foot">{unknown
        ? 'Declining is the output when no replayed release fits well enough; the source may be outside the data.'
        : 'A lead for an analyst, not proof of responsibility.'}</p>
      <HowMeasured>
        <dl>
          <dt>Proximity pick</dt><dd>{C.distance}</dd>
          <dt>Fit (mean IoU)</dt><dd>{C.meanIou}</dd>
          <dt>Fit gate</dt><dd>{C.fitGate}</dd>
          {!unknown && <><dt>Variants won</dt><dd>Every release is replayed under six forcing variants; a win is a variant in which this vessel fits best of all candidates.</dd></>}
          {!unknown && <><dt>Inside the origin area</dt><dd>{C.firstEntry}</dd></>}
          {!unknown && <><dt>Gap to the runner-up</dt><dd>{C.lossGap}</dd></>}
        </dl>
      </HowMeasured>
    </Card>
  );
}

/** Concentric rings, drawn in when they scroll into view; an optional tick marks the gate. */
function Rings({ rings }) {
  const [ref, seen] = useInView();
  const [drawn, setDrawn] = useState(false);
  useEffect(() => { if (!seen) return undefined; const id = requestAnimationFrame(() => setDrawn(true)); return () => cancelAnimationFrame(id); }, [seen]);
  const R = [58, 42];
  return (
    <svg ref={ref} className="cf3-rings" viewBox="-70 -70 140 140" aria-hidden="true">
      <defs>
        <linearGradient id="cf3-blue" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#0a84ff" /><stop offset="1" stopColor="#64d2ff" /></linearGradient>
        <linearGradient id="cf3-teal" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#30b0c7" /><stop offset="1" stopColor="#66e3d0" /></linearGradient>
        <linearGradient id="cf3-amber" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#ff9f0a" /><stop offset="1" stopColor="#ffd60a" /></linearGradient>
        <linearGradient id="cf3-sand" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#a2845e" /><stop offset="1" stopColor="#d4b483" /></linearGradient>
      </defs>
      {rings.map((r, i) => {
        const rad = R[i], c = 2 * Math.PI * rad, f = Math.max(0.004, Math.min(1, r.v));
        const a = (r.mark ?? 0) * 2 * Math.PI - Math.PI / 2;
        return (
          <g key={r.label} className={`cf3-ring tone-${r.tone}`}>
            <circle r={rad} className="cf3-ring-track" />
            <circle r={rad} className="cf3-ring-arc" stroke={`url(#cf3-${r.tone})`} transform="rotate(-90)"
                    strokeDasharray={`${drawn ? c * f : 0} ${c}`} style={{ transitionDelay: `${i * 160}ms` }} />
            {r.mark != null && <line x1={(rad - 9) * Math.cos(a)} y1={(rad - 9) * Math.sin(a)} x2={(rad + 9) * Math.cos(a)} y2={(rad + 9) * Math.sin(a)} className="cf3-mark" />}
          </g>
        );
      })}
    </svg>
  );
}

/** A figure that counts up when seen; fractions like 5/6 count their first part. */
function Count({ text }) {
  const m = String(text).match(/^(\d+(?:\.\d+)?)(.*)$/);
  const [ref, seen] = useInView();
  const decimals = m && m[1].includes('.') ? m[1].split('.')[1].length : 0;
  const n = useCountUp(m ? Number(m[1]) : null, { decimals, duration: 900, run: seen });
  return <span ref={ref}>{m ? <>{n}{m[2]}</> : text}</span>;
}
