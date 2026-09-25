import { Badge, Card, CaptionList } from '../ui/primitives';
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

function Rate({ value, n }) {
  return (
    <>
      {value == null ? <span className="muted">not measured</span> : `${(value * 100).toFixed(1)}%`}
      <span className="sub">{n}</span>
    </>
  );
}

export default function CoverageCard({ coverage }) {
  if (!coverage) return null;
  const { selective, coverage_failure: failure } = coverage.conditions;
  const op = coverage.operating_point;
  return (
    <Card title="Coverage-Aware Matching" badge={<Badge tone="accent">tested</Badge>}
          caption="How well radar contacts are matched to AIS records when some AIS is deliberately hidden, one vessel at a time or a whole area at once."
          footnote={`Operating point: match gate ${op.gate_radius_deg}°, detector miss rate ${op.detector_miss_rate}, hidden fraction ${op.hide_fraction_selective}, ${selective.n_runs} runs per condition.`}>
      <table className="ui-table">
        <caption className="visually-hidden">Matching rates under selective hiding and simulated coverage failure</caption>
        <thead>
          <tr><th scope="col">Rate</th><th scope="col">Vessels hidden</th><th scope="col">Area goes dark</th></tr>
        </thead>
        <tbody>
          {ROWS.map(([rk, nk, label]) => (
            <tr key={rk}>
              <th scope="row">{label}</th>
              <td><Rate value={selective[rk]} n={selective[nk]} /></td>
              <td><Rate value={failure[rk]} n={failure[nk]} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <CaptionList items={[
        ['Hidden-AIS recovery', C.hiddenRecovery],
        ['False unmatched alert', C.falseAlert],
        ['Mistaken promotion', C.mistakenPromotion],
        ['Match gate', C.gateRadius],
        ['Not measured', C.notMeasured],
      ]} />
      <details className="text-equivalent">
        <summary>What these rates do and do not establish</summary>
        <ul className="cov-limits">{coverage.limits.map((l) => <li key={l}>{l}</li>)}</ul>
      </details>
    </Card>
  );
}
