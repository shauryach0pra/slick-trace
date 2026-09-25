import './ConclusionGraph.css';

/**
 * Conclusion graph: how the finding was reached, as a left-to-right chain that
 * scrolls sideways - detection, historical filtering, forward replay (with the
 * proximity baseline it is measured against hanging beneath it), rank
 * fragility, finding.
 *
 * Every value is a field an artifact already carries; nothing here computes
 * beyond formatting. A stage whose artifact has not loaded says so instead of
 * showing a stand-in number. Abstention and an unseparated ranking are marked
 * as such, in a neutral warning colour rather than a verdict colour.
 *
 * Replaces an earlier version that read fields no artifact has
 * (detection.iou, historical.candidates, fragility.flip_delta), showed "N/A",
 * "0 candidates" and "Source: null", and drew attribution before filtering.
 */

const f3 = (x) => (typeof x === 'number' ? x.toFixed(3) : '—');

function Node({ n, title, state, variant = '', children }) {
  return (
    <div className={`cg-node is-${state}${variant ? ` ${variant}` : ''}`}>
      <div className="cg-node-head">
        <span className="cg-dot" aria-hidden="true">{n}</span>
        <span className="cg-title">{title}</span>
      </div>
      {children}
    </div>
  );
}

function Arrow() {
  return (
    <span className="cg-link" aria-hidden="true">
      <svg viewBox="0 0 28 12" width="28" height="12">
        <path d="M1 6h23" />
        <path d="M20 2l4.5 4-4.5 4" />
      </svg>
    </span>
  );
}

function Pending() {
  return <div className="cg-detail">not loaded</div>;
}

export default function ConclusionGraph({ attribution, naive, report, detection, fragility }) {
  const counts = report?.historical_filtering?.status_counts;
  const top = attribution?.ranking?.[0];
  const unknown = attribution?.unknown_source === true;
  const disc = attribution?.discrimination;
  const nearest = naive?.ranking?.[0];

  return (
    <section className="cg" aria-label="How the finding was reached">
      <div className="cg-head">
        <h2>Conclusion Graph</h2>
        <span className="tag">from artifacts</span>
      </div>

      <div className="cg-scroll" tabIndex={0} role="group"
           aria-label="Pipeline stages, left to right; scroll sideways for more">
        <ol className="cg-track">
          <li className="cg-item" style={{ '--k': 1 }}>
            <Node n={1} title="Detection"
                  state={!detection ? 'pending' : detection.detected ? 'done' : 'abstain'}>
              {!detection ? <Pending /> : detection.detected ? (
                <>
                  <div className="cg-value">{detection.geometry.area_km2} km² slick</div>
                  <div className="cg-detail">
                    {detection.n_regions} region{detection.n_regions === 1 ? '' : 's'} · classical baseline detector
                  </div>
                </>
              ) : (
                <div className="cg-value">No slick detected</div>
              )}
            </Node>
            <Arrow />
          </li>

          <li className="cg-item" style={{ '--k': 2 }}>
            <Node n={2} title="Historical filtering" state={counts ? 'done' : 'pending'}>
              {!counts ? <Pending /> : (
                <>
                  <div className="cg-value">{counts.candidate ?? 0} candidates</div>
                  <div className="cg-detail">
                    {counts.unassessed ?? 0} unassessed · {counts.excluded ?? 0} excluded by the
                    backward origin envelope
                  </div>
                </>
              )}
            </Node>
            <Arrow />
          </li>

          <li className="cg-item" style={{ '--k': 3 }}>
            <div className="cg-col">
              <Node n={3} title="Forward replay"
                    state={!attribution ? 'pending'
                      : (unknown || disc?.discriminated === false) ? 'abstain' : 'done'}>
                {!attribution ? <Pending /> : (
                  <>
                    {unknown ? (
                      <>
                        <div className="cg-value">No candidate cleared the fit gate</div>
                        <div className="cg-detail">
                          best mean IoU {f3(top?.mean_iou)} against a gate of {attribution.abstention_iou_gate}
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="cg-value cg-mono">{top?.vessel_key}</div>
                        <div className="cg-detail">
                          mean IoU {f3(top?.mean_iou)} · best under {top?.ensemble_win_count}/{top?.n_ensemble} forcing
                          variants
                        </div>
                      </>
                    )}
                    {disc && disc.discriminated !== null && !unknown && (
                      <div className="cg-detail">
                        {disc.discriminated
                          ? `separated from the runner-up by a loss gap of ${disc.loss_gap}`
                          : `not separated from the runner-up: loss gap ${disc.loss_gap} is under ${disc.tolerance}`}
                      </div>
                    )}
                    <div className="cg-note">
                      physics-based particle tracking under {attribution.n_ensemble_variants} shared forcing
                      perturbations
                    </div>
                  </>
                )}
              </Node>
              {nearest && (
                <>
                  <span className="cg-branch-link" aria-hidden="true" />
                  <Node n="vs" title="Proximity baseline" state="compare" variant="is-comparison">
                    <div className="cg-value cg-mono">{naive.top_candidate_id}</div>
                    <div className="cg-detail">
                      {f3(nearest.distance_deg)}° from the slick —{' '}
                      {unknown ? 'replay names no one'
                        : naive.top_candidate_id === attribution?.top_candidate_id
                          ? 'the same vessel as replay' : 'a different vessel from replay'}
                    </div>
                  </Node>
                </>
              )}
            </div>
            <Arrow />
          </li>

          <li className="cg-item" style={{ '--k': 4 }}>
            <Node n={4} title="Rank fragility"
                  state={!fragility ? 'pending' : fragility.flip_found ? 'abstain' : 'done'}>
              {!fragility ? <Pending /> : (
                <>
                  <div className="cg-value">
                    {unknown ? 'Unnamed leader' : 'Leader'} held in{' '}
                    {Math.round(fragility.lead_retained_fraction * 100)}% of {fragility.n_points_tested} perturbations
                  </div>
                  <div className="cg-detail">
                    {fragility.flip_found && fragility.smallest_flip
                      ? `smallest change that flips it: ${Object.entries(fragility.smallest_flip.changed_axes)
                          .map(([k, v]) => `${k.replaceAll('_', ' ')} ${v}`).join(', ')} (magnitude ${fragility.smallest_flip.magnitude})`
                      : 'no tested perturbation changed the leader'}
                  </div>
                </>
              )}
            </Node>
            <Arrow />
          </li>

          <li className="cg-item" style={{ '--k': 5 }}>
            <Node n={5} title="Finding" variant="is-final"
                  state={!attribution ? 'pending' : unknown ? 'abstain' : 'done'}>
              {!attribution ? <Pending /> : unknown ? (
                <>
                  <div className="cg-value">Unknown source</div>
                  <div className="cg-detail">no vessel is named; declining is the output</div>
                </>
              ) : (
                <>
                  <div className="cg-value">
                    <span className="cg-mono">{attribution.top_candidate_id}</span> is physically consistent
                  </div>
                  <div className="cg-detail">
                    under the tested assumptions — an investigative lead, not proof of responsibility
                    {disc?.discriminated === false ? '; its ordering against the runner-up carries no weight' : ''}
                  </div>
                </>
              )}
            </Node>
          </li>
        </ol>
      </div>

      <p className="cg-foot">
        Replay and fragility are scored against the generator's slick mask, not the detected outline.
      </p>
    </section>
  );
}
