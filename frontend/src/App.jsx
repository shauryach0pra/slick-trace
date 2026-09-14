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
    <div className="finder">
      <div className="finder-window">
        <header className="finder-titlebar">
          <span className="traffic" aria-hidden="true">
            <span className="tl tl-red" />
            <span className="tl tl-amber" />
            <span className="tl tl-green" />
          </span>
          <div className="finder-title">
            <span className="finder-title-main">Slick Trace</span>
            <span className="finder-title-sub">source attribution</span>
          </div>
          {manifest && (
            <div className="finder-title-meta">
              <span className="tag">{manifest.incident_id}</span>
              <span className="tag tag-teal">
                {manifest.case_state?.replace('_', ' ') ?? 'potential slick'}
              </span>
              {manifest.provenance?.status === 'synthetic' && (
                <span className="tag tag-amber">synthetic case</span>
              )}
            </div>
          )}
        </header>

        <div className="finder-body">
          {/* Row 1 — the sidebar: every case, as folders */}
          <CaseSwitcher incidents={incidents} active={incidentId} onSelect={setIncidentId} />

          {/* Rows 2 & 3 — two split-screen windows */}
          <div className="finder-split">
            <section className="finder-pane pane-evidence" aria-label="Evidence">
              <header className="pane-bar">
                <span className="pane-title">Evidence</span>
                {manifest && <span className="pane-sub">{manifest.incident_id}</span>}
              </header>
              <div className="pane-scroll">
                {error && (
                  <div className="error-banner">Failed to load incident data: {error}</div>
                )}
                <ScenePanel manifest={manifest} sceneUrl={api.sceneUrl(incidentId)}
                            detection={detection} />
                <RankingPanel naive={naiveBaseline} attribution={attribution} />
                <TimeSliderMap incidentId={incidentId} api={api} tracksData={tracksData}
                               topCandidateId={attribution?.top_candidate_id} />
                <FragilityPanel fragility={fragility} />
                <ForecastPanel forecast={forecast} />
                <NextObservationPanel nextObs={nextObs} />
                <CoveragePanel coverage={coverage} />
                <ProvenancePanel report={report} manifest={manifest} />
              </div>
            </section>

            <section className="finder-pane pane-conclusion" aria-label="Conclusion">
              <header className="pane-bar">
                <span className="pane-title">Conclusion</span>
                {manifest && (
                  <div className="pane-actions">
                    <a className="pane-file" href={api.reportUrl(incidentId)}
                       target="_blank" rel="noreferrer">
                      <span className="pane-file-ext">MD</span>report
                    </a>
                    <a className="pane-file" href={api.dossierUrl(incidentId)}
                       target="_blank" rel="noreferrer">
                      <span className="pane-file-ext">PDF</span>dossier
                    </a>
                  </div>
                )}
              </header>
              <div className="pane-scroll">
                <VerdictBand attribution={attribution} naive={naiveBaseline}
                             historical={historical} manifest={manifest} />
                <AskConsole incidentId={incidentId} api={api} />
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
