import { Badge, Card } from '../ui/primitives';
import { HowMeasured } from '../ui/viz';
import { LineChart } from '../ui/charts';
import './exposure.css';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Forward exposure: where modelled surface particles go after the image.
 * Modelled exposure and arrival intervals, never predicted damage; the
 * forcing mode is shown verbatim so a retrospective field is not mistaken
 * for an operational forecast.
 */
const hhmm = (s) => s.replace('T', ' ').replace(':00+00:00', ' UTC');

const pct = (v) => `${Math.round(v * 100)}%`;
const TONES = ['cyan', 'green', 'orange'];

export default function ForecastCard({ forecast }) {
  if (!forecast) return null;
  const hs = forecast.horizons;
  const xs = hs.map((h) => `+${h.horizon_hours} h`);
  const spreadMax = Math.ceil(Math.max(...hs.map((h) => h.envelope_area_km2)) / 100) * 100;
  const areas = hs[0]?.sensitive_area_exposure.map((a) => a.name) ?? [];
  const share = [
    ...areas.map((name, k) => ({ name, tone: TONES[k % TONES.length],
      values: hs.map((h) => h.sensitive_area_exposure.find((a) => a.name === name)?.modelled_particle_fraction ?? 0) })),
    ...(hs.some((h) => h.modelled_shoreline_fraction != null)
      ? [{ name: 'Shoreline', tone: 'grey', values: hs.map((h) => h.modelled_shoreline_fraction ?? 0) }] : []),
  ];
  const shareMax = Math.max(0.1, Math.ceil(Math.max(...share.flatMap((x) => x.values)) * 10) / 10);
  // first contact is recorded per area; the chip names the earliest area reached
  const byArea = Object.entries(forecast.first_modelled_sensitive_contact_h ?? {}).filter(([, h]) => h != null)
    .sort((x, y) => x[1] - y[1]);
  const firstArea = byArea[0] ?? null, firstShore = forecast.first_modelled_shoreline_contact_h;
  const last = hs[hs.length - 1]?.horizon_hours;
  return (
    <Card title="Forward Exposure" badge={<Badge tone="warning">modelled</Badge>}
          caption="Where the oil is modelled to drift after the image.">
      <div className="fx-chips">
        <span className={`fx-chip${firstArea != null ? ' is-warn' : ''}`}>
          {firstArea ? <>Reaches the {firstArea[0].replace(' (synthetic)', '').toLowerCase()} by <b>+{firstArea[1]} h</b></> : <>No sensitive-area contact within {last} h</>}</span>
        <span className={`fx-chip${firstShore != null ? ' is-warn' : ''}`}>
          {firstShore != null ? <>Reaches the shoreline by <b>+{firstShore} h</b></> : <>No shoreline contact within {last} h</>}</span>
        <span className="fx-chip is-mode">{forecast.forcing_mode.split(' — ')[0]} — not an operational forecast</span>
      </div>
      <div className="fx-charts">
        <figure className="fx-fig">
          <figcaption><b>Modelled spread</b><span>{hs.map((h) => `${Math.round(h.envelope_area_km2)}`).join(' → ')} km²</span></figcaption>
          <LineChart xs={xs} yMax={spreadMax} yFormat={(v) => `${Math.round(v)}`}
                     series={[{ name: 'Modelled spread (km²)', tone: 'accent', area: true, values: hs.map((h) => h.envelope_area_km2) }]}
                     ariaLabel={`Modelled spread: ${hs.map((h) => `${h.envelope_area_km2} square kilometres at plus ${h.horizon_hours} hours`).join(', ')}`} />
        </figure>
        <figure className="fx-fig">
          <figcaption><b>Share of modelled oil</b>
            <span className="fx-legend">{share.map((x) => <i key={x.name} className={`tone-${x.tone}`}>{x.name.replace(' (synthetic)', '')}</i>)}</span>
          </figcaption>
          <LineChart xs={xs} yMax={shareMax} yFormat={pct} series={share}
                     ariaLabel={share.map((x) => `${x.name}: ${x.values.map((v) => pct(v)).join(', ')}`).join('; ')} />
        </figure>
      </div>
      <HowMeasured>
        <dl>
          <dt>Horizon</dt><dd>{C.horizon} {hs.map((h) => `+${h.horizon_hours} h is ${hhmm(h.valid_utc)}`).join('; ')}.</dd>
          <dt>Modelled spread</dt><dd>{C.envelopeArea}</dd>
          <dt>Shoreline</dt><dd>{C.shoreline}</dd>
          <dt>Sensitive areas</dt><dd>{C.exposure} Areas are synthetic.</dd>
          <dt>Forcing</dt><dd>{forecast.forcing_mode}. {forecast.n_ensemble_variants} forcing settings.</dd>
          <dt>What this is and is not</dt><dd>{forecast.interpretation_note}</dd>
        </dl>
      </HowMeasured>
    </Card>
  );
}
