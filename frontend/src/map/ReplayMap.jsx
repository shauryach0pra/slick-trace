import { useEffect, useRef, useState } from 'react';
import { AttributionControl, Map as MapLibreMap, Marker, NavigationControl, ScaleControl } from 'maplibre-gl';
import { Floater } from './floater';
import 'maplibre-gl/dist/maplibre-gl.css';
import { EMPTY, KEY, baseStyle, currentTheme, repaintBase } from './mapStyle';
import { envelopeAt, forecastContoursAt, hhmm, oilAt, shipsAt } from './timeline';
import { TYPE_LABEL, glyph } from './shipGlyphs';
import './ReplayMap.css';

/**
 * The scene on a real map, at one hour of the replay.
 *
 * Draws only what the card hands it for the selected hour - every layer is a
 * computed artifact - and draws it the same way at every hour, so moving the
 * slider changes the evidence, never the styling.
 *
 * Motion between hours is a visual transition between two computed states,
 * never a new state: each oil particle glides from its position at one hour to
 * its position at the next (the frames list every particle in a fixed order),
 * ships glide between their hourly positions, and the origin envelope
 * cross-fades. When a transition ends - and whenever playback is paused - what
 * is on screen is exactly the computed frame.
 */

const ENV_LEVELS = [
  { pct: 90, fill: 0.07, line: 0.35, width: 0.8, dash: [2, 2] },
  { pct: 75, fill: 0.11, line: 0.55, width: 1.0, dash: null },
  { pct: 50, fill: 0.2, line: 0.95, width: 1.6, dash: null },
];
// Oil as it looks on water: a dark brown-black film where it is thick, and a
// thin iridescent sheen - blue, violet, gold - where it thins at the edges.
// (An orange glow was a heat-map convention; oil is not orange.)
const OIL = ['interpolate', ['linear'], ['heatmap-density'],
  // lone, far-drifted particles stay faint; the sheen marks the film's edge
  0, 'rgba(0,0,0,0)', 0.1, 'rgba(90,200,255,0.07)', 0.2, 'rgba(190,120,255,0.2)',
  0.3, 'rgba(255,196,120,0.36)', 0.4, 'rgba(72,50,32,0.72)', 0.6, 'rgba(34,24,15,0.87)',
  1, 'rgba(10,7,5,0.95)'];

// Overlay ink follows the SURFACE underneath, not the UI theme: satellite
// imagery is dark in either theme; the offline sea follows the theme.
const INK = {
  dark: { trail: 'rgba(255,255,255,0.85)', gap: 'rgba(255,255,255,0.5)', slick: '#ffffff',
          coast: 'rgba(255,255,255,0.55)', outside: 0.42 },
  light: { trail: 'rgba(17,24,39,0.75)', gap: 'rgba(17,24,39,0.45)', slick: '#111827',
           coast: 'rgba(0,0,0,0.55)', outside: 0.1 },
};
const fade = (c) => c.replace(/[\d.]+\)$/, '0)');
const trailGradient = (c) => ['interpolate', ['linear'], ['line-progress'], 0, fade(c), 0.6, c, 1, c];

const fc = (features) => ({ type: 'FeatureCollection', features });
const closed = (r) => (r.length && (r[0][0] !== r.at(-1)[0] || r[0][1] !== r.at(-1)[1]) ? [...r, r[0]] : r);
const pointsFc = (pts) => fc(pts.map((p) => ({ type: 'Feature', properties: {},
                                               geometry: { type: 'Point', coordinates: [p[0], p[1]] } })));
const contourFc = (cs) => fc((cs ?? []).flatMap((c) => c.polygons.map((ring) => ({
  type: 'Feature', properties: { pct: Math.round(c.fraction * 100) },
  geometry: { type: 'Polygon', coordinates: [closed(ring)] } }))));
const linesFc = (lines, props = {}) => fc(lines.filter((l) => l.length > 1).map((l) => ({
  type: 'Feature', properties: props, geometry: { type: 'LineString', coordinates: l } })));

function addLayers(map, bbox) {
  const src = (id, extra = {}) => map.addSource(id, { type: 'geojson', data: EMPTY, ...extra });

  // outside the image footprint is dimmed, so the eye stays on the scene
  map.addSource('outside', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: {
    type: 'Polygon', coordinates: [[[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]],
      [[bbox.min_lon, bbox.min_lat], [bbox.min_lon, bbox.max_lat], [bbox.max_lon, bbox.max_lat],
       [bbox.max_lon, bbox.min_lat], [bbox.min_lon, bbox.min_lat]]] } } });
  map.addLayer({ id: 'outside', type: 'fill', source: 'outside', paint: { 'fill-color': '#000', 'fill-opacity': 0.4 } },
               'coast');

  ['areas', 'slick', 'gaps', 'lastseen', 'proj', 'fc-contours', 'oil', 'oil-fc', 'oil-stranded', 'forcing', 'fan', 'fan-ends'].forEach((id) => src(id));
  src('trails', { lineMetrics: true });
  src('trails-lead', { lineMetrics: true });
  ['a', 'b'].forEach((buf) => { src(`env-${buf}`); src(`env-pts-${buf}`); });

  const kind = ['match', ['get', 'kind'], 'fishery', '#64d2ff', 'mangrove', '#30d158', '#ffffff'];
  // an area keeps its own colour; oil reaching it adds a hazard outline
  map.addLayer({ id: 'areas-fill', type: 'fill', source: 'areas', paint: { 'fill-color': kind, 'fill-opacity': 0 } });
  map.addLayer({ id: 'areas-glow', type: 'line', source: 'areas', filter: ['==', ['get', 'hit'], true],
    paint: { 'line-color': '#ff5a36', 'line-width': 7, 'line-blur': 5, 'line-opacity': 0 } });
  map.addLayer({ id: 'areas-line', type: 'line', source: 'areas',
    paint: { 'line-color': kind, 'line-width': 1.2, 'line-opacity': 0, 'line-dasharray': [2, 2] } });
  map.addLayer({ id: 'areas-hit', type: 'line', source: 'areas', filter: ['==', ['get', 'hit'], true],
    paint: { 'line-color': '#ff6a45', 'line-width': 1.8, 'line-opacity': 0 } });

  // origin envelope: two buffers so one hour can cross-fade into the next
  for (const buf of ['a', 'b']) {
    for (const L of ENV_LEVELS) {
      map.addLayer({ id: `env-${buf}-fill-${L.pct}`, type: 'fill', source: `env-${buf}`,
        filter: ['==', ['get', 'pct'], L.pct],
        paint: { 'fill-color': '#5ac8fa', 'fill-opacity': 0, 'fill-opacity-transition': { duration: 0 } } });
    }
    map.addLayer({ id: `env-${buf}-glow`, type: 'line', source: `env-${buf}`, filter: ['==', ['get', 'pct'], 50],
      paint: { 'line-color': '#7fdcff', 'line-width': 7, 'line-blur': 6, 'line-opacity': 0,
               'line-opacity-transition': { duration: 0 } } });
    for (const L of ENV_LEVELS) {
      map.addLayer({ id: `env-${buf}-line-${L.pct}`, type: 'line', source: `env-${buf}`,
        filter: ['==', ['get', 'pct'], L.pct],
        paint: { 'line-color': '#8fe3ff', 'line-width': L.width, 'line-opacity': 0,
                 'line-opacity-transition': { duration: 0 }, ...(L.dash ? { 'line-dasharray': L.dash } : {}) } });
    }
    map.addLayer({ id: `env-pts-${buf}`, type: 'circle', source: `env-pts-${buf}`,
      paint: { 'circle-radius': 1.2, 'circle-color': '#9fe8ff', 'circle-opacity': 0,
               'circle-opacity-transition': { duration: 0 } } });
  }

  map.addLayer({ id: 'fc-fill', type: 'fill', source: 'fc-contours',
    paint: { 'fill-color': '#0a0806', 'fill-opacity': ['match', ['get', 'pct'], 50, 0.2, 75, 0.13, 0.07] } });
  map.addLayer({ id: 'fc-lines', type: 'line', source: 'fc-contours',
    paint: { 'line-color': 'rgba(228,220,255,1)', 'line-width': ['match', ['get', 'pct'], 50, 1.4, 0.9],
             'line-opacity': ['match', ['get', 'pct'], 50, 0.9, 75, 0.6, 0.38] } });
  map.addLayer({ id: 'oil-heat', type: 'heatmap', source: 'oil',
    paint: { 'heatmap-weight': 1,
             // radius grows faster than zoom, so zoomed in the oil stays one sheen
             // instead of breaking into separate particles
             'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 7, 0.9, 11, 1.2, 13, 1.0],
             'heatmap-radius': ['interpolate', ['exponential', 1.6], ['zoom'], 7, 5, 9, 10, 11, 26, 13, 60],
             'heatmap-color': OIL, 'heatmap-opacity': 0.92,
             'heatmap-opacity-transition': { duration: 300 } } });
  map.addLayer({ id: 'oil-heat-fc', type: 'heatmap', source: 'oil-fc',
    paint: { 'heatmap-weight': 1,
             // radius grows faster than zoom, so zoomed in the oil stays one sheen
             // instead of breaking into separate particles
             'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 7, 0.9, 11, 1.2, 13, 1.0],
             'heatmap-radius': ['interpolate', ['exponential', 1.6], ['zoom'], 7, 5, 9, 10, 11, 26, 13, 60],
             'heatmap-color': OIL, 'heatmap-opacity': 0.92,
             'heatmap-opacity-transition': { duration: 300 } } });
  map.addLayer({ id: 'oil-stranded', type: 'circle', source: 'oil-stranded',
    paint: { 'circle-radius': 2.8, 'circle-color': '#1a120b', 'circle-opacity': 0.95,
             'circle-stroke-color': '#ffcf85', 'circle-stroke-width': 1.3 } });

  map.addLayer({ id: 'slick-fill', type: 'fill', source: 'slick',
    paint: { 'fill-color': '#05070a', 'fill-opacity': 0, 'fill-opacity-transition': { duration: 400 } } });
  map.addLayer({ id: 'slick-glow', type: 'line', source: 'slick',
    paint: { 'line-color': '#ffffff', 'line-width': 8, 'line-blur': 7, 'line-opacity': 0,
             'line-opacity-transition': { duration: 400 } } });
  map.addLayer({ id: 'slick-line', type: 'line', source: 'slick',
    paint: { 'line-color': '#ffffff', 'line-width': 1, 'line-opacity': 0.35 } });
  map.addLayer({ id: 'slick-ants', type: 'line', source: 'slick',
    paint: { 'line-color': '#ffffff', 'line-width': 1.6, 'line-opacity': 0.7, 'line-dasharray': ANTS[0] } });

  // the uniform current the model advects with, and each candidate's six-variant drift
  map.addLayer({ id: 'forcing-arrows', type: 'line', source: 'forcing', layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': 'rgba(210,225,240,0.42)', 'line-width': 1.2 } });
  map.addLayer({ id: 'fan-lines', type: 'line', source: 'fan', layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': ['case', ['get', 'lead'], '#5ac8fa', 'rgba(220,226,235,1)'],
             'line-width': ['case', ['get', 'lead'], 1.5, 1.1],
             'line-opacity': ['case', ['get', 'lead'], 0.75, 0.35] } });
  map.addLayer({ id: 'fan-ends', type: 'circle', source: 'fan-ends',
    paint: { 'circle-radius': ['case', ['get', 'lead'], 2.6, 2], 'circle-color': ['case', ['get', 'lead'], '#5ac8fa', 'rgba(220,226,235,0.7)'],
             'circle-stroke-color': 'rgba(0,0,0,0.5)', 'circle-stroke-width': 0.5 } });
  map.addLayer({ id: 'fan-hit', type: 'line', source: 'fan', paint: { 'line-color': '#000', 'line-width': 10, 'line-opacity': 0 } });
  map.addLayer({ id: 'proj', type: 'line', source: 'proj',
    paint: { 'line-color': 'rgba(255,255,255,0.55)', 'line-width': 1.2, 'line-dasharray': [2, 2] } });
  map.addLayer({ id: 'gaps', type: 'line', source: 'gaps', layout: { 'line-cap': 'round' },
    paint: { 'line-color': 'rgba(255,255,255,0.5)', 'line-width': 1.6, 'line-dasharray': [0.1, 2.4] } });
  map.addLayer({ id: 'gaps-hit', type: 'line', source: 'gaps', paint: { 'line-color': '#000', 'line-width': 14, 'line-opacity': 0 } });
  map.addLayer({ id: 'lastseen', type: 'circle', source: 'lastseen',
    paint: { 'circle-radius': 7, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': 'rgba(210,216,226,0.75)',
             'circle-stroke-width': 1.2 } });
  map.addLayer({ id: 'lastseen-dot', type: 'circle', source: 'lastseen',
    paint: { 'circle-radius': 1.8, 'circle-color': 'rgba(210,216,226,0.9)' } });
  map.addLayer({ id: 'trails', type: 'line', source: 'trails', layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-width': 1.3, 'line-gradient': trailGradient(INK.dark.trail) } });
  map.addLayer({ id: 'trails-lead', type: 'line', source: 'trails-lead', layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-width': 2.6, 'line-gradient': trailGradient('rgba(10,132,255,0.95)') } });
}

function paintInk(map, surface) {
  const ink = INK[surface];
  if (!map.getLayer('trails')) return;
  map.setPaintProperty('trails', 'line-gradient', trailGradient(ink.trail));
  map.setPaintProperty('gaps', 'line-color', ink.gap);
  map.setPaintProperty('proj', 'line-color', ink.gap);
  map.setPaintProperty('slick-line', 'line-color', ink.slick);
  map.setPaintProperty('coast', 'line-color', ink.coast);
  map.setPaintProperty('outside', 'fill-opacity', ink.outside);
}

function shipElement(key, type) {
  const el = document.createElement('div');
  el.className = 'ship';
  el.dataset.type = type ?? 'other';
  el.innerHTML = `<div class="ship-rot"><div class="ship-wake"></div>${glyph(type)}</div><div class="ship-label"></div>`;
  el.title = key;
  return el;
}

function labelAnchor(contours, pct) {
  const c = (contours ?? []).find((x) => Math.round(x.fraction * 100) === pct);
  const ring = c?.polygons?.reduce((a, r) => (r.length > (a?.length ?? 0) ? r : a), null);
  if (!ring?.length) return null;
  return ring.reduce((a, p) => (p[1] > a[1] ? p : a), ring[0]);     // northernmost vertex
}

// envelope opacity by weight, set directly each frame (no style transition)
function envWeight(map, buf, w, ctx) {
  for (const L of ENV_LEVELS) {
    paintIf(map, ctx, `env-${buf}-fill-${L.pct}`, 'fill-opacity', L.fill * w);
    paintIf(map, ctx, `env-${buf}-line-${L.pct}`, 'line-opacity', L.line * w);
  }
  paintIf(map, ctx, `env-${buf}-glow`, 'line-opacity', 0.35 * w);
  paintIf(map, ctx, `env-pts-${buf}`, 'circle-opacity', 0.35 * w);
}

// marching ants on the observed slick's edge (the familiar MapLibre dash sequence)
const ANTS = [[0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0],
              [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5]];

const esc = (x) => String(x).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const STATUS_TEXT = { candidate: 'candidate: inside the origin envelope at some tested hour',
                      excluded: 'excluded: track present throughout, never inside the envelope',
                      unassessed: 'unassessed: no track data for part of the window' };

/** The vessel popover's content at tau: what the artifacts say about it now. */
function vesselCard(key, P, S, tau) {
  const ship = S.ships.find((x) => x.key === key), ls = S.lastSeen.find((x) => x.key === key);
  const v = P.vessels.find((x) => x.key === key), inf = P.info[key] ?? {};
  const type = v?.type && v.type !== 'other' ? v.type : null;
  let pos = null, now;
  if (ship) {
    pos = [ship.lon, ship.lat];
    now = ship.state === 'projected' ? 'projected from its last course and speed (no AIS after the image)'
      : ship.state === 'inside' ? 'inside the origin envelope' : 'outside the origin envelope';
  } else if (ls) {
    pos = [ls.lon, ls.lat];
    now = `AIS off since ${hhmm(ls.since)} UTC: shown at its last reported position`;
  } else {
    return null;                                    // no report at this hour: nothing to point at
  }
  const when = hhmm(P.acq + tau * 3600e3);
  const row = (k, val) => `<div class="rpop-row"><span>${k}</span><span>${val}</span></div>`;
  const rank = inf.replayRank ? `#${inf.replayRank} of ${inf.replayOf} · mean IoU ${inf.iou.toFixed(3)}` : 'not replayed (not a candidate)';
  const html = `<div class="rpop-head">${glyph(v?.type)}<div><div class="rpop-key">${esc(key)}</div>`
    + `<div class="rpop-type">${type ? `${esc(type)} · AIS static data (synthetic)` : 'type not reported'}</div></div>`
    + `${v?.lead ? '<span class="rpop-lead">leading candidate</span>' : ''}</div>`
    + row(`At ${when} UTC`, esc(now))
    + row('Position', `${pos[1].toFixed(4)}° N, ${pos[0].toFixed(4)}° E`)
    + (ship?.sog != null && ship.state !== 'projected' ? row('Reported', `${ship.sog} kn, course ${Math.round(ship.cog)}°`) : '')
    + row('Historical filtering', esc(STATUS_TEXT[inf.status] ?? inf.status ?? '—'))
    + row('Forward replay', esc(rank))
    + (inf.naiveRank ? row('Proximity baseline', `#${inf.naiveRank} of ${inf.naiveOf} nearest at the image`) : '')
    + (() => {
      // recorded internal AIS gaps so far (track_display.json) - listed here because
      // a slow vessel's gap can be shorter on screen than its own symbol
      const T = P.acq + Math.min(tau, 0) * 3600e3;
      const gs = (v?.gaps ?? []).filter(([st]) => st < T);
      return gs.length ? row('AIS gaps', gs.map(([st, en]) => `${hhmm(st)}–${hhmm(en)} UTC`).join(', ')
        + '<br><span class="rpop-note">No position reported; these hours count neither for nor against this vessel.</span>') : '';
    })()
    + `<button type="button" class="rpop-link" data-act="rank">Show in ${inf.replayRank ? 'forward-replay' : 'proximity'} ranking →</button>`;
  return { pos, html };
}

function updatePopover(map, P, S, tau, ctx) {
  const key = ctx.selected.current;
  const pop = ctx.popup.current;
  if (!key || !pop) return;
  const card = vesselCard(key, P, S, tau);
  if (!card) { if (pop.el) pop.el.style.visibility = 'hidden'; return; }
  pop.setHTML(card.html).at(card.pos);
}

// ---- drawing at a fractional hour (module scope: explicit about what it touches)

// Only touch a source or paint value when it actually changes: re-sending every
// layer on every animation frame starved the renderer during playback.
function setDataIf(map, ctx, id, key, build) {
  if (ctx.cache[id] === key) return;
  ctx.cache[id] = key;
  map.getSource(id)?.setData(build());
}
function paintIf(map, ctx, layer, prop, value) {
  const k = `${layer}|${prop}`;
  const v = typeof value === 'number' ? Math.round(value * 1000) / 1000 : JSON.stringify(value);
  if (ctx.cache[k] === v) return;
  ctx.cache[k] = v;
  map.setPaintProperty(layer, prop, value);
}

function drawScene(map, P, tau, prevTau, ctx) {
  // origin envelope: the two computed hours either side, cross-faded
  const env = envelopeAt(P, tau);
  const load = (buf, frame, h) => {
    if (ctx.envLoaded.current[buf] === h) return;
    ctx.envLoaded.current[buf] = h;
    map.getSource(`env-${buf}`).setData(frame?.density_contours ? contourFc(frame.density_contours) : EMPTY);
    map.getSource(`env-pts-${buf}`).setData(frame?.particles ? pointsFc(frame.particles) : EMPTY);
  };
  if (env) {
    load('a', env.near, env.nearH);
    load('b', env.far, env.farH);
    // the image-time envelope (hour 0) is the slick itself: fade it out as tau reaches 0
    envWeight(map, 'a', env.nearH === 0 ? 0 : 1 - env.k, ctx);
    envWeight(map, 'b', env.k, ctx);
  } else {
    envWeight(map, 'a', 0, ctx); envWeight(map, 'b', 0, ctx);
  }
  const labelFrame = env ? (env.k < 0.5 && env.nearH > 0 ? env.near : env.far) : null;
  for (const pct of [50, 90]) {
    const at = labelFrame ? labelAnchor(labelFrame.density_contours, pct) : null;
    let m = ctx.envLabels.current[pct];
    if (!m) {
      const node = document.createElement('div');
      node.className = `env-label is-${pct}`;
      node.textContent = `${pct}%`;
      m = new Marker({ element: node, anchor: 'bottom' }).setLngLat([0, 0]).addTo(map);
      ctx.envLabels.current[pct] = m;
    }
    m.getElement().classList.toggle('is-hidden', !at);
    if (at) m.setLngLat(at);
  }

  // sensitive areas matter after the image: they fade in with the forecast and
  // light up from the hour the forecast first reaches them (forecast_result)
  const aw = Math.max(0, Math.min(1, tau));
  const hits = (ctx.areas ?? []).map((a) => {
    const h = P.contactH[a.name];
    return h !== null && h !== undefined && tau >= h;
  });
  setDataIf(map, ctx, 'areas', hits.join(','), () => fc((ctx.areas ?? []).map((a, i) => ({ type: 'Feature',
    properties: { kind: a.kind, name: a.name, hit: hits[i] },
    geometry: { type: 'Polygon', coordinates: [closed(a.polygon)] } }))));
  paintIf(map, ctx, 'areas-fill', 'fill-opacity', ['*', aw, ['case', ['get', 'hit'], 0.22, 0.12]]);
  paintIf(map, ctx, 'areas-line', 'line-opacity', 0.9 * aw);
  paintIf(map, ctx, 'areas-glow', 'line-opacity', 0.6 * aw);
  paintIf(map, ctx, 'areas-hit', 'line-opacity', aw);
  (ctx.areas ?? []).forEach((a, i) => {
    const m = ctx.areaLabels.current[a.name];
    if (!m) return;
    const node = m.getElement();
    node.classList.toggle('is-hidden', aw <= 0.05);
    node.classList.toggle('is-hit', hits[i]);
    const text = `${a.kind === 'fishery' ? 'Fishing ground' : 'Mangrove fringe'} · synthetic`
      + (hits[i] ? ` · oil from +${P.contactH[a.name]} h` : '');
    if (node.textContent !== text) node.textContent = text;
  });

  // oil: the replayed release before the image, the forecast after, faded across
  const oil = oilAt(P, tau);
  map.getSource('oil').setData(oil.replay ? pointsFc(oil.replay) : EMPTY);
  paintIf(map, ctx, 'oil-heat', 'heatmap-opacity', 0.92 * oil.replayW);
  const fcPts = oil.forecast ?? [];
  map.getSource('oil-fc').setData(pointsFc(fcPts.filter((p) => !p[2])));
  map.getSource('oil-stranded').setData(pointsFc(fcPts.filter((p) => p[2])));
  paintIf(map, ctx, 'oil-heat-fc', 'heatmap-opacity', 0.92 * oil.forecastW);
  paintIf(map, ctx, 'oil-stranded', 'circle-opacity', 0.95 * oil.forecastW);
  setDataIf(map, ctx, 'fc-contours', tau >= 0.5 ? Math.round(tau) : -1, () => contourFc(forecastContoursAt(P, tau)));

  // the observed image: emphasis around the image hour
  const strong = Math.abs(tau) < 0.5;
  paintIf(map, ctx, 'slick-fill', 'fill-opacity', strong ? 0.3 : 0.07);
  paintIf(map, ctx, 'slick-glow', 'line-opacity', strong ? 0.55 : 0);
  paintIf(map, ctx, 'slick-line', 'line-opacity', strong ? 0.9 : 0.35);
  paintIf(map, ctx, 'slick-ants', 'line-width', strong ? 2.2 : 1.6);
  paintIf(map, ctx, 'slick-ants', 'line-opacity', strong ? 1 : 0.7);
  const wasStrong = prevTau !== null && Math.abs(prevTau) < 0.5;
  if (strong && prevTau !== null && !wasStrong) scan(map, ctx);

  // the release: a burst at the ship the moment it happens
  if (P.releaseH !== null && P.releasePos && prevTau !== null && prevTau < P.releaseH && tau >= P.releaseH
      && tau - prevTau < 2) burst(map, P.releasePos);

  // ships, trails and projected tracks
  const S = shipsAt(P, tau);
  map.getSource('trails').setData(linesFc(S.trails.others));
  map.getSource('trails-lead').setData(linesFc(S.trails.lead));
  setDataIf(map, ctx, 'gaps', S.gaps.length, () => fc(S.gaps.map((g) => ({ type: 'Feature',
    properties: { key: g.key, start: g.start, end: g.end }, geometry: { type: 'LineString', coordinates: g.line } }))));
  setDataIf(map, ctx, 'lastseen', S.lastSeen.map((l) => l.key).join(','), () => fc(S.lastSeen.map((l) => ({ type: 'Feature',
    properties: { key: l.key, since: l.since, until: l.until }, geometry: { type: 'Point', coordinates: [l.lon, l.lat] } }))));
  setDataIf(map, ctx, 'proj', tau > 0 ? Math.round(tau * 12) : -1, () => linesFc(S.projected));
  placeShips(map, S.ships, ctx);
  updatePopover(map, P, S, tau, ctx);
}

function scan(map, ctx) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const box = ctx.el.current?.parentElement?.querySelector('.rmap-sweep');
  if (!box) return;
  const nw = map.project([ctx.bbox.min_lon, ctx.bbox.max_lat]), se = map.project([ctx.bbox.max_lon, ctx.bbox.min_lat]);
  Object.assign(box.style, { left: `${nw.x}px`, top: `${nw.y}px`, width: `${se.x - nw.x}px`, height: `${se.y - nw.y}px` });
  box.classList.remove('is-on'); void box.offsetWidth; box.classList.add('is-on');
  map.setPaintProperty('frame', 'line-color', '#ffffff');
  map.setPaintProperty('frame', 'line-dasharray', [1, 0]);
  setTimeout(() => {
    if (ctx.mapRef.current !== map) return;
    repaintBase(map);
    map.setPaintProperty('frame', 'line-dasharray', [3, 3]);
  }, 1400);
}

function burst(map, at) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const node = document.createElement('div');
  node.className = 'release-burst';
  node.innerHTML = '<span></span><span></span><em>release</em>';
  const m = new Marker({ element: node }).setLngLat(at).addTo(map);
  setTimeout(() => m.remove(), 1900);
}

function placeShips(map, ships, ctx) {
  const ms = ctx.markers.current;
  const seen = new Set();
  for (const s of ships) {
    seen.add(s.key);
    let m = ms.get(s.key);
    if (!m) {
      const node = shipElement(s.key, s.type);
      node.tabIndex = 0;
      node.setAttribute('role', 'button');
      node.setAttribute('aria-label', `Vessel ${s.key}: show details`);
      const open = (e) => { e.stopPropagation(); ctx.select(s.key); };
      node.addEventListener('click', open);
      node.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(e); } });
      m = { el: node, marker: new Marker({ element: node }).setLngLat([s.lon, s.lat]).addTo(map), visible: false };
      ms.set(s.key, m);
    }
    if (!m.visible) {                                // AIS signal starts: one ping
      m.el.classList.remove('is-new'); void m.el.offsetWidth; m.el.classList.add('is-new');
    }
    m.visible = true;
    m.el.style.display = '';
    m.marker.setLngLat([s.lon, s.lat]);
    if (m.el.dataset.state !== s.state) m.el.dataset.state = s.state;
    m.el.classList.toggle('is-lead', s.lead);
    m.el.style.setProperty('--cog', `${(s.cog ?? 0).toFixed(1)}deg`);
    m.el.style.setProperty('--wake', String(Math.max(0, Math.min(1, ((s.sog ?? 0) - 0.5) / 7))));
    const text = s.lead ? `${s.key} · leading candidate${s.state === 'projected' ? ' · projected' : ''}` : '';
    const lbl = m.el.querySelector('.ship-label');
    if (lbl.textContent !== text) lbl.textContent = text;
    m.el.title = `${s.key} · ${TYPE_LABEL[s.type] ?? TYPE_LABEL.other}${s.state === 'projected' ? ': projected from last course and speed, not observed'
      : s.state === 'inside' ? ': inside the origin envelope' : ''}${s.sog != null ? ` · ${s.sog} kn reported` : ''}`;
  }
  ms.forEach((m, key) => { if (!seen.has(key)) { m.el.style.display = 'none'; m.visible = false; } });
}

/** The model's forcing: one uniform current, and the six variants that perturb it. */
function ForcingRose({ forcing }) {
  // the model's forcing as a small chip: an arrow along the current, and its speed
  const kn = Math.hypot(forcing.u_ms, forcing.v_ms) * 1.943844;
  const bearing = Math.round(((Math.atan2(forcing.u_ms, forcing.v_ms) * 180) / Math.PI + 360) % 360);
  return (
    <div className="rmap-forcing" title={`Uniform current: ${kn.toFixed(2)} kn toward ${bearing}°, the same everywhere; 6 forcing variants perturb it`}
         aria-label={`Model forcing: one uniform current, ${kn.toFixed(2)} knots toward ${bearing} degrees`}>
      <svg viewBox="0 0 16 16" aria-hidden="true" style={{ transform: `rotate(${bearing}deg)` }}><path d="M8 13V3M4.5 6.5 8 3l3.5 3.5" /></svg>
      {kn.toFixed(2)} kn
    </div>
  );
}

// the first map appears at once; maps created on a case switch wait for the transition
const MAP_DEFER_MS = 420;
let firstMap = true;

export default function ReplayMap({ bbox, coastline, areas, slick, slickInfo, timeline, tau, label, onPick, onMode, onShowRanking, fan }) {
  const el = useRef(null);
  const mapRef = useRef(null);
  const markers = useRef(new Map());
  const envLabels = useRef({});
  const areaLabels = useRef({});
  const selected = useRef(null);       // the vessel whose popover is open
  const popup = useRef(null);
  const popBody = useRef(null);
  const [sel, setSel] = useState(0);   // bumps a redraw when the selection changes
  const rankRef = useRef(onShowRanking);
  useEffect(() => { rankRef.current = onShowRanking; }, [onShowRanking]);
  const tlRef = useRef(timeline);
  useEffect(() => { tlRef.current = timeline; }, [timeline]);
  const slickRef = useRef(slickInfo);
  useEffect(() => { slickRef.current = slickInfo; }, [slickInfo]);
  const [hidden, setHidden] = useState({});
  const [layersOpen, setLayersOpen] = useState(false);
  const envLoaded = useRef({ a: null, b: null });
  const lastTau = useRef(null);
  const cache = useRef({});
  const lastDraw = useRef(0);
  const raf = useRef(0);
  const pickRef = useRef(onPick);
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState(KEY ? 'imagery' : 'offline');
  const modeRef = useRef(mode);
  useEffect(() => { pickRef.current = onPick; }, [onPick]);

  useEffect(() => {
    modeRef.current = mode;
    onMode?.(mode);
    if (mapRef.current) paintInk(mapRef.current, mode === 'imagery' ? 'dark' : currentTheme());
  }, [mode, onMode]);

  // one map per case, framed on the scene
  useEffect(() => {
    if (!el.current || !bbox) return undefined;
    // Creating a map compiles its WebGL programs and tearing one down is costly:
    // done in the same instant as a case switch, it froze the transition. The
    // first map is created at once; on a switch the new one is created just after
    // the new case has risen into focus, and the old one is removed after the fade.
    let teardown = null;
    const start = () => {
    const map = new MapLibreMap({
      container: el.current,
      style: baseStyle(bbox, coastline, currentTheme()),
      bounds: [[bbox.min_lon, bbox.min_lat], [bbox.max_lon, bbox.max_lat]],
      fitBoundsOptions: { padding: 20 },
      attributionControl: false, dragRotate: false, pitchWithRotate: false,
    });
    mapRef.current = map;
    map.touchZoomRotate.disableRotation();
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left');
    map.addControl(new AttributionControl({ compact: true }), 'bottom-right');

    let imageryLoaded = false;
    map.on('sourcedata', (e) => {
      if (e.sourceId === 'imagery' && e.tile && e.tile.state === 'loaded') imageryLoaded = true;
    });
    map.on('error', (e) => {
      if (KEY && !imageryLoaded && e.sourceId === 'imagery' && map.getLayer('imagery')) {
        map.setLayoutProperty('imagery', 'visibility', 'none');
        setMode('imagery-failed');
        return;
      }
      console.error('map:', e.error?.message ?? e);          // never fail silently
    });

    // Ships are symbols, not to scale (no vessel dimensions are known, and at
    // scene zoom one pixel is ~200 m): readable at scene zoom, larger zoomed in.
    let baseZoom = null;
    const sizeShips = () => {
      if (baseZoom === null) baseZoom = map.getZoom();
      const len = Math.max(16, Math.min(52, 20 * 1.4 ** (map.getZoom() - baseZoom)));
      el.current?.style.setProperty('--ship-len', `${len.toFixed(1)}px`);
    };
    map.on('load', () => {
      addLayers(map, bbox);
      paintInk(map, KEY ? 'dark' : currentTheme());
      sizeShips();
      setReady(true);
    });
    map.on('zoom', sizeShips);
    map.on('click', (e) => {
      popup.current?.remove();                        // a click on open water closes the popovers
      slickF?.remove();
      pickRef.current?.({ lon: e.lngLat.lng, lat: e.lngLat.lat });
    });
    // hover labels: recorded AIS gaps and last-seen positions, from track_display.json
    let hintF = null, slickF = null;          // floating popovers, above the whole app
    const hint = (layer, text) => {
      map.on('mousemove', layer, (e) => {
        map.getCanvas().style.cursor = 'help';
        if (!hintF) hintF = new Floater(map, { className: 'rpop is-hint', interactive: false, onClose: () => { hintF = null; } });
        hintF.setHTML(text(e.features[0].properties)).at(e.lngLat);
      });
      map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = ''; hintF?.remove(); });
    };
    const hrs = (p) => Math.round(((p.end ?? p.until) - (p.start ?? p.since)) / 360e3) / 10;
    hint('gaps-hit', (p) => `<strong>AIS gap ${hhmm(p.start)}–${hhmm(p.end)} UTC (${hrs(p)} h)</strong><br>`
      + 'No position was reported. These hours count neither for nor against this vessel.');
    hint('fan-hit', (p) => `<strong>${esc(p.vessel)} · ${esc(p.variant)}</strong><br>Fit under this forcing variant: IoU ${p.iou}`
      + (p.won ? '. The best of all candidates under this variant.' : '.') + '<br>One of the six runs forward replay scored.');
    hint('lastseen', (p) => `<strong>AIS off since ${hhmm(p.since)} UTC</strong><br>Last reported position; `
      + `reporting resumes at ${hhmm(p.until)} UTC. No position is shown for the hours between.`);
    // the observed slick: what the detection artifact says about it
    map.on('click', 'slick-fill', (e) => {
      const s = slickRef.current;
      if (!s) return;
      slickF?.remove();
      slickF = new Floater(map, { className: 'rpop', closeButton: true, onClose: () => { slickF = null; } });
      slickF.setHTML(`<div class="rpop-key">Observed slick</div><div class="rpop-type">${esc(s.when)}</div>`
          + `<div class="rpop-row"><span>Area</span><span>${esc(s.area)}</span></div>`
          + `<div class="rpop-row"><span>Detector</span><span>${esc(s.detector)}</span></div>`
          + `<div class="rpop-row"><span>Outline vs generator mask</span><span>${esc(s.iou)}</span></div>`)
          .at(e.lngLat);
    });
    map.on('mouseenter', 'slick-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'slick-fill', () => { map.getCanvas().style.cursor = ''; });

    const repaint = () => { repaintBase(map); paintInk(map, modeRef.current === 'imagery' ? 'dark' : currentTheme()); };
    const mo = new MutationObserver(repaint);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', repaint);

    const ms = markers.current;
    const labels = envLabels.current;
    return () => {
      cancelAnimationFrame(raf.current);
      popup.current?.remove();
      popup.current = null;
      selected.current = null;
      hintF?.remove();
      slickF?.remove();
      mo.disconnect();
      mq.removeEventListener('change', repaint);
      ms.forEach(({ marker }) => marker.remove());
      ms.clear();
      Object.values(labels).forEach((m) => m.remove());
      envLabels.current = {};
      Object.values(areaLabels.current).forEach((m) => m.remove());
      areaLabels.current = {};
      envLoaded.current = { a: null, b: null };
      lastTau.current = null;
      cache.current = {};
      setTimeout(() => map.remove(), MAP_DEFER_MS + 300);
      mapRef.current = null;
      setReady(false);
    };
    };
    const delay = firstMap ? 0 : MAP_DEFER_MS;
    firstMap = false;
    const id = setTimeout(() => { teardown = start(); }, delay);
    return () => { clearTimeout(id); teardown?.(); };
  }, [bbox, coastline]);

  // layer toggle: map layers by group, markers by a class on the map
  const GROUPS = {
    envelope: ['a', 'b'].flatMap((b) => [...ENV_LEVELS.flatMap((L) => [`env-${b}-fill-${L.pct}`, `env-${b}-line-${L.pct}`]),
                                         `env-${b}-glow`, `env-pts-${b}`]),
    oil: ['oil-heat', 'oil-heat-fc', 'oil-stranded'],
    vessels: ['trails', 'trails-lead', 'gaps', 'gaps-hit', 'lastseen', 'lastseen-dot', 'proj'],
    fan: ['fan-lines', 'fan-ends', 'fan-hit'],
    forcing: ['forcing-arrows'],
    areas: ['areas-fill', 'areas-glow', 'areas-line', 'areas-hit'],
    forecast: ['fc-fill', 'fc-lines'],
  };
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    for (const [g, ids] of Object.entries(GROUPS)) {
      for (const id of ids) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', hidden[g] ? 'none' : 'visible');
    }
  }, [ready, hidden]);   // eslint-disable-line react-hooks/exhaustive-deps

  // open the popover for a vessel; it follows the vessel and updates as time moves
  function select(key) {
    const map = mapRef.current;
    if (!map) return;
    popup.current?.remove();
    const f = new Floater(map, { className: 'rpop', closeButton: true,
      onClose: () => { if (popup.current === f) { popup.current = null; selected.current = null; } } });
    const node = f.body;
    node.classList.add('rpop-body');
    node.addEventListener('click', (e) => {
      if (!e.target.closest('[data-act="rank"]')) return;
      const inf = tlRef.current?.info?.[key] ?? {};
      rankRef.current?.(key, inf.replayRank ? 'replay' : 'naive');
    });
    popBody.current = node;
    popup.current = f;
    selected.current = key;
    setSel((n) => n + 1);
  }
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') popup.current?.remove(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  // marching ants on the observed slick's edge
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined;
    let i = 0;
    const id = setInterval(() => {
      if (mapRef.current !== map || !map.getLayer('slick-ants')) return;
      i = (i + 1) % ANTS.length;
      map.setPaintProperty('slick-ants', 'line-dasharray', ANTS[i]);
    }, 100);
    return () => clearInterval(id);
  }, [ready]);

  // the forcing field and the ensemble fan, from ensemble_fan.json
  const fanOn = tau <= 0;
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const f = fan?.forcing;
    const arrows = [];
    if (f) {
      // one uniform current: the same arrow at every grid point (direction from u, v)
      const sp = Math.hypot(f.u_ms, f.v_ms) || 1, ux = f.u_ms / sp, vy = f.v_ms / sp;
      const W = bbox.max_lon - bbox.min_lon, Hh = bbox.max_lat - bbox.min_lat, L = Math.min(W, Hh) * 0.055;
      const k = Math.cos(((bbox.min_lat + bbox.max_lat) / 2) * Math.PI / 180);
      for (let i = 1; i <= 5; i += 1) {
        for (let j = 1; j <= 5; j += 1) {
          const x = bbox.min_lon + (W * i) / 6, y = bbox.min_lat + (Hh * j) / 6;
          const tx = x + (ux * L) / k, ty = y + vy * L;
          const hx = -ux * 0.35 * L, hy = -vy * 0.35 * L, c = Math.cos(0.5), s = Math.sin(0.5);
          arrows.push([[x, y], [tx, ty]],
            [[tx, ty], [tx + (hx * c - hy * s) / k, ty + (hx * s + hy * c)]],
            [[tx, ty], [tx + (hx * c + hy * s) / k, ty + (-hx * s + hy * c)]]);
        }
      }
    }
    map.getSource('forcing')?.setData(fc(arrows.map((a) => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: a } }))));
    const lines = [], ends = [];
    if (fan && fanOn) {
      const lead = fan.named ? fan.top_candidate_id : null;
      for (const c of fan.candidates.slice(0, 3)) {
        for (const m of c.members) {
          if (m.path.length < 1) continue;
          const props = { lead: c.vessel_key === lead, vessel: c.vessel_key, variant: m.variant, iou: m.iou, won: m.won };
          if (m.path.length > 1) lines.push({ type: 'Feature', properties: props, geometry: { type: 'LineString', coordinates: m.path } });
          ends.push({ type: 'Feature', properties: props, geometry: { type: 'Point', coordinates: m.path[m.path.length - 1] } });
        }
      }
    }
    map.getSource('fan')?.setData(fc(lines));
    map.getSource('fan-ends')?.setData(fc(ends));
  }, [ready, fan, fanOn, bbox]);

  // things that do not change with time
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    for (const a of areas ?? []) {
      if (areaLabels.current[a.name]) continue;
      const top = a.polygon.reduce((p, q) => (q[1] > p[1] ? q : p), a.polygon[0]);
      const node = document.createElement('div');
      node.className = `area-label is-${a.kind} is-hidden`;
      areaLabels.current[a.name] = new Marker({ element: node, anchor: 'bottom' }).setLngLat(top).addTo(map);
    }
    map.getSource('slick').setData(slick?.length > 2
      ? fc([{ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [closed(slick)] } }]) : EMPTY);
  }, [ready, areas, slick]);

  // draw the scene at tau - at most once per animation frame
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !timeline) return undefined;
    cancelAnimationFrame(raf.current);
    const at = tau;
    const run = (now) => {
      if (mapRef.current !== map) return;
      // about 30 frames a second is smooth here and leaves the renderer headroom;
      // a whole computed hour is always drawn at once
      if (now - lastDraw.current < 30 && Math.abs(at - Math.round(at)) > 1e-6) {
        raf.current = requestAnimationFrame(run);
        return;
      }
      lastDraw.current = now;
      drawScene(map, timeline, at, lastTau.current, { el, mapRef, markers, envLabels, envLoaded, bbox, cache: cache.current, areas, areaLabels,
        selected, popup, popBody, select });
      lastTau.current = at;
    };
    raf.current = requestAnimationFrame(run);
    return () => cancelAnimationFrame(raf.current);
  }, [ready, timeline, tau, bbox, areas, sel]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={`rmap${Object.entries(hidden).filter(([, v]) => v).map(([k]) => ` hide-${k}`).join('')}`}>
      <div ref={el} className="rmap-canvas" role="img"
           aria-label={`Map of the scene, ${bbox.min_lon}–${bbox.max_lon}° E, ${bbox.min_lat}–${bbox.max_lat}° N. ${label}`} />
      {(() => {
        // "Observed · the image: …" becomes a coloured tag and its description, on one line
        const [head, ...rest] = String(label ?? '').split(' · ');
        const text = rest.join(' · ');
        const tone = /^observed/i.test(head) ? 'observed' : 'modelled';
        return (
          <div className="rmap-label" title={label}>
            <span className={`rmap-tag is-${tone}`}><i />{head}</span>
            {text && <span className="rmap-phase">{text.charAt(0).toUpperCase() + text.slice(1)}</span>}
            <span className="rmap-base">
              {mode === 'imagery' && 'real imagery · synthetic case'}
              {mode === 'offline' && 'offline coastline'}
              {mode === 'imagery-failed' && 'imagery unavailable'}
            </span>
          </div>
        );
      })()}
      <div className="rmap-sweep" aria-hidden="true"><span /></div>
      {fan?.forcing && !hidden.forcing && <ForcingRose forcing={fan.forcing} />}
      <div className="rmap-layers">
        <button type="button" className="rmap-layers-btn" aria-expanded={layersOpen}
                onClick={() => setLayersOpen((o) => !o)} title="Layers">
          <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><path d="M8 2 1.5 5.5 8 9l6.5-3.5L8 2Zm-6.5 6L8 11.5 14.5 8M1.5 10.5 8 14l6.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" /></svg>
        </button>
        {layersOpen && (
          <div className="rmap-layers-pop" role="group" aria-label="Map layers">
            {[['envelope', 'Origin envelope'], ['oil', 'Oil'], ['vessels', 'Vessels and tracks'],
              ['areas', 'Sensitive areas'], ['forecast', 'Forecast contours'], ['fan', 'Ensemble drift'],
              ['forcing', 'Forcing current']].map(([k, name]) => (
              <label key={k}><input type="checkbox" checked={!hidden[k]}
                onChange={() => setHidden((h) => ({ ...h, [k]: !h[k] }))} />{name}</label>
            ))}
          </div>
        )}
      </div>
      {Math.abs(tau) < 0.5 && <div className="rmap-acq" aria-hidden="true">Radar image acquired</div>}
    </div>
  );
}
