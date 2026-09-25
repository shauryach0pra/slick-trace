import { useEffect, useState } from 'react';
import { api } from './api';

/**
 * Everything the cards need for one incident.
 *
 * case    the Case contract (/case): one validated object assembled from the
 *         committed artifacts.
 * report  /report, for the status counts and checksum list the contract
 *         does not carry.
 * tracks  /tracks, for the replay map.
 *
 * Responses for a case that is no longer selected are dropped, so switching
 * quickly can never leave one case's evidence beside another's.
 */
const EMPTY = { case: null, report: null, tracks: null, error: null };

export function useCase(incidentId) {
  const [state, setState] = useState(EMPTY);

  useEffect(() => {
    let live = true;
    setState(EMPTY);
    const put = (k) => (v) => { if (live) setState((s) => ({ ...s, [k]: v })); };
    api.case(incidentId).then(put('case'))
      .catch((e) => put('error')(String(e.message ?? e)));
    api.report(incidentId).then(put('report')).catch(() => {});
    api.tracks(incidentId).then(put('tracks')).catch(() => {});
    return () => { live = false; };
  }, [incidentId]);

  return state;
}
