/**
 * The replay's clock: every layer evaluated at a fractional hour.
 *
 * The pipeline computes hourly states. Between two computed hours the map
 * shows a visual transition - particles and ships move linearly between their
 * two computed positions, the envelope cross-fades - and at a whole hour it
 * shows exactly the computed state. Ships between fixes follow the
 * rendering-only display path (track_display.json), which never bridges a gap.
 *
 * After the image there is no AIS. Ships are then PROJECTED from their last
 * reported course and speed (dead reckoning), stopping at the coast, and are
 * drawn and labelled as projections, never as observations.
 */

const H = 3600e3;
const ms = (s) => new Date(s).getTime();
const KM_PER_DEG_LAT = 111.0;

export function prepare({ acquiredUtc, env, replay, forecast, display, tracks, leadKey, coastline, contactH }) {
  const acq = ms(acquiredUtc);
  const envByH = new Map((env?.frames ?? []).map((f) => [Math.round(f.hours_before_acquisition), f]));
  const repByH = new Map((replay?.named ? replay.frames : []).map((f) => [Math.round(f.hours_before_acquisition), f]));
  const fcByH = new Map((forecast?.frames ?? []).map((f) => [f.hours_after_acquisition, f]));
  const fixesByKey = new Map((tracks?.tracks ?? []).map((t) => [t.vessel_key, t.fixes.map((f) => ({ t: ms(f.t_utc), sog: f.sog_knots }))]));
  const vessels = (display?.vessels ?? []).map((v) => ({
    key: v.vessel_key,
    lead: v.vessel_key === leadKey,
    pts: v.display_path.map((p) => [p[0], p[1], ms(p[2])]),
    gaps: v.gaps.filter((g) => g.kind === 'internal').map((g) => [ms(g.start_utc), ms(g.end_utc)]),
    fixes: fixesByKey.get(v.vessel_key) ?? [],
  }));
  const repHours = [...repByH.keys()];
  const releaseH = replay?.named ? (ms(replay.release_start) - acq) / H : null;
  const leadV = vessels.find((v) => v.lead);
  const releasePos = releaseH !== null && leadV ? vesselAt(leadV, acq + releaseH * H)?.pos ?? null : null;
  return {
    acq, envByH, repByH, fcByH, vessels, leadKey,
    minH: -Math.max(0, ...envByH.keys()),
    maxH: Math.max(0, ...fcByH.keys()),
    releaseH, releasePos,
    releaseFrom: repHours.length ? -Math.max(...repHours) : null,
    land: landTester(coastline),
    contactH: contactH ?? {},          // first modelled contact hour per sensitive area (forecast_result)
  };
}

// ------------------------------------------------------------ geometry

const lerp = (a, b, k) => a + (b - a) * k;

function bearing(a, b) {
  const dx = (b[0] - a[0]) * Math.cos((a[1] * Math.PI) / 180);
  const dy = b[1] - a[1];
  return ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
}

// point-in-polygon against the coastline closed around the land to its east,
// the same land test the pipeline uses (slicktrace_core.geography)
function landTester(coastline) {
  if (!coastline || coastline.length < 2) return () => false;
  const east = Math.max(...coastline.map((p) => p[0])) + 1;
  const ring = [...coastline, [east, coastline.at(-1)[1]], [east, coastline[0][1]]];
  return (lon, lat) => {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  };
}

// ------------------------------------------------------------ vessels

function sogAt(fixes, t) {
  let s = null;
  for (const f of fixes) { if (f.t <= t) s = f.sog; else break; }
  return s;
}

/** Position, heading and the trail so far, at time t (ms). Null when there is
 *  no track: before the first fix, after the last, or inside a gap. */
function vesselAt(v, t) {
  const p = v.pts;
  if (!p.length || t < p[0][2] || t > p.at(-1)[2]) return null;
  if (v.gaps.some(([s, e]) => t > s && t < e)) return null;
  let i = 0;
  while (i < p.length - 2 && p[i + 1][2] < t) i += 1;
  const a = p[i], b = p[Math.min(i + 1, p.length - 1)];
  const k = b[2] > a[2] ? (t - a[2]) / (b[2] - a[2]) : 0;
  const pos = [lerp(a[0], b[0], k), lerp(a[1], b[1], k)];
  // heading from the path's own curve, looking a little either side
  const back = p[Math.max(0, i - 1)], ahead = p[Math.min(p.length - 1, i + 2)];
  return { pos, heading: bearing(back, ahead), i };
}

function trailUpTo(v, t, pos) {
  const segs = [];
  let seg = [];
  for (let i = 0; i < v.pts.length && v.pts[i][2] <= t; i += 1) {
    if (i > 0 && v.gaps.some(([s, e]) => s >= v.pts[i - 1][2] && e <= v.pts[i][2])) {
      if (seg.length > 1) segs.push(seg);
      seg = [];
    }
    seg.push([v.pts[i][0], v.pts[i][1]]);
  }
  if (pos && seg.length) seg.push(pos);
  if (seg.length > 1) segs.push(seg);
  return segs;
}

function gapsUpTo(v, t) {
  const out = [];
  for (let i = 1; i < v.pts.length && v.pts[i][2] <= t; i += 1) {
    if (v.gaps.some(([s, e]) => s >= v.pts[i - 1][2] && e <= v.pts[i][2])) {
      out.push([[v.pts[i - 1][0], v.pts[i - 1][1]], [v.pts[i][0], v.pts[i][1]]]);
    }
  }
  return out;
}

/** Dead reckoning after the image: from the last reported position, along the
 *  path's final heading at the last reported speed, held at the coast. */
function projectAfter(v, hoursAfter, land) {
  const p = v.pts;
  if (!p.length) return null;
  const last = p.at(-1), prev = p[Math.max(0, p.length - 3)];
  const heading = bearing(prev, last);
  const sog = v.fixes.length ? v.fixes.at(-1).sog ?? 0 : 0;
  const km = sog * 1.852;                       // km per hour
  const rad = (heading * Math.PI) / 180;
  const dLat = (Math.cos(rad) * km) / KM_PER_DEG_LAT;
  const dLon = (Math.sin(rad) * km) / (KM_PER_DEG_LAT * Math.cos((last[1] * Math.PI) / 180));
  let pos = [last[0], last[1]];
  const path = [pos];
  const steps = Math.ceil(hoursAfter * 4);
  for (let s = 1; s <= steps; s += 1) {
    const h = Math.min(hoursAfter, s / 4);
    const next = [last[0] + dLon * h, last[1] + dLat * h];
    if (land(next[0], next[1])) break;          // a ship does not sail onto land
    pos = next;
    path.push(pos);
  }
  return { pos, heading, sog, path };
}

export function shipsAt(P, tau) {
  const t = P.acq + Math.min(tau, 0) * H;
  const hb = Math.max(0, Math.round(-tau));
  const envF = P.envByH.get(hb);
  const stateOf = new Map((envF?.vessels ?? []).map((v) => [v.vessel_key, v.at_this_time]));
  const ships = [], lead = [], others = [], gaps = [], projected = [];
  for (const v of P.vessels) {
    if (tau <= 0) {
      const at = vesselAt(v, t);
      const segs = trailUpTo(v, t, at?.pos);
      (v.lead ? lead : others).push(...segs);
      gaps.push(...gapsUpTo(v, t));
      if (at) {
        ships.push({ key: v.key, lon: at.pos[0], lat: at.pos[1], cog: at.heading, sog: sogAt(v.fixes, t),
                     lead: v.lead, state: stateOf.get(v.key) === 'inside' ? 'inside' : 'outside' });
      }
    } else {
      (v.lead ? lead : others).push(...trailUpTo(v, P.acq, null));
      gaps.push(...gapsUpTo(v, P.acq));
      if (!v.pts.length || v.pts.at(-1)[2] < P.acq - 0.25 * H) continue;   // no report near the image
      const pr = projectAfter(v, tau, P.land);
      if (!pr) continue;
      projected.push(pr.path);
      ships.push({ key: v.key, lon: pr.pos[0], lat: pr.pos[1], cog: pr.heading, sog: pr.sog,
                   lead: v.lead, state: 'projected' });
    }
  }
  return { ships, trails: { lead, others }, gaps, projected };
}

// ------------------------------------------------------------ oil

function lerpParticles(a, b, k) {
  // same particles in the same order in both frames; one not yet released in
  // the earlier frame starts from the point it leaves the ship
  return b.map((q, i) => {
    const p = a[i] ?? q;
    return [lerp(p[0], q[0], k), lerp(p[1], q[1], k), q[2]];
  });
}

/** Oil at a fractional hour. Replay (before the image, named vessel only) and
 *  forecast (after) are different models; across the hour after the image one
 *  fades into the other rather than jumping. */
export function oilAt(P, tau) {
  const out = { replay: null, replayW: 0, forecast: null, forecastW: 0 };
  if (tau <= 0 && P.repByH.size) {
    const hb = -tau, e = Math.ceil(hb - 1e-9), l = Math.floor(hb + 1e-9);
    const E = P.repByH.get(e), L = P.repByH.get(l);
    if (E && L) {
      const k = e === l ? 1 : (e - hb);
      out.replay = lerpParticles(E.particles, L.particles, k).filter((p) => p[2]);
      out.replayW = 1;
    } else if (L && !E && P.releaseH !== null && -tau <= -P.releaseH) {
      // Between the release moment and the first computed hour: nothing had
      // left the ship before the release, so the oil emerges from the ship's
      // position at that moment and spreads to where the first frame has it.
      const span = -P.releaseH - l;
      const k = span > 0 ? (-P.releaseH - hb) / span : 1;
      const from = P.releasePos ?? L.particles[0];
      out.replay = L.particles.filter((p) => p[2]).map((q) => [lerp(from[0], q[0], k), lerp(from[1], q[1], k), true]);
      out.replayW = Math.min(1, 0.35 + k);
    }
  }
  if (tau > 0 && tau < 1) {
    const last = P.repByH.get(0), first = P.fcByH.get(1);
    if (last) { out.replay = last.particles.filter((p) => p[2]); out.replayW = 1 - tau; }
    if (first) { out.forecast = first.particles; out.forecastW = tau; }
  } else if (tau >= 1) {
    const a = Math.floor(tau), b = Math.min(Math.ceil(tau), P.maxH);
    const A = P.fcByH.get(a), B = P.fcByH.get(b);
    if (A && B) { out.forecast = lerpParticles(A.particles, B.particles, a === b ? 1 : tau - a); out.forecastW = 1; }
  }
  return out;
}

/** The two envelope hours either side of tau and how far between them. */
export function envelopeAt(P, tau) {
  if (tau >= 0) return null;
  const hb = -tau, near = Math.floor(hb), far = Math.ceil(hb);
  return { near: P.envByH.get(near), far: P.envByH.get(far), k: far === near ? 0 : hb - near, nearH: near, farH: far };
}

export function forecastContoursAt(P, tau) {
  return tau >= 0.5 ? P.fcByH.get(Math.min(P.maxH, Math.max(1, Math.round(tau))))?.density_contours ?? null : null;
}
