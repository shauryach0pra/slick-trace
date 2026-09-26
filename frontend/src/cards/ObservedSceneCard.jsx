import { Badge, Card } from '../ui/primitives';
import { HowMeasured } from '../ui/viz';
import { useCountUp } from '../ui/useCountUp';
import './observedScene.css';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Values are shown at the precision the detection artifact rounds them to.
 *
 * The observed scene with the detector's outline drawn on it, and the
 * outline's measurements. The raw image alone proves nothing; the outline is
 * what the classical baseline detector retained.
 */
export default function ObservedSceneCard({ meta, slick, sceneUrl, nVessels }) {
  if (!meta) return null;
  const synthetic = meta.provenance?.status === 'synthetic';
  const b = meta.bbox;
  const g = slick?.geometry;
  const pts = (slick?.polygon ?? []).map(([lon, lat]) => {
    const x = ((lon - b.min_lon) / (b.max_lon - b.min_lon)) * 100;
    const y = ((b.max_lat - lat) / (b.max_lat - b.min_lat)) * 100;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ');

  return (
    <Card title="Observed Scene"
          badge={<Badge tone={synthetic ? 'warning' : 'accent'}>{synthetic ? 'synthetic' : 'real'}</Badge>}
          caption="The dark, smooth patch the detector outlined. Radar darkness alone is not proof of oil.">
      <div className="os">
        <div className="scene-wrap os-scene">
          <img className="scene-img" src={sceneUrl} alt="Radar scene of the incident area" />
          {pts && (
            <svg className="scene-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" role="img"
                 aria-label={`Detected slick outline covering ${g?.area_km2} square kilometres`}>
              <polygon points={pts} className="scene-poly" />
            </svg>
          )}
          {slick && !slick.detected && <div className="scene-nodetect">No slick detected</div>}
          <span className="os-stamp">{meta.acquired_utc.slice(11, 16)} UTC · {meta.acquired_utc.slice(0, 10)}</span>
        </div>

        {g && (
          <div className="os-print">
            <span className="os-eyebrow">Slick fingerprint</span>
            <div className="os-print-row">
              <ShapeGlyph major={g.major_axis_km} minor={g.minor_axis_km} bearing={g.orientation_deg_from_north} />
              <div className="os-hero">
                <span className="os-big"><Count value={g.area_km2} decimals={0} /><small> km²</small></span>
                <span className="os-hero-label">sea surface covered</span>
                <div className="os-facts">
                  <span><b>{g.perimeter_km.toFixed(1)}</b> km edge</span>
                  <span><b>{g.elongation.toFixed(2)}</b> elongation</span>
                  <span><b>{g.orientation_deg_from_north.toFixed(0)}°</b> from north</span>
                </div>
                <ElongationBar value={g.elongation} />
              </div>
            </div>
            <div className="os-chips">
              {slick.truth_agreement_iou != null && (
                <span className="os-chip is-truth"><i style={{ '--v': slick.truth_agreement_iou }} />
                  {slick.truth_agreement_iou.toFixed(2)} match with the generator's mask</span>
              )}
              <span className="os-chip">{meta.pixel_spacing_m} m pixels</span>
              <span className="os-chip">{nVessels} vessels tracked</span>
            </div>
          </div>
        )}
      </div>

      <HowMeasured>
        <dl>
          <dt>Detector</dt><dd>{slick?.detector}. {C.darkness}</dd>
          {g && <>
            <dt>Area and edge</dt><dd>{C.area} {C.perimeter}</dd>
            <dt>Shape</dt><dd>Long axis {g.major_axis_km.toFixed(2)} km, short axis {g.minor_axis_km.toFixed(2)} km. {C.elongation} {C.bearing}</dd>
          </>}
          {slick?.truth_agreement_iou != null && <><dt>Match with the generator's mask</dt><dd>{C.truthIou}</dd></>}
          <dt>Measurement</dt><dd>{slick?.measurement_note}</dd>
          <dt>Downstream</dt><dd>{slick?.downstream_note}</dd>
        </dl>
      </HowMeasured>
    </Card>
  );
}

/** The slick's shape, drawn to its measured axes and bearing, north up. */
function ShapeGlyph({ major, minor, bearing }) {
  const S = 62 / Math.max(major, 1e-6);                  // the long axis fills the glyph
  const rx = (major / 2) * S, ry = (minor / 2) * S;
  return (
    <svg className="os-glyph" viewBox="-40 -40 80 80" role="img"
         aria-label={`Slick shape: ${major.toFixed(1)} by ${minor.toFixed(1)} kilometres, long axis ${bearing.toFixed(0)} degrees from north`}>
      <circle r="37" className="os-glyph-ring" />
      <path d="M0 -37 L0 -31" className="os-glyph-tick" />
      <text x="0" y="-26" className="os-glyph-n">N</text>
      <g transform={`rotate(${bearing - 90})`}>
        <ellipse rx={rx} ry={ry} className="os-glyph-shape" pathLength="100" />
        <line x1={-rx} y1="0" x2={rx} y2="0" className="os-glyph-axis" />
        <line x1="0" y1={-ry} x2="0" y2={ry} className="os-glyph-axis is-minor" />
      </g>
    </svg>
  );
}

/** Where the elongation falls between round (1) and streak-like (5 and beyond). */
function ElongationBar({ value }) {
  const f = Math.max(0, Math.min(1, Math.log(value) / Math.log(5)));
  return (
    <div className="os-elong" aria-hidden="true">
      <span>round</span><div className="os-elong-track"><i style={{ left: `${f * 100}%` }} /></div><span>streak</span>
    </div>
  );
}

function Count({ value, decimals }) {
  return useCountUp(value, { decimals, duration: 1000 });
}
