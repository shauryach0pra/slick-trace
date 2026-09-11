import { useEffect, useState } from 'react';
import './dashboard.css';
import { api } from './api';
import ScenePanel from './ScenePanel';
import RankingPanel from './RankingPanel';
import TimeSliderMap from './TimeSliderMap';
import FragilityPanel from './FragilityPanel';
import AskConsole from './AskConsole';

const INCIDENT_ID = 'case_0001';

export default function App() {
  const [manifest, setManifest] = useState(null);
  const [attribution, setAttribution] = useState(null);
  const [naiveBaseline, setNaiveBaseline] = useState(null);
  const [tracksData, setTracksData] = useState(null);
  const [fragility, setFragility] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Core evidence must load for the page to mean anything, so a failure here
    // is surfaced. Fragility is an overlay on top of a ranking that already
    // renders, so its absence degrades one panel rather than the whole view.
    Promise.all([
      api.manifest(INCIDENT_ID),
      api.attribution(INCIDENT_ID),
      api.naiveBaseline(INCIDENT_ID),
      api.tracks(INCIDENT_ID),
    ])
      .then(([m, at, nb, tr]) => {
        setManifest(m);
        setAttribution(at);
        setNaiveBaseline(nb);
        setTracksData(tr);
      })
      .catch((e) => setError(String(e.message ?? e)));

    api.fragility(INCIDENT_ID).then(setFragility).catch(() => setFragility(null));
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="wordmark">VARUNA<span className="wordmark-sub">/ OilTrace</span></div>
        {manifest && (
          <div className="topbar-meta">
            <span className="tag">{manifest.incident_id}</span>
            <span className="tag tag-teal">{manifest.case_state?.replace('_', ' ') ?? 'potential slick'}</span>
            {manifest.provenance?.status === 'synthetic' && <span className="tag tag-amber">synthetic case</span>}
            <a className="tag tag-link" href={api.reportUrl(INCIDENT_ID)} target="_blank" rel="noreferrer">
              investigation report
            </a>
          </div>
        )}
      </header>

      {error && <div className="error-banner">Failed to load incident data: {error}</div>}

      <main className="grid">
        <div className="grid-col grid-col-left">
          <ScenePanel manifest={manifest} sceneUrl={api.sceneUrl(INCIDENT_ID)} />
          <TimeSliderMap incidentId={INCIDENT_ID} api={api} tracksData={tracksData}
                         topCandidateId={attribution?.top_candidate_id} />
        </div>
        <div className="grid-col grid-col-mid">
          <RankingPanel naive={naiveBaseline} attribution={attribution} />
          <FragilityPanel fragility={fragility} />
        </div>
        <div className="grid-col grid-col-right">
          <AskConsole incidentId={INCIDENT_ID} api={api} />
        </div>
      </main>
    </div>
  );
}
