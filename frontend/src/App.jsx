import { useEffect, useState } from 'react';
import './dashboard.css';
import './shell.css';
import { api } from './api';
import { useCase } from './useCase';
import CaseSwitcher from './CaseSwitcher';
import ThemeToggle from './ThemeToggle';
import ConclusionGraph from './ConclusionGraph';
import CaseFindingCard from './cards/CaseFindingCard';
import CandidateRankingCard from './cards/CandidateRankingCard';
import ObservedSceneCard from './cards/ObservedSceneCard';
import HistoricalReplayCard from './cards/HistoricalReplayCard';
import BasemapCard from './cards/BasemapCard';
import FragilityCard from './cards/FragilityCard';
import ForecastCard from './cards/ForecastCard';
import NextObservationCard from './cards/NextObservationCard';
import CoverageCard from './cards/CoverageCard';
import ProvenanceCard from './cards/ProvenanceCard';
import AskSlickTraceCard from './cards/AskSlickTraceCard';

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [incidentId, setIncidentId] = useState('case_0001');
  const { case: c, report, tracks, error } = useCase(incidentId);

  useEffect(() => {
    api.listIncidents().then(setIncidents).catch(() => setIncidents([]));
  }, []);

  const meta = c?.meta;

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
          {meta && (
            <div className="topbar-meta">
              <span className="tag tag-teal">{meta.case_state.replace('_', ' ')}</span>
              {meta.provenance.status === 'synthetic' && <span className="tag tag-amber">synthetic case</span>}
            </div>
          )}
          <ThemeToggle />
        </div>
      </header>

      {error && <div className="error-banner">Failed to load incident data: {error}</div>}

      <div className="finder-layout">
        <aside className="finder-sidebar">
          <CaseSwitcher incidents={incidents} active={incidentId} onSelect={setIncidentId} />
        </aside>

        <div className="finder-content">
          {/* Evidence column, in the order a reviewer needs it: finding first. */}
          <div className="finder-features" key={incidentId}>
            {c && (
              <>
                <CaseFindingCard attribution={c.attribution} baseline={c.baseline} vessels={c.vessels} />
                <CandidateRankingCard kind="replay" attribution={c.attribution} baseline={c.baseline} />
                <CandidateRankingCard kind="baseline" attribution={c.attribution} baseline={c.baseline} />
                <ObservedSceneCard meta={meta} slick={c.slick} sceneUrl={api.sceneUrl(incidentId)}
                                   nVessels={c.vessels.length} />
                <BasemapCard meta={meta} api={api} />
                <HistoricalReplayCard incidentId={incidentId} api={api} tracks={tracks}
                                      topCandidateId={c.attribution?.top_candidate_id} />
                <FragilityCard fragility={c.fragility} />
                <ForecastCard forecast={c.forecast} />
                <NextObservationCard nextObs={c.next_observation} />
                <CoverageCard coverage={c.coverage} />
                <ProvenanceCard meta={meta} report={report} />
              </>
            )}
          </div>

          <div className="finder-details">
            {meta && (
              <div className="report-buttons">
                <a className="report-button" href={api.reportUrl(incidentId)} target="_blank" rel="noreferrer">
                  Investigation Report
                </a>
                <a className="report-button" href={api.dossierUrl(incidentId)} target="_blank" rel="noreferrer">
                  Dossier (PDF)
                </a>
              </div>
            )}
            <ConclusionGraph key={incidentId} attribution={c?.attribution} naive={c?.baseline}
                             report={report} detection={c?.slick} fragility={c?.fragility} />
            <AskSlickTraceCard key={`ask-${incidentId}`} incidentId={incidentId} api={api} />
          </div>
        </div>
      </div>
    </div>
  );
}
