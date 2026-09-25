import { useEffect, useRef, useState } from 'react';
import {
  AttributionControl, Map as MapLibreMap, NavigationControl, ScaleControl, setWorkerUrl,
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
// MapLibre 6 computes its worker's URL at run time, which a bundler cannot
// see, so the worker was never emitted and GeoJSON layers failed to load.
// Vite bundles it here (with the chunk it imports) and hands back its URL.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import './BaseMap.css';

/**
 * Basemap for one case, framed on the scene's real coordinates.
 *
 * Two modes, chosen at run time rather than build time:
 *   imagery  Esri World Imagery through an ArcGIS Location Platform key read
 *            from VITE_ARCGIS_API_KEY (frontend/.env.local, never committed).
 *   offline  a plain sea background with the real coastline from this app's
 *            own /api/geo/coastline, so the map frames correctly with no key
 *            and no network.
 * If imagery was requested but its tiles fail (key rejected, referrer not
 * allowed, offline), the imagery layer is hidden and the map says so, rather
 * than showing a blank or broken grid.
 *
 * Basemap only: no case data is drawn yet. The dashed rectangle is the
 * scene's extent (meta.bbox), shown so the framing can be checked by eye.
 */

setWorkerUrl(workerUrl);

const KEY = import.meta.env.VITE_ARCGIS_API_KEY;
const IMAGERY_TILES = 'https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
const ESRI_ATTRIBUTION = 'Powered by <a href="https://www.esri.com" target="_blank" rel="noreferrer">Esri</a>'
  + ' | Esri, Maxar, Earthstar Geographics, and the GIS User Community';

// MapLibre paints with concrete colours, so the two themes are spelled out
// here rather than read from CSS variables.
const PALETTE = {
  light: { sea: '#dfe9f1', coast: 'rgba(0,0,0,0.55)', frame: '#007aff' },
  dark: { sea: '#15202b', coast: 'rgba(255,255,255,0.6)', frame: '#0a84ff' },
};

function currentTheme() {
  const forced = document.documentElement.dataset.theme;
  if (forced === 'light' || forced === 'dark') return forced;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function frameOf(b) {
  return {
    type: 'Feature', properties: {},
    geometry: {
      type: 'LineString',
      coordinates: [[b.min_lon, b.min_lat], [b.max_lon, b.min_lat], [b.max_lon, b.max_lat],
                    [b.min_lon, b.max_lat], [b.min_lon, b.min_lat]],
    },
  };
}

function styleFor(bbox, theme) {
  const p = PALETTE[theme];
  const sources = {
    coast: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
    frame: { type: 'geojson', data: frameOf(bbox) },
  };
  const layers = [{ id: 'sea', type: 'background', paint: { 'background-color': p.sea } }];
  if (KEY) {
    sources.imagery = {
      type: 'raster', tiles: [`${IMAGERY_TILES}?token=${encodeURIComponent(KEY)}`],
      tileSize: 256, maxzoom: 19, attribution: ESRI_ATTRIBUTION,
    };
    layers.push({ id: 'imagery', type: 'raster', source: 'imagery' });
  }
  layers.push(
    { id: 'coast', type: 'line', source: 'coast', paint: { 'line-color': p.coast, 'line-width': 1.1 } },
    { id: 'frame', type: 'line', source: 'frame',
      paint: { 'line-color': p.frame, 'line-width': 1.5, 'line-dasharray': [3, 2] } },
  );
  return { version: 8, sources, layers };
}

export default function BaseMap({ bbox, api, onMode }) {
  const el = useRef(null);
  const mapRef = useRef(null);
  const [mode, setMode] = useState(KEY ? 'imagery' : 'offline');

  useEffect(() => { onMode?.(mode); }, [mode, onMode]);

  useEffect(() => {
    if (!el.current || !bbox) return undefined;
    const bounds = [[bbox.min_lon, bbox.min_lat], [bbox.max_lon, bbox.max_lat]];
    const map = new MapLibreMap({
      container: el.current,
      style: styleFor(bbox, currentTheme()),
      bounds,
      fitBoundsOptions: { padding: 24 },
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
    });
    mapRef.current = map;
    map.touchZoomRotate.disableRotation();
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left');
    map.addControl(new AttributionControl({ compact: true }), 'bottom-right');

    // one failed imagery tile before any has loaded means the key or network is
    // the problem, not one missing tile: fall back instead of showing holes
    let imageryLoaded = false;
    map.on('sourcedata', (e) => {
      if (e.sourceId === 'imagery' && e.tile && e.tile.state === 'loaded') imageryLoaded = true;
    });
    map.on('error', (e) => {
      if (KEY && !imageryLoaded && e.sourceId === 'imagery' && map.getLayer('imagery')) {
        map.setLayoutProperty('imagery', 'visibility', 'none');
        setMode('imagery-failed');
      }
    });

    let alive = true;
    api.realCoastline()
      .then((r) => {
        if (!alive) return;
        const set = () => map.getSource('coast')?.setData({ type: 'Feature', properties: {}, geometry: r.geometry });
        if (map.isStyleLoaded()) set(); else map.once('load', set);
      })
      .catch(() => {});

    // follow the appearance control without rebuilding the map
    const repaint = () => {
      const p = PALETTE[currentTheme()];
      if (!map.getLayer('sea')) return;
      map.setPaintProperty('sea', 'background-color', p.sea);
      map.setPaintProperty('coast', 'line-color', p.coast);
      map.setPaintProperty('frame', 'line-color', p.frame);
    };
    const mo = new MutationObserver(repaint);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', repaint);

    return () => {
      alive = false;
      mo.disconnect();
      mq.removeEventListener('change', repaint);
      map.remove();
      mapRef.current = null;
    };
  }, [bbox, api]);

  return (
    <div className="basemap">
      <div ref={el} className="basemap-canvas" role="img"
           aria-label={`Map of the scene extent, ${bbox.min_lon}–${bbox.max_lon}° E, ${bbox.min_lat}–${bbox.max_lat}° N`} />
      <div className="basemap-label">
        {mode === 'imagery' && 'Real satellite imagery · case data is synthetic'}
        {mode === 'offline' && 'Offline basemap: real coastline only · add an Esri key for imagery'}
        {mode === 'imagery-failed' && 'Imagery unavailable (key rejected or offline) · showing real coastline'}
      </div>
    </div>
  );
}
