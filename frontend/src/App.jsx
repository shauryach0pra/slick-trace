import { useEffect, useState } from 'react';
import './dashboard.css';
import { api } from './api';
import CaseSwitcher from './CaseSwitcher';
import VerdictBand from './VerdictBand';
import ScenePanel from './ScenePanel';
import RankingPanel from './RankingPanel';
import TimeSliderMap from './TimeSliderMap';
import FragilityPanel from './FragilityPanel';
import AskConsole from './AskConsole';
import ForecastPanel from './ForecastPanel';
import CoveragePanel from './CoveragePanel';
import NextObservationPanel from './NextObservationPanel';

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [incidentId, setIncidentId] = useState('case_0001');
  const [manifest, setManifest] = useState(null);
  const [attribution, setAttribution] = useState(null);
  const [naiveBaseline, setNaiveBaseline] = useState(null);
  const [tracksData, setTracksData] = useState(null);
  const [fragility, setFragility] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [nextObs, setNextObs] = useState(null);
  const [historical, setHistorical] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listIncidents().then(setIncidents).catch(() => setIncidents([]));
  }, []);

  useEffect(() => {
    // Clear first: switching case must never leave one case's evidence on
    // screen beside another's while the new request is in flight.
    setManifest(null); setAttribution(null); setNaiveBaseline(null);
    setTracksData(null); setFragility(null); setForecast(null);
    setCoverage(null); setNextObs(null); setHistorical(null); setError(null);

    Promise.all([
      api.manifest(incidentId),
      api.attribution(incidentId),
      api.naiveBaseline(incidentId),
      api.tracks(incidentId),
    ])
      .then(([m, at, nb, tr]) => {
        setManifest(m); setAttribution(at); setNaiveBaseline(nb); setTracksData(tr);
      })
      .catch((e) => setError(String(e.message ?? e)));

    // Secondary evidence: each degrades its own panel, not the page.
    api.historicalMapping(incidentId).then(setHistorical).catch(() => setHistorical(null));
    api.fragility(incidentId).then(setFragility).catch(() => setFragility(null));
    api.forecast(incidentId).then(setForecast).catch(() => setForecast(null));
    api.coverage(incidentId).then(setCoverage).catch(() => setCoverage(null));
    api.nextObservation(incidentId).then(setNextObs).catch(() => setNextObs(null));
  }, [incidentId]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="wordmark">Slick Trace<span className="wordmark-sub">/ source attribution</span></div>
        {manifest && (
          <div className="topbar-meta">
            <span className="tag">{manifest.incident_id}</span>
            <span className="tag tag-teal">{manifest.case_state?.replace('_', ' ') ?? 'potential slick'}</span>
            {manifest.provenance?.status === 'synthetic' && <span className="tag tag-amber">synthetic case</span>}
            <a className="tag tag-link" href={api.reportUrl(incidentId)} target="_blank" rel="noreferrer">
              investigation report
            </a>
          </div>
        )}
      </header>

      <CaseSwitcher incidents={incidents} active={incidentId} onSelect={setIncidentId} />

      {error && <div className="error-banner">Failed to load incident data: {error}</div>}

      <VerdictBand attribution={attribution} naive={naiveBaseline}
                   historical={historical} manifest={manifest} />

      <main className="grid">
        <div className="grid-col grid-col-left">
          <ScenePanel manifest={manifest} sceneUrl={api.sceneUrl(incidentId)} />
          <TimeSliderMap incidentId={incidentId} api={api} tracksData={tracksData}
                         topCandidateId={attribution?.top_candidate_id} />
        </div>
        <div className="grid-col grid-col-mid">
          <RankingPanel naive={naiveBaseline} attribution={attribution} />
          <FragilityPanel fragility={fragility} />
          <NextObservationPanel nextObs={nextObs} />
        </div>
        <div className="grid-col grid-col-right">
          <AskConsole incidentId={incidentId} api={api} />
          <ForecastPanel forecast={forecast} />
          <CoveragePanel coverage={coverage} />
        </div>
      </main>
    </div>
  );
}
