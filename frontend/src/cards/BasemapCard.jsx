import { lazy, Suspense } from 'react';
import { Badge, Card } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';

// MapLibre is about a megabyte: load it in its own chunk, only when this card
// renders, so the rest of the page never waits for it.
const BaseMap = lazy(() => import('../BaseMap'));

/**
 * Basemap preview for the selected case: the scene's extent on a real map,
 * before any case data is drawn on it (that arrives layer by layer in Phase 4).
 */
export default function BasemapCard({ meta, api }) {
  if (!meta) return null;
  return (
    <Card title="Scene Map" badge={<Badge>basemap preview</Badge>} caption={C.basemap}
          footnote={`Scene extent (dashed): ${meta.bbox.min_lon}–${meta.bbox.max_lon}° E, `
            + `${meta.bbox.min_lat}–${meta.bbox.max_lat}° N, ${meta.crs}. ${C.basemapGeography}`}>
      <Suspense fallback={<div className="basemap basemap-loading">Loading map…</div>}>
        <BaseMap bbox={meta.bbox} api={api} />
      </Suspense>
    </Card>
  );
}
