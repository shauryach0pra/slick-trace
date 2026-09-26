import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import TimeScrubber from '../map/TimeScrubber';
import { prepare } from '../map/timeline';
import '../map/replayCard.css';
import { Badge, Card } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * The replay map: the case on a real map, from 24 h before the image to 24 h after.
 *
 * Every hour shown is a computed state:
 *   before  the backward origin envelope (envelope_timeline.json) and, when a
 *           vessel was named, its scored release replayed hour by hour
 *           (replay_timeline.json);
 *   image   the detected slick outline, observed;
 *   after   the forecast's particle drift, stranding at the coast
 *           (forecast_timeline.json).
 * Vessel positions and trails come from the envelope frames and the
 * rendering-only display paths (track_display.json), cut at the selected hour
 * so the map never shows a track the analysis would not yet have.
 */
const ReplayMap = lazy(() => import('../map/ReplayMap'));

const pct = (x) => `${(x * 100).toFixed(x < 0.1 ? 1 : 0)}%`;
const ms = (s) => new Date(s).getTime();

const STATE_LABEL = { inside: 'inside the origin envelope', outside: 'outside the origin envelope',
                      ended: 'AIS ends at the image' };

export default function HistoricalReplayCard({ incidentId, api, c, tracks }) {
  const [data, setData] = useState({});
  // tau: the continuous replay clock, in hours from the image. t: the computed
  // hour nearest it, which the labels, badge and text table describe.
  const [tau, setTau] = useState(0);
  const tauRef = useRef(0);
  const anim = useRef(0);
  const t = Math.round(tau);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [probe, setProbe] = useState(null);

  useEffect(() => {
    let live = true;
    const put = (k) => (v) => { if (live) setData((d) => ({ ...d, [k]: v })); };
    api.envelopeTimeline(incidentId).then(put('env')).catch(() => put('env')(null));
    api.replayTimeline(incidentId).then(put('replay')).catch(() => put('replay')(null));
    api.forecastTimeline(incidentId).then(put('forecast')).catch(() => put('forecast')(null));
    api.trackDisplay(incidentId).then(put('display')).catch(() => put('display')(null));
    return () => { live = false; };
  }, [api, incidentId]);

  const { env, replay, forecast, display } = data;
  const min = -((env?.frames?.length ?? 1) - 1);
  const max = forecast?.frames?.length ?? 0;

  const moveTau = useCallback((v) => { tauRef.current = v; setTau(v); }, []);

  // playback: the clock runs continuously, about 1.4 h a second at 1x
  useEffect(() => {
    if (!playing) return undefined;
    const rate = (speed === 1 ? 1 / 0.7 : 1 / 0.35) / 1000;      // hours per millisecond
    let last = performance.now();
    const step = (now) => {
      const next = Math.min(max, tauRef.current + (now - last) * rate);
      last = now;
      moveTau(next);
      if (next >= max) { setPlaying(false); return; }
      anim.current = requestAnimationFrame(step);
    };
    anim.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(anim.current);
  }, [playing, speed, max, moveTau]);

  // scrubbing or stepping glides the clock to the chosen hour and stops on it
  const seek = useCallback((v) => {
    setPlaying(false);
    cancelAnimationFrame(anim.current);
    const from = tauRef.current, t0 = performance.now(), dur = Math.min(700, 140 + Math.abs(v - from) * 90);
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur), e = 1 - (1 - k) ** 3;
      moveTau(k === 1 ? v : from + (v - from) * e);
      if (k < 1) anim.current = requestAnimationFrame(step);
    };
    anim.current = requestAnimationFrame(step);
  }, [moveTau]);
  useEffect(() => () => cancelAnimationFrame(anim.current), []);

  const acquired = c?.meta?.acquired_utc;
  const leadKey = c?.attribution && !c.attribution.unknown_source ? c.attribution.top_candidate_id : null;
  const envFrame = env?.frames?.find((f) => f.hours_before_acquisition === Math.max(-t, 0));
  const repFrame = replay?.frames?.find((f) => f.hours_before_acquisition === Math.max(-t, 0));
  const fcFrame = t > 0 ? forecast?.frames?.find((f) => f.hours_after_acquisition === t) : null;

  const timeline = useMemo(() => (c && env && display && tracks ? prepare({
    acquiredUtc: acquired, env, replay, forecast, display, tracks, leadKey, coastline: c.geography?.coastline,
    contactH: c.forecast?.first_modelled_sensitive_contact_h,
  }) : null), [c, env, replay, forecast, display, tracks, leadKey, acquired]);

  const label = t < 0
    ? (repFrame && repFrame.released_fraction > 0
      ? `Modelled · ${-t} h before the image: where this oil could have been, and ${leadKey} releasing (${pct(repFrame.released_fraction)} released)`
      : `Modelled · ${-t} h before the image: where this oil could have been ${-t} h earlier`)
    : t === 0
      ? `Observed · the image: detected slick${repFrame ? ', with the leading candidate’s replayed footprint' : ''}`
      : `Modelled · ${t} h after the image: forecast drift${fcFrame?.stranded_fraction ? `, ${pct(fcFrame.stranded_fraction)} stranded on the coast` : ''}; ships projected from their last course and speed`;
  const note = t < 0 ? (repFrame ? replay.note : env?.note) : t === 0 ? (replay?.named ? replay.note : env?.note) : forecast?.note;

  const marks = [];
  if (replay?.named && acquired) {
    const h = Math.round((ms(replay.release_start) - ms(acquired)) / 3600e3);
    if (h >= min && h < 0) marks.push({ t: h, label: 'release' });
  }

  const onPick = useCallback(async ({ lon, lat }) => {
    if (t > 0) { setProbe({ note: C.probeRange }); return; }
    try {
      const r = await api.probe(incidentId, lon.toFixed(5), lat.toFixed(5), -t);
      setProbe(r);
    } catch { setProbe(null); }
  }, [api, incidentId, t]);

  if (!c) return null;
  const tone = t === 0 ? 'accent' : 'warning';
  return (
    <Card title="Replay Map" caption={C.replayMap}
          badge={<Badge tone={tone}>{t === 0 ? 'observed' : 'modelled'}</Badge>}
          footnote={note}>
      <Suspense fallback={<div className="rmap rmap-loading">Loading map…</div>}>
        {timeline ? (
          <ReplayMap bbox={c.meta.bbox} coastline={c.geography?.coastline}
                     areas={c.geography?.sensitive_areas} slick={c.slick?.polygon}
                     timeline={timeline} tau={tau} label={label} onPick={onPick} />
        ) : <div className="rmap rmap-loading">Loading replay…</div>}
      </Suspense>

      {acquired && env && (
        <TimeScrubber t={t} pos={tau} onChange={seek} min={min} max={max}
                      playing={playing} speed={speed} acquiredUtc={acquired} marks={marks}
                      onPlay={() => {
                        cancelAnimationFrame(anim.current);
                        if (!playing && tauRef.current >= max) moveTau(min);
                        setPlaying((p) => !p);
                      }}
                      onSpeed={() => setSpeed((s) => (s === 1 ? 2 : 1))} />
      )}

      {probe && (
        <div className="probe-readout">
          {probe.current ? (
            <div className="probe-head">
              <strong>{probe.current.speed_knots} kn</strong> bearing {probe.current.bearing_deg_from_north}° at{' '}
              {probe.lat.toFixed(3)}° N {probe.lon.toFixed(3)}° E
              <button type="button" className="probe-close" onClick={() => setProbe(null)}>clear</button>
            </div>
          ) : (
            <div className="probe-head">{probe.note}
              <button type="button" className="probe-close" onClick={() => setProbe(null)}>clear</button></div>
          )}
          {probe.model_note && <p className="probe-note">{probe.model_note}</p>}
        </div>
      )}

      <ul className="rmap-legend" aria-label="Map legend">
        <li><i className="lg-ship" /> vessel (symbol, not to scale)</li>
        <li><i className="lg-ship is-projected" /> projected after the image</li>
        <li><i className="lg-ship is-inside" /> inside origin envelope</li>
        {leadKey && <li><i className="lg-ship is-lead" /> leading candidate</li>}
        <li><i className="lg-env" /> origin envelope 50 / 75 / 90%</li>
        <li><i className="lg-oil" /> modelled oil</li>
        <li><i className="lg-stranded" /> stranded on the coast</li>
        <li><i className="lg-slick" /> observed slick</li>
        <li><i className="lg-gap" /> AIS gap or projected track</li>
        <li><i className="lg-area is-fishery" /> fishing ground (synthetic, after the image)</li>
        <li><i className="lg-area" /> mangrove fringe (synthetic, after the image)</li>
      </ul>

      {envFrame && (
        <details className="text-equivalent">
          <summary>Vessel states at this hour (text equivalent)</summary>
          <table className="ui-table">
            <caption className="visually-hidden">Vessel positions and envelope membership at the selected hour</caption>
            <thead><tr><th scope="col">Vessel</th><th scope="col">At this hour</th>
              <th scope="col">Overall</th><th scope="col">Distance to envelope</th></tr></thead>
            <tbody>
              {envFrame.vessels.map((v) => (
                <tr key={v.vessel_key}>
                  <td className="cg-mono">{v.vessel_key}{v.vessel_key === leadKey ? ' (leading candidate)' : ''}</td>
                  <td>{t > 0 ? 'projected from last course and speed (no AIS after the image)' : (v.lon === null ? 'no track data' : STATE_LABEL[v.at_this_time] ?? v.at_this_time)}</td>
                  <td>{v.overall_status}</td>
                  <td>{v.distance_to_envelope_deg ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </Card>
  );
}
