import { Badge, Card } from '../ui/primitives';
import { HowMeasured } from '../ui/viz';
import { useCountUp } from '../ui/useCountUp';
import { useInView } from '../ui/useInView';
import './supporting.css';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Coverage-aware matching: how radar contacts and AIS records are paired when
 * some AIS is hidden. An unmatched contact is an unresolved identity, never
 * automatically a suspect. A null rate had nothing to count and says so.
 */
const ROWS = [
  ['hidden_ais_recovery_rate', 'hidden_ais_recovery_n', 'Hidden-AIS recovery'],
  ['false_unmatched_alert_rate', 'false_unmatched_alert_n', 'False unmatched alert'],
  ['mistaken_promotion_rate', 'mistaken_promotion_n', 'Mistaken promotion'],
];

const RATE = {
  // every title on exactly two lines, broken deliberately, so all three line up
  hidden_ais_recovery_rate: { title: 'Hidden AIS recovered', lines: ['Hidden AIS', 'recovered'], better: 'higher' },
  false_unmatched_alert_rate: { title: 'False alerts', lines: ['False', 'alerts'], better: 'lower' },
  mistaken_promotion_rate: { title: 'Mistaken promotions', lines: ['Mistaken', 'promotions'], better: 'lower' },
};

/** A rate under both conditions as two concentric rings: outer, vessels hidden; inner, area goes dark. */
function Rings({ outer, inner, title, lines, better, nOuter, nInner, col = 0, run = false }) {
  const ring = (r, v, cls) => {
    const c = 2 * Math.PI * r;
    return (
      <g className={cls}>
        <circle r={r} className="cv-ring-track" />
        {v == null ? <circle r={r} className="cv-ring-none" /> :
          <circle r={r} className="cv-ring-arc" style={{ stroke: `url(#cv-${cls === 'is-outer' ? 'b' : 'y'}-${title.length})` }}
                  strokeDasharray={`${c * Math.max(0.004, Math.min(1, v))} ${c}`} transform="rotate(-90)" />}
      </g>
    );
  };
  const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
  return (
    <figure className="cv-rate" style={{ '--c': col }}>
      <svg viewBox="-50 -50 100 100" role="img" aria-label={`${title}: vessels hidden ${pct(outer)} (${nOuter}), area goes dark ${pct(inner)} (${nInner}); ${better} is better`}>
        <defs>
          <linearGradient id={`cv-b-${title.length}`} x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#0a84ff" /><stop offset="1" stopColor="#64d2ff" /></linearGradient>
          <linearGradient id={`cv-y-${title.length}`} x1="0" y1="1" x2="1" y2="0"><stop offset="0" stopColor="#ff9f0a" /><stop offset="1" stopColor="#ffd60a" /></linearGradient>
        </defs>
        {ring(40, outer, 'is-outer')}
        {ring(28, inner, 'is-inner')}
      </svg>
      <figcaption>
        <b>{lines ? <>{lines[0]}<br />{lines[1]}</> : title}</b>
        <span className="cv-vals"><i className="is-outer" title={`vessels hidden: ${nOuter}`}><Pct v={outer} run={run} /></i><i className="is-inner" title={`area goes dark: ${nInner}`}><Pct v={inner} run={run} /></i></span>
        <span className={`cv-better is-${better}`}>{better === 'higher' ? '↑' : '↓'} {better} is better</span>
      </figcaption>
    </figure>
  );
}

export default function CoverageCard({ coverage }) {
  // the rings fill when they themselves are on screen - the card's top entering is too early
  const [ringsRef, ringsSeen] = useInView({ threshold: 0.6 });
  if (!coverage) return null;
  const { selective, coverage_failure: failure } = coverage.conditions;
  const op = coverage.operating_point;
  return (
    <Card title="Coverage-Aware Matching" badge={<Badge tone="accent">Synthetic tests</Badge>}
          caption="Matching radar contacts to AIS when some AIS is hidden.">
      <div ref={ringsRef} className={`cv-rings${ringsSeen ? ' is-playing' : ''}`}>
        {ROWS.map(([rk, nk], col) => (
          <Rings key={rk} col={col} run={ringsSeen} title={RATE[rk].title} lines={RATE[rk].lines} better={RATE[rk].better}
                 outer={selective[rk]} inner={failure[rk]} nOuter={selective[nk]} nInner={failure[nk]} />
        ))}
      </div>
      <div className="cv-key">
        <span><i className="is-outer" />outer: vessels hidden</span><span><i className="is-inner" />inner: area goes dark</span>
      </div>
      <HowMeasured>
        <dl>
          <dt>Counts</dt><dd>{ROWS.map(([, nk, label]) => `${label}: vessels hidden ${selective[nk]}, area goes dark ${failure[nk]}`).join('; ')}.</dd>
          <dt>Hidden-AIS recovery</dt><dd>{C.hiddenRecovery}</dd>
          <dt>False unmatched alert</dt><dd>{C.falseAlert}</dd>
          <dt>Mistaken promotion</dt><dd>{C.mistakenPromotion}</dd>
          <dt>Match gate</dt><dd>{C.gateRadius} {op.gate_radius_deg}°.</dd>
          <dt>Not measured</dt><dd>{C.notMeasured}</dd>
          <dt>Operating point</dt><dd>Detector miss rate {op.detector_miss_rate}, hidden fraction {op.hide_fraction_selective}, {selective.n_runs} runs per condition.</dd>
          <dt>What these rates do and do not establish</dt><dd><ul className="cov-limits">{coverage.limits.map((l) => <li key={l}>{l}</li>)}</ul></dd>
        </dl>
      </HowMeasured>
    </Card>
  );
}

/** A percentage that counts up from 0 as the rings fill, once the card is seen. */
function Pct({ v, run }) {
  const n = useCountUp(v == null ? null : Math.round(v * 100), { decimals: 0, duration: 1700, run });
  return <span>{v == null ? '—' : `${n}%`}</span>;
}
