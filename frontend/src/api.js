const BASE = '/api';

async function j(path, opts) {
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${path}: ${detail}`);
  }
  return res.json();
}

export const api = {
  listIncidents: () => j('/incidents'),
  // the whole incident as one validated object (slicktrace_core.case_contract)
  case: (id) => j(`/incidents/${id}/case`),
  manifest: (id) => j(`/incidents/${id}/manifest`),
  sceneUrl: (id) => `${BASE}/incidents/${id}/scene`,
  historicalMapping: (id) => j(`/incidents/${id}/historical-mapping`),
  attribution: (id) => j(`/incidents/${id}/attribution`),
  naiveBaseline: (id) => j(`/incidents/${id}/naive-baseline`),
  tracks: (id) => j(`/incidents/${id}/tracks`),
  overview: () => j('/overview'),
  // computed frames for the replay map's time slider
  envelopeTimeline: (id) => j(`/incidents/${id}/envelope-timeline`),
  replayTimeline: (id) => j(`/incidents/${id}/replay-timeline`),
  forecastTimeline: (id) => j(`/incidents/${id}/forecast-timeline`),
  trackDisplay: (id) => j(`/incidents/${id}/track-display`),
  ensembleFan: (id) => j(`/incidents/${id}/ensemble-fan`),
  detection: (id) => j(`/incidents/${id}/detection`),
  fragility: (id) => j(`/incidents/${id}/fragility`),
  forecast: (id) => j(`/incidents/${id}/forecast`),
  coverage: (id) => j(`/incidents/${id}/coverage`),
  nextObservation: (id) => j(`/incidents/${id}/next-observation`),
  report: (id) => j(`/incidents/${id}/report`),
  reportUrl: (id) => `${BASE}/incidents/${id}/report.md`,
  dossierUrl: (id) => `${BASE}/incidents/${id}/dossier.pdf`,
  realCoastline: () => j('/geo/coastline'),
  // hours_before is the slider position: 0 = acquisition time, 24 = a full day back
  probe: (id, lon, lat, hoursBefore) =>
    j(`/incidents/${id}/probe?lon=${lon}&lat=${lat}`
      + `&hours_before=${encodeURIComponent(hoursBefore)}`),

  envelope: (id, hoursBefore) =>
    j(`/incidents/${id}/envelope?hours_before=${encodeURIComponent(hoursBefore)}`),
  ask: (id, question) => j(`/incidents/${id}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  }),
};
