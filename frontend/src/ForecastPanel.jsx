import MetricInfo from './MetricInfo';

/**
 * Forward response mode (masterplan p.13).
 *
 * Shows modelled exposure and arrival intervals, never guaranteed damage.
 * The forcing mode is displayed verbatim from the server so a reviewer sees
 * that this is a retrospective reanalysis field, not an operational forecast
 * issued from fields available at issuance time.
 */
export default function ForecastPanel({ forecast }) {
  if (!forecast) return null;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Forward exposure</h2>
        <span className="tag tag-amber">modelled</span>
      </div>

      <p className="ranking-caption">
        Issued from {forecast.issued_from_utc} across{' '}
        {forecast.n_ensemble_variants} forcing variants.
      </p>

      <table className="fc-table">
        <caption className="visually-hidden">
          Modelled spread envelope and sensitive-area exposure by forecast horizon
        </caption>
        <thead>
          <tr>
            <th scope="col">Horizon</th>
            <th scope="col">Envelope</th>
            <th scope="col">Shoreline<MetricInfo metric="exposure" /></th>
            <th scope="col">Sensitive areas</th>
          </tr>
        </thead>
        <tbody>
          {forecast.horizons.map((h) => (
            <tr key={h.horizon_hours}>
              <th scope="row">+{h.horizon_hours} h</th>
              <td>{h.envelope_area_km2} km²</td>
              <td>{(h.modelled_shoreline_fraction * 100).toFixed(1)}%</td>
              <td>
                <ul className="fc-areas">
                  {h.sensitive_area_exposure.map((a) => (
                    <li key={a.name} className={a.any_contact ? 'is-contact' : ''}>
                      <span aria-hidden="true">{a.any_contact ? '▲' : '–'}</span>{' '}
                      {a.name}
                      {a.any_contact
                        ? ` — ${(a.modelled_particle_fraction * 100).toFixed(1)}%`
                        : ' — no modelled contact'}
                    </li>
                  ))}
                </ul>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="ranking-caption">{forecast.forcing_mode}</p>
    </div>
  );
}
