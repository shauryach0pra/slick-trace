/**
 * Plain-language verdict, stated before any panel.
 *
 * The dashboard below is evidence. This is the finding. Without it a reviewer
 * has to reconstruct the argument from two bar charts of nine-digit MMSIs,
 * and the whole point of the case — that the nearest vessel is wrong — is
 * left for them to notice on their own.
 *
 * Wording is deliberately constrained: "ruled out" and "physically consistent"
 * rather than guilt language, and an explicit refusal when nothing fits.
 */

function Vessel({ id, role, tone, inline }) {
  if (inline) {
    return (
      <span className={`vd-inline vd-${tone}`}>
        <span className="vd-mmsi-inline">{id}</span>
        <span className="vd-role-inline"> ({role})</span>
      </span>
    );
  }
  return (
    <span className={`vd-vessel vd-${tone}`}>
      <span className="vd-mmsi">{id}</span>
      <span className="vd-role">{role}</span>
    </span>
  );
}

export default function VerdictBand({ attribution, naive, historical, manifest }) {
  if (!attribution || !naive || !manifest) return null;

  const nearest = naive.ranking?.[0];
  const top = attribution.ranking?.[0];
  const runnerUp = attribution.ranking?.[1];
  const unknown = attribution.unknown_source === true;
  const considered = Array.isArray(attribution.candidates_considered)
    ? attribution.candidates_considered.length
    : attribution.candidates_considered;

  const nearestAssessment = historical?.assessments?.find(
    (a) => a.vessel_key === nearest?.vessel_key,
  );
  const topAssessment = historical?.assessments?.find(
    (a) => a.vessel_key === top?.vessel_key,
  );

  if (unknown) {
    return (
      <section className="verdict verdict-unknown" aria-label="Case finding">
        <div className="panel-head">
          <h2>Case Finding</h2>
          <span className="verdict-chip vd-amber">Unknown Source</span>
        </div>
        <div className="verdict-content">
          <p className="verdict-body">
            No vessel in this scene can account for the observed slick. The nearest vessel at image time was{' '}
            <Vessel id={nearest?.vessel_key} role="Nearest at acquisition" tone="muted" inline />,
            which a proximity ranking would name. Forward replay tested{' '}
            <strong>{considered}</strong> release hypotheses and none reached the
            absolute fit gate of <strong>{attribution.abstention_iou_gate}</strong>
            {top && <> — the best Mean IoU {top.mean_iou.toFixed(3)}</>}. The system
            returns no name rather than the least-bad one.
          </p>
          <p className="verdict-note">
            A source vessel may have left the scene before acquisition. Declining to
            answer is the correct output here, and it is demonstrated rather than asserted.
          </p>
        </div>
      </section>
    );
  }

  const decoyBeaten = nearest && top && nearest.vessel_key !== top.vessel_key;
  const bandModifier = decoyBeaten ? 'verdict-ruledout' : 'verdict-affirmed';

  return (
    <section className={`verdict ${bandModifier}`} aria-label="Case finding">
      <div className="panel-head">
        <h2>Case Finding</h2>
        <span className={`verdict-chip ${decoyBeaten ? 'vd-green' : 'vd-green'}`}>
          {decoyBeaten ? 'Nearest Vessel Ruled Out' : 'Candidate Named'}
        </span>
      </div>
      <div className="verdict-content">
        <p className="verdict-line">
          {decoyBeaten ? (
            <>
              The closest ship is not the source. Forward replay points elsewhere.
            </>
          ) : (
            <>Forward replay identifies a physically consistent source.</>
          )}
        </p>

        <div className="verdict-compare">
          <div className="verdict-side">
            <span className="verdict-side-label">Proximity baseline picks</span>
            <Vessel id={nearest?.vessel_key} role="Nearest at acquisition" tone="wrong" />
            <span className="verdict-side-detail">
              {nearest && <>{(nearest.distance_deg).toFixed(3)}° from the slick</>}
              {nearestAssessment?.status === 'excluded' && (
                <> · earlier route never enters the origin envelope</>
              )}
            </span>
          </div>

          <div className="verdict-divider" aria-hidden="true">
            <span className="verdict-arrow">→</span>
          </div>

          <div className="verdict-side">
            <span className="verdict-side-label">Forward replay points to</span>
            <Vessel id={top?.vessel_key} role="Physically consistent" tone="right" />
            <span className="verdict-side-detail">
              Mean IoU <strong>{top?.mean_iou.toFixed(3)}</strong>
              {runnerUp && <> against {runnerUp.mean_iou.toFixed(3)} for the runner-up</>}
              {topAssessment?.first_entry_hours_before != null && (
                <> · inside the origin window {topAssessment.first_entry_hours_before} h
                   before acquisition</>
              )}
            </span>
          </div>
        </div>

      <p className="verdict-note">
        A ranking reflects physical consistency under tested assumptions — an
        investigative lead for a human analyst, not proof of responsibility.
      </p>
      </div>
    </section>
  );
}
