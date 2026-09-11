export default function ScenePanel({ manifest, sceneUrl }) {
  if (!manifest) return null;
  const isSynthetic = manifest.provenance?.status === 'synthetic';

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Observed scene</h2>
        {isSynthetic && <span className="tag tag-amber">synthetic</span>}
      </div>
      <img className="scene-img" src={sceneUrl} alt="SAR scene" />
      <dl className="meta">
        <div><dt>Incident</dt><dd>{manifest.incident_id}</dd></div>
        <div><dt>Acquired</dt><dd>{manifest.acquired_utc?.replace('T', ' ').replace('+00:00', ' UTC')}</dd></div>
        <div><dt>Sensor</dt><dd>synthetic SAR-like</dd></div>
        <div><dt>Vessels tracked</dt><dd>{manifest.tracks?.length ?? 0}</dd></div>
      </dl>
    </div>
  );
}
