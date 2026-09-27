import { useState } from 'react';
import { Badge, Card } from '../ui/primitives';
import { useCountUp } from '../ui/useCountUp';
import { useInView } from '../ui/useInView';
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

const TONES = ['cyan', 'green', 'orange'];

export default function ForecastCard({ forecast }) {
  const [hi, setHi] = useState(0);
  // the share bars fill, and their numbers count up, when the share panel itself is on screen
  const [sharesRef, sharesSeen] = useInView({ threshold: 0.5 });
  if (!forecast) return null;
  const hs = forecast.horizons;
  const h = hs[Math.min(hi, hs.length - 1)];
  const xs = hs.map((x) => `+${x.horizon_hours} h`);
  const spreadMax = Math.ceil(Math.max(...hs.map((x) => x.envelope_area_km2)) / 100) * 100;
  const shares = [
    ...h.sensitive_area_exposure.map((a, k) => ({ name: a.name.replace(' (synthetic)', ''), v: a.modelled_particle_fraction, tone: TONES[k % TONES.length] })),
    ...(h.modelled_shoreline_fraction != null ? [{ name: 'Shoreline', v: h.modelled_shoreline_fraction, tone: 'grey' }] : []),
  ];
  return (
    <Card title="Forward Exposure" badge={<Badge tone="warning">Modelled, not a forecast</Badge>}
          caption="Where the oil is modelled to drift after the image.">
      <div className="fx-board">
        <div className="fx-hero">
          <div className="fx-hero-head">
            <span className="fx-hero-label">Modelled spread</span>
            <div className="fx-seg" role="tablist" aria-label="Hours after the image">
              {hs.map((x, i) => (
                <button key={x.horizon_hours} type="button" role="tab" aria-selected={i === hi} className={i === hi ? 'is-on' : ''}
                        onClick={() => setHi(i)}>+{x.horizon_hours} h</button>
              ))}
              <span className="fx-seg-thumb" style={{ '--i': hi }} aria-hidden="true" />
            </div>
          </div>
          <span className="fx-hero-big"><Count value={h.envelope_area_km2} /><small> km²</small></span>
          <LineChart xs={xs} yMax={spreadMax} yFormat={(v) => `${Math.round(v)}`} highlight={hi} height={124}
                     series={[{ name: 'Modelled spread (km²)', tone: 'accent', area: true, values: hs.map((x) => x.envelope_area_km2) }]}
                     ariaLabel={`Modelled spread: ${hs.map((x) => `${x.envelope_area_km2} square kilometres at plus ${x.horizon_hours} hours`).join(', ')}`} />
        </div>
        <div className="fx-shares" ref={sharesRef}>
          <span className="fx-hero-label">Share of modelled oil at +{h.horizon_hours} h</span>
          {shares.map((x, k) => (
            <div key={x.name} className={`fx-share tone-${x.tone}`}>
              <span className="fx-share-name">{x.name}</span>
              <span className="fx-share-track"><i style={{ '--w': sharesSeen ? Math.min(1, x.v) : 0, '--k': k }} /></span>
              <span className="fx-share-val"><ShareVal v={x.v} run={sharesSeen} /></span>
            </div>
          ))}
          <span className="fx-when">{hhmm(h.valid_utc)}</span>
        </div>
      </div>
      <HowMeasured>
        <dl>
          <dt>Horizon</dt><dd>{C.horizon} {hs.map((x) => `+${x.horizon_hours} h is ${hhmm(x.valid_utc)}`).join('; ')}.</dd>
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

function Count({ value }) {
  const [ref, seen] = useInView();
  return <span ref={ref}>{useCountUp(value, { decimals: 0, duration: 700, run: seen })}</span>;
}

// the bar's own curve (CSS cubic-bezier(0.65, 0, 0.35, 1)), so the number moves in step with it
const easeInOutCubic = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);

/** A share that counts up with its bar; one too small to count shows as "<1%". */
function ShareVal({ v, run }) {
  const tiny = v > 0 && v < 0.005;
  const n = useCountUp(tiny ? null : Math.round(v * 100), { decimals: 0, duration: 1300, run, easing: easeInOutCubic });
  return <>{tiny ? '<1' : n}%</>;
}
