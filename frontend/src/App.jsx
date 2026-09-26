import { Suspense, lazy, useCallback, useEffect, useState } from 'react';
import './dashboard.css';
import './shell.css';
import { api } from './api';
import { useCase } from './useCase';
import CaseSwitcher from './CaseSwitcher';
import Overview from './Overview';
import FamilyChips from './FamilyChips';
import ConfidenceBadge from './ConfidenceBadge';
import { attachStickyHeaders } from './stickyHeaders';
import { attachTilt } from './tilt';
import ThemeToggle from './ThemeToggle';
import ConclusionGraph from './ConclusionGraph';
import CaseFindingCard from './cards/CaseFindingCard';
import RankingRevealCard from './cards/RankingRevealCard';
import ObservedSceneCard from './cards/ObservedSceneCard';
import HistoricalReplayCard from './cards/HistoricalReplayCard';
import FragilityCard from './cards/FragilityCard';
import ForecastCard from './cards/ForecastCard';
import NextObservationCard from './cards/NextObservationCard';
import CoverageCard from './cards/CoverageCard';
import ProvenanceCard from './cards/ProvenanceCard';
import AskSlickTraceCard from './cards/AskSlickTraceCard';

// loaded only when a tour starts, so driver.js is not in every page view
const Tour = lazy(() => import('./tour/Tour'));

export default function App() {
  const [incidents, setIncidents] = useState([]);
  // Routes live in the URL hash, so Back and Forward work: #/overview (the
  // default) or #/case/<id>. The last case opened stays loaded behind the
  // overview, so returning to it is instant.
  const parseRoute = () => {
    const m = window.location.hash.match(/^#\/case\/([\w-]+)/);
    return m ? { view: 'case', id: m[1] } : { view: 'overview', id: null };
  };
  const [route, setRoute] = useState(parseRoute);
  useEffect(() => {
    const on = () => setRoute(parseRoute());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  const [lastCase, setLastCase] = useState(route.id ?? 'case_0001');
  if (route.id && route.id !== lastCase) setLastCase(route.id);
  const incidentId = route.id ?? lastCase;
  const openCase = useCallback((id) => { window.location.hash = `#/case/${id}`; }, []);
  const openOverview = useCallback(() => { window.location.hash = '#/overview'; }, []);
  // family filter for the overview grid; the sidebar always lists every case
  const [family, setFamily] = useState('all');
  const { case: c, report, tracks, error } = useCase(incidentId);

  useEffect(() => {
    api.listIncidents().then(setIncidents).catch(() => setIncidents([]));
  }, []);
  // hover tilt and light for every card, one listener for the app
  useEffect(() => attachTilt(), []);


  const [touring, setTouring] = useState(false);

  // Cross-fade between cases: the last fully loaded case stays on screen (dimmed)
  // until the next has loaded, then fades in - rather than blanking and
  // reloading. Updated during render, the standard pattern for derived state.
  const [shown, setShown] = useState(null);
  if (c && (shown?.c !== c || shown?.report !== report || shown?.tracks !== tracks)) {
    setShown({ id: incidentId, c, report, tracks });
  }
  const vid = shown?.id;
  const vc = shown?.c;
  const leaving = !!shown && shown.id !== incidentId;
  const meta = vc?.meta;

  // scroll-edge effect on the pinned card headers; the column remounts per case
  useEffect(() => attachStickyHeaders(document.querySelector('.finder-features')), [vid, route.view]);

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
          {meta && route.view === 'case' && (
            <div className="topbar-meta">
              <span className="tag tag-teal">{meta.case_state.replace('_', ' ')}</span>
              {meta.provenance.status === 'synthetic' && <span className="tag tag-amber">synthetic case</span>}
            </div>
          )}
          {route.view === 'case' && vc && <ConfidenceBadge key={`conf-${vid}`} attribution={vc.attribution} />}
          <button type="button" className={`tour-btn${touring ? ' is-on' : ''}`} onClick={() => setTouring((t) => !t)}>
            {touring ? 'Exit Tour' : 'Start Tour'}
          </button>
          <ThemeToggle />
        </div>
      </header>

      {error && <div className="error-banner">Failed to load incident data: {error}</div>}
      {touring && incidents.length > 0 && (
        <Suspense fallback={null}>
          <Tour incidents={incidents} api={api} selectCase={openCase} onExit={() => setTouring(false)} />
        </Suspense>
      )}

      <div className="finder-layout">
        <aside className="finder-sidebar">
          <button type="button" className={`nav-overview${route.view === 'overview' ? ' is-active' : ''}`} onClick={openOverview}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 2h5v5H2zM9 2h5v5H9zM2 9h5v5H2zM9 9h5v5H9z" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" /></svg>
            Overview
          </button>
          <CaseSwitcher incidents={incidents} active={route.view === 'case' ? incidentId : null} onSelect={openCase} />
        </aside>

        {route.view === 'overview' ? (
          <Overview api={api} onOpen={openCase} family={family}
                    chips={<FamilyChips incidents={incidents} value={family} onChange={setFamily} className="in-overview" />} />
        ) : (
        <div className={`finder-content${leaving ? ' is-leaving' : ''}`} data-case={vid}>
          {/* Evidence column, in the order a reviewer needs it: finding first. */}
          <div className="finder-features" key={vid}>
            {vc && (
              <>
                <CaseFindingCard attribution={vc.attribution} baseline={vc.baseline} vessels={vc.vessels} />
                <RankingRevealCard attribution={vc.attribution} baseline={vc.baseline} vessels={vc.vessels} />
                <ObservedSceneCard meta={meta} slick={vc.slick} sceneUrl={api.sceneUrl(vid)}
                                   nVessels={vc.vessels.length} />
                <HistoricalReplayCard incidentId={vid} api={api} c={vc} tracks={shown.tracks} />
                <FragilityCard fragility={vc.fragility} attribution={vc.attribution} />
                <ForecastCard forecast={vc.forecast} />
                {/* two supporting cards, side by side */}
                <div className="card-row">
                  <CoverageCard coverage={vc.coverage} />
                  <ProvenanceCard meta={meta} report={shown.report} attribution={vc.attribution} />
                </div>
                {/* the case closes on what to check next */}
                <NextObservationCard nextObs={vc.next_observation} closing />
              </>
            )}
          </div>

          <div className="finder-details" key={`d-${vid}`}>
            {meta && (
              <div className="report-buttons">
                <a className="report-button" href={api.reportUrl(vid)} target="_blank" rel="noreferrer">
                  Investigation Report
                </a>
                <a className="report-button" href={api.dossierUrl(vid)} target="_blank" rel="noreferrer">
                  Dossier (PDF)
                </a>
              </div>
            )}
            {vc && (
              <ConclusionGraph key={vid} attribution={vc.attribution} naive={vc.baseline}
                               report={shown.report} detection={vc.slick} fragility={vc.fragility} />
            )}
            {vid && <AskSlickTraceCard key={`ask-${vid}`} incidentId={vid} api={api} />}
          </div>
        </div>
        )}
      </div>
    </div>
  );
}
