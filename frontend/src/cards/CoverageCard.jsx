import { Badge, Card } from '../ui/primitives';
import { HowMeasured } from '../ui/viz';
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

// which direction is better for each rate
const BETTER = { hidden_ais_recovery_rate: 'higher', false_unmatched_alert_rate: 'lower', mistaken_promotion_rate: 'lower' };

function Pair({ label, better, rows }) {
  return (
    <div className="cv-pair">
      <div className="cv-pair-head"><b>{label}</b><span className={`cv-better is-${better}`}>{better} is better</span></div>
      {rows.map((r) => (
        <div key={r.name} className={`cv-bar-row tone-${r.tone}`}>
          <span className="cv-name">{r.name}</span>
          <span className="cv-track">{r.value == null
            ? <i className="cv-none">not measured</i>
            : <i className="cv-fill" style={{ '--w': r.value }} />}</span>
          <span className="cv-val">{r.value == null ? '—' : `${Math.round(r.value * 100)}%`}<em>{r.n}</em></span>
        </div>
      ))}
    </div>
  );
}

export default function CoverageCard({ coverage }) {
  if (!coverage) return null;
  const { selective, coverage_failure: failure } = coverage.conditions;
  const op = coverage.operating_point;
  return (
    <Card title="Coverage-Aware Matching" badge={<Badge tone="accent">tested</Badge>}
          caption="Matching radar contacts to AIS when some AIS is hidden.">
      <div className="cv-key">
        <span><i className="tone-a" />vessels hidden</span><span><i className="tone-b" />area goes dark</span>
      </div>
      {ROWS.map(([rk, nk, label]) => (
        <Pair key={rk} label={label} better={BETTER[rk]}
              rows={[{ name: 'vessels hidden', tone: 'a', value: selective[rk], n: selective[nk] },
                     { name: 'area goes dark', tone: 'b', value: failure[rk], n: failure[nk] }]} />
      ))}
      <HowMeasured>
        <dl>
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
