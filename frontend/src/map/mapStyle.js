import { setWorkerUrl } from 'maplibre-gl';
// MapLibre 6 computes its worker's URL at run time, which a bundler cannot
// see, so the worker was never emitted and GeoJSON layers failed to load.
// Vite bundles it here (with the chunk it imports) and hands back its URL.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

setWorkerUrl(workerUrl);

/**
 * The basemap every map in the app shares.
 *
 * imagery  Esri World Imagery through an ArcGIS Location Platform key read
 *          from VITE_ARCGIS_API_KEY (frontend/.env.local, never committed).
 * offline  a plain sea with the case's real coastline, so the map frames
 *          correctly with no key and no network.
 * The imagery is dimmed slightly so overlays read against it.
 */
export const KEY = import.meta.env.VITE_ARCGIS_API_KEY;
const IMAGERY_TILES = 'https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
const ESRI_ATTRIBUTION = 'Powered by <a href="https://www.esri.com" target="_blank" rel="noreferrer">Esri</a>'
  + ' | Esri, Maxar, Earthstar Geographics, and the GIS User Community';

export const PALETTE = {
  light: { sea: '#dde8f0', coast: 'rgba(0,0,0,0.55)', frame: 'rgba(0,122,255,0.55)' },
  dark: { sea: '#131d27', coast: 'rgba(255,255,255,0.6)', frame: 'rgba(10,132,255,0.6)' },
};

export function currentTheme() {
  const forced = document.documentElement.dataset.theme;
  if (forced === 'light' || forced === 'dark') return forced;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export const EMPTY = { type: 'FeatureCollection', features: [] };

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

export function baseStyle(bbox, coastline, theme) {
  const p = PALETTE[theme];
  const sources = {
    coast: { type: 'geojson',
             data: coastline?.length > 1
               ? { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coastline } }
               : EMPTY },
    frame: { type: 'geojson', data: frameOf(bbox) },
  };
  const layers = [{ id: 'sea', type: 'background', paint: { 'background-color': p.sea } }];
  if (KEY) {
    sources.imagery = {
      type: 'raster', tiles: [`${IMAGERY_TILES}?token=${encodeURIComponent(KEY)}`],
      tileSize: 256, maxzoom: 19, attribution: ESRI_ATTRIBUTION,
    };
    layers.push({ id: 'imagery', type: 'raster', source: 'imagery',
                  paint: { 'raster-brightness-max': 0.88, 'raster-saturation': -0.15 } });
  }
  layers.push(
    { id: 'coast', type: 'line', source: 'coast', paint: { 'line-color': p.coast, 'line-width': 1 } },
    { id: 'frame', type: 'line', source: 'frame',
      paint: { 'line-color': p.frame, 'line-width': 1, 'line-dasharray': [3, 3] } },
  );
  return { version: 8, sources, layers };
}

export function repaintBase(map) {
  const p = PALETTE[currentTheme()];
  if (!map.getLayer('sea')) return;
  map.setPaintProperty('sea', 'background-color', p.sea);
  map.setPaintProperty('coast', 'line-color', p.coast);
  map.setPaintProperty('frame', 'line-color', p.frame);
}
