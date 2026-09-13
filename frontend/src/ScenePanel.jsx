import MetricInfo from './MetricInfo';

/**
 * Observed scene with the detected slick drawn on it (PS part (a)).
 *
 * The raw image alone shows a dark patch and proves nothing. The outline is
 * what the classical baseline detector actually retained, and the measurements
 * beside it are taken from that region — so a reviewer sees the detector's
 * output, not just its input.
 */
export default function ScenePanel({ manifest, sceneUrl, detection }) {
  if (!manifest) return null;
  const isSynthetic = manifest.provenance?.status === 'synthetic';
  const bbox = manifest.bbox;
  const g = detection?.geometry;

  // polygon arrives in lon/lat; map it onto the 0–100 overlay box
  const pts = (detection?.polygon ?? []).map(([lon, lat]) => {
    const x = ((lon - bbox.min_lon) / (bbox.max_lon - bbox.min_lon)) * 100;
    const y = ((bbox.max_lat - lat) / (bbox.max_lat - bbox.min_lat)) * 100;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ');

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Observed scene</h2>
        {isSynthetic && <span className="tag tag-amber">synthetic</span>}
      </div>

      <div className="scene-wrap">
        <img className="scene-img" src={sceneUrl} alt="SAR scene" />
        {pts && (
          <svg className="scene-overlay" viewBox="0 0 100 100"
               preserveAspectRatio="none" role="img"
               aria-label={`Detected slick outline covering ${g?.area_km2} square kilometres`}>
            <polygon points={pts} className="scene-poly" />
          </svg>
        )}
        {detection?.detected === false && (
          <div className="scene-nodetect">No slick detected</div>
        )}
      </div>

      {g && (
        <>
          <div className="geom-grid">
            <div><span className="geom-k">Area</span><span className="geom-v">{g.area_km2} km²</span></div>
            <div><span className="geom-k">Perimeter</span><span className="geom-v">{g.perimeter_km} km</span></div>
            <div><span className="geom-k">Major axis</span><span className="geom-v">{g.major_axis_km} km</span></div>
            <div><span className="geom-k">Minor axis</span><span className="geom-v">{g.minor_axis_km} km</span></div>
            <div><span className="geom-k">Elongation</span><span className="geom-v">{g.elongation}</span></div>
            <div><span className="geom-k">Bearing</span><span className="geom-v">{g.orientation_deg_from_north}° from N</span></div>
          </div>
          <p className="ranking-caption">
            Outline from the classical baseline detector — IoU{' '}
            <strong>{detection.agreement_with_truth_mask?.iou}</strong> against the
            generator truth mask<MetricInfo metric="iou" />. {detection.boundary_note}
          </p>
        </>
      )}

      <dl className="meta">
        <div><dt>Incident</dt><dd>{manifest.incident_id}</dd></div>
        <div><dt>Acquired</dt><dd>{manifest.acquired_utc?.replace('T', ' ').replace('+00:00', ' UTC')}</dd></div>
        <div><dt>Pixel spacing</dt><dd>{manifest.pixel_spacing_m} m</dd></div>
        <div><dt>Vessels tracked</dt><dd>{manifest.tracks?.length ?? 0}</dd></div>
      </dl>
    </div>
  );
}
