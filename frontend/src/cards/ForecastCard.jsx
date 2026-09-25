import { Badge, Card, CaptionList } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Forward exposure: where modelled surface particles go after the image.
 * Modelled exposure and arrival intervals, never predicted damage; the
 * forcing mode is shown verbatim so a retrospective field is not mistaken
 * for an operational forecast.
 */
const hhmm = (s) => s.replace('T', ' ').replace(':00+00:00', ' UTC');

export default function ForecastCard({ forecast }) {
  if (!forecast) return null;
  return (
    <Card title="Forward Exposure" badge={<Badge tone="warning">modelled</Badge>}
          caption={`Where the slick’s surface particles are modelled to drift after the image, across ${forecast.n_ensemble_variants} forcing settings.`}
          footnote={`${forecast.forcing_mode}. ${forecast.interpretation_note}`}>
      <table className="ui-table">
        <caption className="visually-hidden">Modelled spread and exposure by hours after the image</caption>
        <thead>
          <tr>
            <th scope="col">Horizon</th>
            <th scope="col">Modelled spread</th>
            <th scope="col">Shoreline</th>
            <th scope="col">Sensitive areas</th>
          </tr>
        </thead>
        <tbody>
          {forecast.horizons.map((h) => (
            <tr key={h.horizon_hours}>
              <th scope="row">+{h.horizon_hours} h<span className="sub">{hhmm(h.valid_utc)}</span></th>
              <td>{h.envelope_area_km2.toFixed(1)} km²</td>
              <td>{h.modelled_shoreline_fraction == null
                ? <span className="muted">not modelled</span>
                : `${(h.modelled_shoreline_fraction * 100).toFixed(1)}%`}</td>
              <td>
                <ul className="ui-list">
                  {h.sensitive_area_exposure.map((a) => (
                    <li key={a.name} className={a.any_contact ? '' : 'muted'}>
                      {a.name}{' — '}
                      {a.any_contact ? `${(a.modelled_particle_fraction * 100).toFixed(1)}%` : 'no modelled contact'}
                    </li>
                  ))}
                </ul>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <CaptionList items={[
        ['Horizon', C.horizon],
        ['Modelled spread', C.envelopeArea],
        ['Shoreline', C.shoreline],
        ['Sensitive areas', C.exposure],
      ]} />
    </Card>
  );
}
