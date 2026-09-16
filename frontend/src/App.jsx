import { useEffect, useState } from 'react';
import './dashboard.css';
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
        <div className="wordmark">Slick Trace<span className="wordmark-sub">/ source attribution</span></div>
        {manifest && (
          <div className="topbar-meta">
            <span className="tag tag-teal">{manifest.case_state?.replace('_', ' ') ?? 'potential slick'}</span>
            {manifest.provenance?.status === 'synthetic' && <span className="tag tag-amber">synthetic case</span>}
          </div>
        )}
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
            <ConclusionGraph 
              attribution={attribution} 
              naive={naiveBaseline}
              historical={historical} 
              manifest={manifest} 
              detection={detection} 
              fragility={fragility} 
              forecast={forecast} 
              coverage={coverage} 
              nextObs={nextObs} 
            />
            <AskConsole incidentId={incidentId} api={api} />
          </div>
        </div>
      </div>
    </div>
  );
}
