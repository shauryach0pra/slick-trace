import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { HowMeasured } from '../ui/viz';
import TimeScrubber from '../map/TimeScrubber';
import { prepare } from '../map/timeline';
import { SHIP_TYPES, TYPE_LABEL, glyph } from '../map/shipGlyphs';
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

// a tiny share is '<0.1%', never '0.0%'
const pct = (x) => (x > 0 && x < 0.001 ? '<0.1%' : `${(x * 100).toFixed(x < 0.1 ? 1 : 0)}%`);
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
    api.ensembleFan(incidentId).then(put('fan')).catch(() => put('fan')(null));
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
    info: Object.fromEntries((c.vessels ?? []).map((v) => {
      const ri = c.attribution?.ranking?.findIndex((r) => r.vessel_key === v.vessel_key) ?? -1;
      const ni = c.baseline?.ranking?.findIndex((r) => r.vessel_key === v.vessel_key) ?? -1;
      return [v.vessel_key, {
        status: v.status,
        replayRank: ri >= 0 ? ri + 1 : null, replayOf: c.attribution?.ranking?.length ?? 0,
        iou: ri >= 0 ? c.attribution.ranking[ri].mean_iou : null,
        naiveRank: ni >= 0 ? ni + 1 : null, naiveOf: c.baseline?.ranking?.length ?? 0,
      }];
    })),
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

  const slickInfo = c?.slick?.geometry ? {
    when: `detected in the radar image at ${acquired?.slice(11, 16)} UTC`,
    area: `${c.slick.geometry.area_km2} km²`,
    detector: c.slick.detector,
    iou: c.slick.truth_agreement_iou != null ? `IoU ${c.slick.truth_agreement_iou} (synthetic benchmark)` : 'not measured',
  } : null;

  // the popover's "show in ranking": scroll to the vessel's row and flash it
  const flash = (key) => {
    const row = document.querySelector(`[data-rank-key="${key}"]`);
    if (!row) return;
    // scroll only the evidence column: scrollIntoView can also scroll the locked
    // window itself, which shifted the whole app sideways
    const pane = row.closest('.finder-features');
    if (pane) {
      const top = row.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop - pane.clientHeight / 2;
      pane.scrollTo({ top, behavior: 'smooth' });
    }
    row.classList.remove('is-flash'); void row.offsetWidth; row.classList.add('is-flash');
    setTimeout(() => row.classList.remove('is-flash'), 1900);
  };
  const showRanking = useCallback((key, which) => {
    // the ranking opens on proximity; a forward-replay row needs the reveal first
    if (which === 'replay') window.dispatchEvent(new CustomEvent('slicktrace:reveal'));
    setTimeout(() => flash(key), which === 'replay' ? 1250 : 0);
  }, []);

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
    <Card title="Replay Map" caption="Play the 24 hours before and after the image."
          badge={<Badge tone={tone}>{t === 0 ? 'Observed at image time' : 'Modelled drift'}</Badge>}>
      <Suspense fallback={<div className="rmap rmap-loading">Loading map…</div>}>
        {timeline ? (
          <ReplayMap bbox={c.meta.bbox} coastline={c.geography?.coastline} slickInfo={slickInfo} onShowRanking={showRanking}
                     areas={c.geography?.sensitive_areas} slick={c.slick?.polygon}
                     timeline={timeline} tau={tau} label={label} onPick={onPick} fan={data.fan} />
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

      <MapLegend leadKey={leadKey} />
      <HowMeasured title="How to read this map">
        <dl>
          <dt>Reading the map</dt><dd>{C.replayMap}</dd>
          {note && <><dt>At this hour</dt><dd>{note}</dd></>}
        </dl>
      </HowMeasured>
      {envFrame && (
        <details className="howto">
          <summary><span className="howto-chev" aria-hidden="true" />Vessel states at this hour</summary>
          <table className="ui-table">
            <caption className="visually-hidden">Vessel positions and envelope membership at the selected hour</caption>
            <thead><tr><th scope="col">Vessel</th><th scope="col">At this hour</th>
              <th scope="col">Type</th><th scope="col">Overall</th><th scope="col">Distance to envelope</th></tr></thead>
            <tbody>
              {envFrame.vessels.map((v) => (
                <tr key={v.vessel_key}>
                  <td className="cg-mono">{v.vessel_key}{v.vessel_key === leadKey ? ' (leading candidate)' : ''}</td>
                  <td>{t > 0 ? 'projected from last course and speed (no AIS after the image)' : (v.lon === null ? 'no track data' : STATE_LABEL[v.at_this_time] ?? v.at_this_time)}</td>
                  <td>{TYPE_LABEL[display?.vessels?.find((d) => d.vessel_key === v.vessel_key)?.vessel_type] ?? TYPE_LABEL.other}</td>
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

/**
 * The legend as four groups - Vessels, Oil, Areas, Model - each opening its
 * entries, instead of one long list under the map. Symbols are the map's own.
 */
function MapLegend({ leadKey }) {
  const [open, setOpen] = useState(null);
  const groups = [
    { key: 'vessels', name: 'Vessels', icon: <i className="lg-glyph" dangerouslySetInnerHTML={{ __html: glyph('tanker') }} />, entries: [
      ...SHIP_TYPES.map((ty) => [<i key={ty} className="lg-glyph" dangerouslySetInnerHTML={{ __html: glyph(ty) }} />, ty]),
      [<i key="p" className="lg-ship is-projected" />, 'projected after the image'],
      [<i key="i" className="lg-ship is-inside" />, 'inside the origin envelope'],
      ...(leadKey ? [[<i key="l" className="lg-ship is-lead" />, 'leading candidate']] : []),
      [<i key="g" className="lg-gap" />, 'AIS gap or projected track'],
    ] },
    { key: 'oil', name: 'Oil', icon: <i className="lg-oil" />, entries: [
      [<i key="s" className="lg-slick" />, 'observed slick'],
      [<i key="o" className="lg-oil" />, 'modelled oil'],
      [<i key="t" className="lg-stranded" />, 'stranded on the coast'],
      [<i key="h" className="lg-hit" />, 'oil reaches a sensitive area'],
    ] },
    { key: 'areas', name: 'Areas', icon: <i className="lg-env" />, entries: [
      [<i key="e" className="lg-env" />, 'origin envelope, 50 / 75 / 90%'],
      [<i key="f" className="lg-area is-fishery" />, 'fishing ground'],
      [<i key="m" className="lg-area" />, 'mangrove fringe'],
    ] },
    { key: 'model', name: 'Model', icon: <i className="lg-fan" />, entries: [
      [<i key="d" className="lg-fan" />, 'ensemble drift: the six forcing variants forward replay scored'],
      [<i key="c" className="lg-forcing" />, 'forcing: one uniform current'],
    ] },
  ];
  const g = groups.find((x) => x.key === open);
  return (
    <div className="lgx">
      <div className="lgx-chips" role="group" aria-label="Map legend">
        {groups.map((x) => (
          <button key={x.key} type="button" className={`lgx-chip${open === x.key ? ' is-on' : ''}`} aria-expanded={open === x.key}
                  onClick={() => setOpen(open === x.key ? null : x.key)}>
            {x.icon}{x.name}<span className="lgx-n">{x.entries.length}</span>
          </button>
        ))}
      </div>
      {g && (
        <div className="lgx-panel" key={g.key}>
          <ul>{g.entries.map(([icon, label]) => <li key={label}>{icon}<span>{label.charAt(0).toUpperCase() + label.slice(1)}</span></li>)}</ul>
          {g.note && <p>{g.note}</p>}
        </div>
      )}
    </div>
  );
}

