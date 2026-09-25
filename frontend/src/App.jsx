import { useEffect, useState } from 'react';
import './dashboard.css';
import './shell.css';
import { api } from './api';
import CaseSwitcher from './CaseSwitcher';
import ProvenancePanel from './ProvenancePanel';
import VerdictBand from './VerdictBand';
import ScenePanel from './ScenePanel';
import RankingPanel from './RankingPanel';
import TimeSliderMap from './TimeSliderMap';
import FragilityPanel from './FragilityPanel';
import AskConsole from './AskConsole';
import ForecastPanel from './ForecastPanel';
import CoveragePanel from './CoveragePanel';
import NextObservationPanel from './NextObservationPanel';
import ThemeToggle from './ThemeToggle';
import ConclusionGraph from './ConclusionGraph';

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
  const [detection, setDetection] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listIncidents().then(setIncidents).catch(() => setIncidents([]));
  }, []);

  useEffect(() => {
    // Clear first: switching case must never leave one case's evidence on
    // screen beside another's while the new request is in flight.
    setManifest(null); setAttribution(null); setNaiveBaseline(null);
    setTracksData(null); setFragility(null); setForecast(null);
    setCoverage(null); setNextObs(null); setHistorical(null); setDetection(null); setReport(null); setError(null);

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
    api.detection(incidentId).then(setDetection).catch(() => setDetection(null));
    api.report(incidentId).then(setReport).catch(() => setReport(null));
    api.historicalMapping(incidentId).then(setHistorical).catch(() => setHistorical(null));
    api.fragility(incidentId).then(setFragility).catch(() => setFragility(null));
    api.forecast(incidentId).then(setForecast).catch(() => setForecast(null));
    api.coverage(incidentId).then(setCoverage).catch(() => setCoverage(null));
    api.nextObservation(incidentId).then(setNextObs).catch(() => setNextObs(null));
  }, [incidentId]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="wordmark">
          <svg className="wordmark-mark" viewBox="0 0 18 18" aria-hidden="true">
            <rect width="18" height="18" rx="5" fill="var(--accent)" />
            <path d="M9 3.6s-3.1 3.9-3.1 5.9a3.1 3.1 0 0 0 6.2 0C12.1 7.5 9 3.6 9 3.6Z" fill="#fff" />
            <path d="M3.8 14c1.2-.9 2.3-.9 3.5 0s2.3.9 3.5 0 2.3-.9 3.4 0" stroke="#fff"
                  strokeWidth="1.2" fill="none" strokeLinecap="round" opacity=".85" />
          </svg>
          Slick Trace<span className="wordmark-sub">Source attribution</span>
        </div>
        <div className="topbar-trailing">
          {manifest && (
            <div className="topbar-meta">
              <span className="tag tag-teal">{manifest.case_state?.replace('_', ' ') ?? 'potential slick'}</span>
              {manifest.provenance?.status === 'synthetic' && <span className="tag tag-amber">synthetic case</span>}
            </div>
          )}
          <ThemeToggle />
        </div>
      </header>

      {error && <div className="error-banner">Failed to load incident data: {error}</div>}

      <div className="finder-layout">
        {/* First column: Sidebar with cases */}
        <aside className="finder-sidebar">
          <CaseSwitcher incidents={incidents} active={incidentId} onSelect={setIncidentId} />
        </aside>

        {/* Second column: Feature boxes - Inverted Pyramid Structure */}
        <div className="finder-content">
          <div className="finder-features">
            {/* Top: Most important conclusion */}
            <VerdictBand attribution={attribution} naive={naiveBaseline}
                         historical={historical} manifest={manifest} />
            
            {/* Key attribution results */}
            <RankingPanel naive={naiveBaseline} attribution={attribution} />
            
            {/* Primary evidence */}
            <ScenePanel manifest={manifest} sceneUrl={api.sceneUrl(incidentId)}
                        detection={detection} />
            
            {/* Supporting analysis */}
            <TimeSliderMap incidentId={incidentId} api={api} tracksData={tracksData}
                           topCandidateId={attribution?.top_candidate_id} />
            
            {/* Sensitivity analysis */}
            <FragilityPanel fragility={fragility} />
            
            {/* Predictive information */}
            <ForecastPanel forecast={forecast} />
            
            {/* Future analysis */}
            <NextObservationPanel nextObs={nextObs} />
            
            {/* Hidden AIS analysis */}
            <CoveragePanel coverage={coverage} />
            
            {/* Technical metadata */}
            <ProvenancePanel report={report} manifest={manifest} />
          </div>

          {/* Third column: Ask Console and report buttons */}
          <div className="finder-details">
            {manifest && (
              <div className="report-buttons">
                <a className="report-button" href={api.reportUrl(incidentId)} target="_blank" rel="noreferrer">
                  Investigation Report
                </a>
                <a className="report-button" href={api.dossierUrl(incidentId)} target="_blank" rel="noreferrer">
                  Dossier (PDF)
                </a>
              </div>
            )}
            <ConclusionGraph key={incidentId} attribution={attribution} naive={naiveBaseline}
                             report={report} detection={detection} fragility={fragility} />
            <AskConsole incidentId={incidentId} api={api} />
          </div>
        </div>
      </div>
    </div>
  );
}
