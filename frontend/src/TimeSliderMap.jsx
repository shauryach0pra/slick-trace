import { useCallback, useEffect, useRef, useState } from 'react';
import MetricInfo from './MetricInfo';

/**
 * Live historical map with a draggable UTC control (masterplan p.8, p.13).
 *
 * This replaces the earlier static filmstrip. The distinction is the whole
 * demonstration: three vessels excluded and two retained is an argument;
 * watching the exclusion happen as time rewinds is the evidence. The slider
 * queries the backward envelope for the requested time rather than stepping
 * through pre-rendered frames, so a reviewer can stop anywhere.
 *
 * Accessibility: the slider is a native range input, so it is keyboard
 * operable (arrows, Home, End) with no extra handling, and the same state is
 * published as a text table below the map for anyone not reading the SVG.
 * Vessel state is carried by SHAPE as well as colour.
 */

const W = 480;
const H = 340;
const PAD = 26;

const STATE_STYLE = {
  inside: { color: 'var(--teal)', shape: 'circle', label: 'in envelope' },
  outside: { color: 'var(--text-dim)', shape: 'square', label: 'outside envelope' },
  no_data: { color: 'var(--amber)', shape: 'triangle', label: 'no track data at this time' },
};

function VesselMarker({ x, y, state, isLead }) {
  const style = STATE_STYLE[state] ?? STATE_STYLE.no_data;
  const r = isLead ? 5 : 3.6;
  if (style.shape === 'square') {
    return <rect x={x - r} y={y - r} width={r * 2} height={r * 2} fill={style.color} />;
  }
  if (style.shape === 'triangle') {
    return <polygon points={`${x},${y - r} ${x + r},${y + r} ${x - r},${y + r}`} fill={style.color} />;
  }
  return (
    <g>
      <circle cx={x} cy={y} r={r} fill={style.color} />
      {isLead && <circle cx={x} cy={y} r={r + 3.5} fill="none" stroke={style.color} strokeWidth="1.2" />}
    </g>
  );
}

export default function TimeSliderMap({ incidentId, api, tracksData, topCandidateId }) {
  const [hoursBefore, setHoursBefore] = useState(0);
  const [envelope, setEnvelope] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const requestSeq = useRef(0);

  const fetchEnvelope = useCallback(async (h) => {
    const seq = ++requestSeq.current;
    setLoading(true);
    try {
      const data = await api.envelope(incidentId, h);
      // drop stale responses: dragging fires many requests and they can land
      // out of order, which would show a time the slider is no longer at
      if (seq === requestSeq.current) {
        setEnvelope(data);
        setError(null);
      }
    } catch (e) {
      if (seq === requestSeq.current) setError(String(e.message ?? e));
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }, [api, incidentId]);

  useEffect(() => { fetchEnvelope(hoursBefore); }, [hoursBefore, fetchEnvelope]);

  if (!tracksData) return null;
  const { bbox, sensitive_areas: areas = [], coastline = [] } = tracksData;

  const toXY = (lon, lat) => [
    PAD + ((lon - bbox.min_lon) / (bbox.max_lon - bbox.min_lon)) * (W - 2 * PAD),
    PAD + ((bbox.max_lat - lat) / (bbox.max_lat - bbox.min_lat)) * (H - 2 * PAD),
  ];

  const timeLabel = envelope
    ? envelope.time_utc.replace('T', ' ').replace('+00:00', '')
    : '—';
  const inside = (envelope?.vessels ?? []).filter((v) => v.at_this_time === 'inside');

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Historical replay</h2>
        <span className={envelope?.hindcast ? 'tag tag-amber' : 'tag tag-teal'}>
          {envelope?.hindcast ? 'hindcast — modelled' : 'observed'}
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="track-map" role="img"
           aria-label={`Vessel positions and the backward origin envelope at ${timeLabel} UTC. ` +
             `${inside.length} of ${envelope?.vessels?.length ?? 0} vessels are inside the envelope ` +
             `at this time. A text equivalent follows below the map.`}>
        <rect x="0" y="0" width={W} height={H} fill="var(--ink-950)" />

        {areas.map((a) => {
          const pts = a.polygon.map(([lo, la]) => toXY(lo, la).map((n) => n.toFixed(1)).join(',')).join(' ');
          return <polygon key={a.name} points={pts} fill="var(--ink-800)" stroke="var(--line)"
                          strokeDasharray="3 3" opacity="0.7" />;
        })}
        {coastline.length > 1 && (
          <path d={coastline.map(([lo, la], i) => {
            const [x, y] = toXY(lo, la);
            return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
          }).join(' ')} fill="none" stroke="var(--line)" strokeWidth="1.5" />
        )}

        {/* Probability contours over the origin envelope. Drawn under the
            particles: the cloud shows the ensemble, the rings say how much of
            it sits where. 90% outermost so the nesting reads correctly. */}
        {[...(envelope?.density_contours ?? [])].reverse().map((c, ci) =>
          c.polygons.map((ring, ri) => (
            <polygon
              key={`dc-${ci}-${ri}`}
              points={ring.map(([lo, la]) => toXY(lo, la).map((n) => n.toFixed(1)).join(',')).join(' ')}
              fill="var(--teal)"
              fillOpacity={0.05 + 0.05 * ci}
              stroke="var(--teal)"
              strokeOpacity={0.35 + 0.2 * ci}
              strokeWidth="0.9"
              strokeDasharray={ci === 2 ? 'none' : '3 2'}
            />
          )),
        )}

        {/* origin envelope particles at the selected time */}
        {(envelope?.particles ?? []).map(([lo, la], i) => {
          const [x, y] = toXY(lo, la);
          return <circle key={i} cx={x} cy={y} r="1.1" fill="var(--teal)" opacity="0.22" />;
        })}

        {/* track history up to the selected time only — drawing the full track
            would show the reviewer information the analysis does not have yet
            at that point in the replay */}
        {tracksData.tracks.map((t) => {
          const cutoff = envelope ? new Date(envelope.time_utc) : null;
          const pts = t.fixes
            .filter((f) => !cutoff || new Date(f.t_utc) <= cutoff)
            .map((f) => toXY(f.lon, f.lat));
          if (pts.length < 2) return null;
          const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
          const isLead = t.vessel_key === topCandidateId;
          return <path key={t.vessel_key} d={d} fill="none"
                       stroke={isLead ? 'var(--teal)' : 'var(--text-dim)'}
                       strokeWidth={isLead ? 1.8 : 1} opacity={isLead ? 0.9 : 0.45} />;
        })}

        {(envelope?.vessels ?? []).filter((v) => v.lon !== null).map((v) => {
          const [x, y] = toXY(v.lon, v.lat);
          const isLead = v.vessel_key === topCandidateId;
          return (
            <g key={v.vessel_key}>
              <VesselMarker x={x} y={y} state={v.at_this_time} isLead={isLead} />
              <text x={x + 8} y={y - 7} fontSize="8.5" fontFamily="var(--font-mono)"
                    fill={v.at_this_time === 'inside' ? 'var(--teal)' : 'var(--text-dim)'}>
                {v.vessel_key}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="slider-row">
        <label htmlFor="utc-slider" className="slider-label">
          UTC replay
          <MetricInfo metric="hindcastEnvelope" />
        </label>
        <input
          id="utc-slider"
          type="range"
          min="0"
          max="24"
          step="1"
          value={hoursBefore}
          onChange={(e) => setHoursBefore(Number(e.target.value))}
          aria-valuetext={`${hoursBefore} hours before acquisition — ${timeLabel} UTC`}
          className="utc-slider"
        />
        <output className="slider-readout" htmlFor="utc-slider">
          <span className="slider-time">{timeLabel} UTC</span>
          <span className="slider-delta">
            {hoursBefore === 0 ? 'acquisition time' : `−${hoursBefore} h`}
            {loading ? ' · updating' : ''}
          </span>
        </output>
      </div>

      {error && <p className="panel-error" role="alert">Envelope query failed: {error}</p>}

      <div className="legend" aria-hidden="true">
        <span><i className="mk mk-circle" /> in envelope</span>
        <span className="mk-contour-legend">50 / 75 / 90% of origin density</span>
        <span><i className="mk mk-square" /> outside</span>
        <span><i className="mk mk-triangle" /> no data</span>
        <span><i className="mk mk-ring" /> leading candidate</span>
      </div>

      {/* Text equivalent of the map. The SVG carries a summary label, but the
          per-vessel detail has to be reachable without reading a picture. */}
      <details className="text-equivalent">
        <summary>Vessel states at {timeLabel} UTC (text equivalent)</summary>
        <table className="state-table">
          <caption className="visually-hidden">
            Vessel envelope membership at the selected replay time
          </caption>
          <thead>
            <tr><th scope="col">Vessel</th><th scope="col">At this time</th>
                <th scope="col">Overall</th><th scope="col">Distance to envelope</th></tr>
          </thead>
          <tbody>
            {(envelope?.vessels ?? []).map((v) => (
              <tr key={v.vessel_key}>
                <td>{v.vessel_key}</td>
                <td>{STATE_STYLE[v.at_this_time]?.label ?? v.at_this_time}</td>
                <td>{v.overall_status}</td>
                <td>{v.distance_to_envelope_deg ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      <p className="ranking-caption">
        {envelope?.note ?? 'Envelope width grows with hours-back because release time, ' +
          'duration and diffusivity are unknown.'}
      </p>
    </div>
  );
}
