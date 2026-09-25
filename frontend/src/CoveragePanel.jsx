import MetricInfo from './MetricInfo';

/**
 * Coverage-aware matching (masterplan p.11).
 *
 * Three named rates at a stated operating point, reported under both selective
 * hiding and simulated coverage failure. An unmatched contact is a contact
 * whose identity is unresolved — never automatically a suspect.
 */
const ROWS = [
  ['hidden_ais_recovery_rate', 'hidden_ais_recovery_n', 'Hidden-AIS recovery', true],
  ['false_unmatched_alert_rate', 'false_unmatched_alert_n', 'False unmatched-alert', false],
  ['mistaken_promotion_rate', 'mistaken_promotion_n', 'Mistaken promotion', false],
];

// A null rate means its denominator was zero: nothing was there to measure.
// Multiplying null by 100 in JavaScript gives 0, which would print a rate of
// 0.0% that no run produced.
function Rate({ value, n }) {
  return (
    <>
      {value == null ? 'not measured' : `${(value * 100).toFixed(1)}%`}{' '}
      <span className="cov-n">({n})</span>
    </>
  );
}

export default function CoveragePanel({ coverage }) {
  if (!coverage) return null;
  const { selective, coverage_failure: failure } = coverage.conditions;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Coverage-Aware Matching</h2>
        <span className="tag tag-teal">Tested</span>
      </div>

      <table className="fc-table">
        <caption className="visually-hidden">
          Matching rates under selective AIS hiding and simulated coverage failure
        </caption>
        <thead>
          <tr>
            <th scope="col">Rate</th>
            <th scope="col">Selective hiding</th>
            <th scope="col">Coverage failure</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map(([rateKey, nKey, label, higherIsBetter]) => (
            <tr key={rateKey}>
              <th scope="row">
                {label}
                {rateKey === 'hidden_ais_recovery_rate' && <MetricInfo metric="hiddenAis" />}
                <span className="visually-hidden">
                  {higherIsBetter ? ' higher is better' : ' lower is better'}
                </span>
              </th>
              <td><Rate value={selective[rateKey]} n={selective[nKey]} /></td>
              <td><Rate value={failure[rateKey]} n={failure[nKey]} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="ranking-caption">
        Operating point: gate {coverage.operating_point.gate_radius_deg}°, detector
        miss {coverage.operating_point.detector_miss_rate}, hidden fraction{' '}
        {coverage.operating_point.hide_fraction_selective}.
      </p>
      <details className="text-equivalent">
        <summary>What these rates do and do not establish</summary>
        <ul className="cov-limits">
          {coverage.limits.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </details>
    </div>
  );
}
