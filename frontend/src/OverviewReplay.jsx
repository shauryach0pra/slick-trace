import { Suspense, lazy, useEffect, useMemo, useState } from 'react';
import OutcomeIcon from './OutcomeIcon';
import { prepare } from './map/timeline';

/**
 * A case's replay in its overview tile: the case page's own Replay Map - the same imagery, ships and
 * their labels, replayed oil, release burst and moment pills - in compact mode, fed exactly the inputs
 * the Historical Replay card gives it. Every tile follows the overview's one clock (tau), so the image is
 * acquired at the same moment in all of them. A tap opens the case.
 */
const ReplayMap = lazy(() => import('./map/ReplayMap'));

// one fetch per case, shared across mounts and switches between views
const cache = new Map();
function load(api, id) {
  if (!cache.has(id)) {
    const get = (f) => f(id).catch(() => null);
    cache.set(id, Promise.all([api.case(id), get(api.tracks), get(api.envelopeTimeline), get(api.replayTimeline),
      get(api.forecastTimeline), get(api.trackDisplay)])
      .then(([c, tracks, env, replay, forecast, display]) => ({ c, tracks, env, replay, forecast, display }))
      .catch((e) => { cache.delete(id); throw e; }));
  }
  return cache.get(id);
}

export default function ReplayTile({ api, row, index, tau, onOpen }) {
  const [d, setD] = useState(null);
  const [failed, setFailed] = useState(false);
  const f = row.finding;
  const unknown = f?.unknown_source;

  useEffect(() => {
    let live = true;
    // a short stagger, so nine maps are not all built in the same instant
    const t = setTimeout(() => load(api, row.incident_id).then((x) => live && setD(x)).catch(() => live && setFailed(true)), index * 90);
    return () => { live = false; clearTimeout(t); };
  }, [api, row.incident_id, index]);

  // exactly the inputs the Historical Replay card prepares for the map
  const timeline = useMemo(() => {
    if (!d?.c || !d.env || !d.display || !d.tracks) return null;
    const c = d.c;
    const leadKey = c.attribution && !c.attribution.unknown_source ? c.attribution.top_candidate_id : null;
    return prepare({
      acquiredUtc: c.meta?.acquired_utc, env: d.env, replay: d.replay, forecast: d.forecast, display: d.display, tracks: d.tracks, leadKey,
      coastline: c.geography?.coastline, contactH: c.forecast?.first_modelled_sensitive_contact_h,
      info: Object.fromEntries((c.vessels ?? []).map((v) => {
        const ri = c.attribution?.ranking?.findIndex((r) => r.vessel_key === v.vessel_key) ?? -1;
        const ni = c.baseline?.ranking?.findIndex((r) => r.vessel_key === v.vessel_key) ?? -1;
        return [v.vessel_key, {
          status: v.status, replayRank: ri >= 0 ? ri + 1 : null, replayOf: c.attribution?.ranking?.length ?? 0,
          iou: ri >= 0 ? c.attribution.ranking[ri].mean_iou : null, naiveRank: ni >= 0 ? ni + 1 : null, naiveOf: c.baseline?.ranking?.length ?? 0,
        }];
      })),
    });
  }, [d]);

  const open = () => onOpen(row.incident_id);
  const name = row.incident_id.replace('case_', 'Case ');
  return (
    <div className={`ov-tile ov-replay${unknown ? ' is-abstain' : ''}`} style={{ '--k': index }} role="link" tabIndex={0}
         aria-label={`${name} replay - open the case`}
         onClick={(e) => { if (!e.target.closest('.maplibregl-ctrl')) open(); }}
         onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } }}>
      <div className="ovr-map">
        {timeline ? (
          <Suspense fallback={null}>
            <ReplayMap compact bbox={d.c.meta.bbox} coastline={d.c.geography?.coastline} areas={d.c.geography?.sensitive_areas}
                       slick={d.c.slick?.polygon} timeline={timeline} tau={tau} label="" />
          </Suspense>
        ) : <span className="ovr-wait">{failed ? 'Replay unavailable' : 'Loading replay…'}</span>}
      </div>
      <span className="ovr-chip">
        {f && <OutcomeIcon abstain={unknown} />}
        <span className="ov-id">{name}</span>
      </span>
      <span className="ov-open">Open case →</span>
    </div>
  );
}
