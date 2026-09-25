import { Badge, Card, Stat, StatGrid } from '../ui/primitives';
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
          caption={`Outline from the ${slick?.detector ?? 'detector'}. ${C.darkness}`}>
      <div className="scene-wrap">
        <img className="scene-img" src={sceneUrl} alt="Radar scene of the incident area" />
        {pts && (
          <svg className="scene-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" role="img"
               aria-label={`Detected slick outline covering ${g?.area_km2} square kilometres`}>
            <polygon points={pts} className="scene-poly" />
          </svg>
        )}
        {slick && !slick.detected && <div className="scene-nodetect">No slick detected</div>}
      </div>

      {g && (
        <div style={{ marginTop: 'var(--space-5)' }}>
          <StatGrid cols={3}>
            <Stat label="Area" value={`${g.area_km2.toFixed(2)} km²`} caption={C.area} />
            <Stat label="Perimeter" value={`${g.perimeter_km.toFixed(2)} km`} caption={C.perimeter} />
            <Stat label="Elongation" value={g.elongation.toFixed(2)} caption={C.elongation} />
            <Stat label="Long axis" value={`${g.major_axis_km.toFixed(2)} km`} caption={C.majorAxis} />
            <Stat label="Short axis" value={`${g.minor_axis_km.toFixed(2)} km`} caption={C.minorAxis} />
            <Stat label="Bearing" value={`${g.orientation_deg_from_north.toFixed(1)}° from N`} caption={C.bearing} />
            {slick.truth_agreement_iou != null && (
              <Stat label="Agreement with truth mask" value={slick.truth_agreement_iou.toFixed(4)} caption={C.truthIou} />
            )}
            <Stat label="Pixel spacing" value={`${meta.pixel_spacing_m} m`} caption={C.pixelSpacing} />
            <Stat label="Vessels tracked" value={nVessels} caption="Vessels with AIS tracks in this scene." />
          </StatGrid>
        </div>
      )}

      <p className="card-foot">
        {meta.incident_id} · acquired {meta.acquired_utc.replace('T', ' ').replace('+00:00', ' UTC')}.
        {' '}{slick?.downstream_note} {slick?.measurement_note}
      </p>
    </Card>
  );
}
