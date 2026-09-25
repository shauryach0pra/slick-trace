import TimeSliderMap from '../TimeSliderMap';

/**
 * Historical replay, chrome only: the card frame, badge and caption now come
 * from the shared Card (inside TimeSliderMap); the map itself is unchanged
 * until Phase 4.
 */
export default function HistoricalReplayCard({ incidentId, api, tracks, topCandidateId }) {
  return (
    <TimeSliderMap incidentId={incidentId} api={api} tracksData={tracks}
                   topCandidateId={topCandidateId} />
  );
}
