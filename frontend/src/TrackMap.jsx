const STATUS_COLOR = {
  candidate: 'var(--teal)',
  excluded: 'var(--text-dim)',
  unassessed: 'var(--amber)',
};

export default function TrackMap({ tracksData, historicalMapping, topCandidateId }) {
  if (!tracksData) return null;
  const { bbox, tracks } = tracksData;
  const W = 480, H = 340, PAD = 24;

  const statusByVessel = Object.fromEntries(
    (historicalMapping?.assessments ?? []).map((a) => [a.vessel_key, a.status])
  );

  const toXY = (lon, lat) => [
    PAD + ((lon - bbox.min_lon) / (bbox.max_lon - bbox.min_lon)) * (W - 2 * PAD),
    PAD + ((bbox.max_lat - lat) / (bbox.max_lat - bbox.min_lat)) * (H - 2 * PAD),
  ];

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Candidate vessel tracks</h2>
        <span className="tag">origin envelope</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="track-map">
        <rect x="0" y="0" width={W} height={H} fill="var(--ink-900)" />
        {tracks.map((t) => {
          const status = statusByVessel[t.vessel_key] ?? 'unassessed';
          const color = STATUS_COLOR[status];
          const isTop = t.vessel_key === topCandidateId;
          const points = t.fixes.map((f) => toXY(f.lon, f.lat));
          const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
          return (
            <g key={t.vessel_key}>
              <path d={pathD} fill="none" stroke={color} strokeWidth={isTop ? 2.5 : 1.4} opacity={isTop ? 1 : 0.75} />
              {points.map((p, i) => (
                <circle key={i} cx={p[0]} cy={p[1]} r={isTop ? 3 : 2} fill={color} />
              ))}
              {status !== 'excluded' && (
                <text x={points[0][0] + 6} y={points[0][1] - 6} fontSize="9" fill={color} fontFamily="var(--font-mono)">
                  {t.vessel_key}{isTop ? ' \u2605' : ''}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="legend">
        <span><i style={{ background: STATUS_COLOR.candidate }} /> candidate</span>
        <span><i style={{ background: STATUS_COLOR.excluded }} /> excluded</span>
        <span><i style={{ background: STATUS_COLOR.unassessed }} /> unassessed</span>
        <span><i style={{ background: 'var(--teal)', boxShadow: '0 0 0 1px var(--teal)' }} /> ★ top candidate</span>
      </div>
    </div>
  );
}
