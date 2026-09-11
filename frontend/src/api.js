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
  manifest: (id) => j(`/incidents/${id}/manifest`),
  sceneUrl: (id) => `${BASE}/incidents/${id}/scene`,
  historicalMapping: (id) => j(`/incidents/${id}/historical-mapping`),
  attribution: (id) => j(`/incidents/${id}/attribution`),
  naiveBaseline: (id) => j(`/incidents/${id}/naive-baseline`),
  tracks: (id) => j(`/incidents/${id}/tracks`),
  fragility: (id) => j(`/incidents/${id}/fragility`),
  forecast: (id) => j(`/incidents/${id}/forecast`),
  coverage: (id) => j(`/incidents/${id}/coverage`),
  nextObservation: (id) => j(`/incidents/${id}/next-observation`),
  report: (id) => j(`/incidents/${id}/report`),
  reportUrl: (id) => `${BASE}/incidents/${id}/report.md`,
  // hours_before is the slider position: 0 = acquisition time, 24 = a full day back
  envelope: (id, hoursBefore) =>
    j(`/incidents/${id}/envelope?hours_before=${encodeURIComponent(hoursBefore)}`),
  ask: (id, question) => j(`/incidents/${id}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  }),
};
