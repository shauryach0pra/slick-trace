import { useEffect, useId, useRef, useState } from 'react';

/**
 * Inline metric explanation (masterplan p.5, p.13).
 *
 * A reviewer has limited time per team and no presenter at their shoulder when
 * they revisit the build. Every metric on screen carries its own explanation,
 * so correctness is checkable without narration.
 *
 * Hover OR tap OR keyboard — the tap path matters because the panel is also
 * read on a phone, where hover does not exist.
 */

export const METRIC_TEXT = {
  iou: {
    title: 'IoU (intersection over union)',
    body: 'Overlap between the simulated footprint and the observed slick, divided by their ' +
      'combined area. 1.0 is a perfect match, 0.0 is no overlap at all. It penalises both ' +
      'missing real slick and inventing slick that is not there, which a simple ' +
      '"how much did we cover" score does not.',
  },
  abstention: {
    title: 'Abstention gate',
    body: 'The minimum IoU a candidate must reach before the system will name it. Below this ' +
      'the result is reported as unknown source rather than the least-bad option. Without ' +
      'an absolute floor, a ranking always has a winner — even when nothing fits.',
  },
  ensembleWins: {
    title: 'Ensemble win count',
    body: 'How many of the shared wind/current perturbations this candidate fits best under. ' +
      'Every candidate is tested against the identical perturbation set and search budget. ' +
      'This is an evidence score, not a calibrated probability of responsibility — there is ' +
      'no calibration against held-out real outcomes.',
  },
  naiveBaseline: {
    title: 'Naive proximity baseline',
    body: 'Picks whichever vessel was nearest the slick when the image was taken, over the ' +
      'full unfiltered vessel list. It is the shortcut this system has to beat, and it is ' +
      'shown whether it wins or loses.',
  },
  leadRetention: {
    title: 'Lead retention',
    body: 'The share of tested perturbations in which the leading candidate kept its lead. ' +
      'High retention means the answer does not depend on one lucky assumption. Only ' +
      'single-axis and two-axis perturbations were tested, so this is evidence of ' +
      'stability across the tested set, not a proof of stability.',
  },
  fragilityMagnitude: {
    title: 'Standardised perturbation magnitude',
    body: 'Each axis is normalised by its own plausible range, so 1.0 means one axis pushed ' +
      'to the edge of that range and 0.5 means half of it. The axes are comparable by ' +
      'construction, not by physical equivalence, so the axis is always named alongside ' +
      'the number.',
  },
  candidateStates: {
    title: 'Candidate, excluded, unassessed',
    body: 'Candidate: track data present and inside the backward envelope at some time. ' +
      'Excluded: track data at every queried time, never inside. Unassessed: never inside ' +
      'where data exists, but no track data for part or all of the window. Those hours are ' +
      'missing evidence, not exoneration, which is why a partly covered vessel is never excluded.',
  },
  hindcastEnvelope: {
    title: 'Backward origin envelope',
    body: 'Where the observed slick could have drifted from, traced backwards under reversed ' +
      'forcing. It widens the further back you go because release time, duration and ' +
      'diffusivity are all unknown. It is not converging on a point source, and it is not ' +
      'drawn to look as if it does.',
  },
  exposure: {
    title: 'Modelled exposure',
    body: 'The fraction of simulated surface particles reaching an area under the tested ' +
      'forcing ensemble. It is a modelled arrival interval, not a prediction of beaching, ' +
      'concentration or environmental damage. Weathering and shoreline interaction are ' +
      'not modelled.',
  },
  hiddenAis: {
    title: 'Hidden-AIS recovery rate',
    body: 'Of vessels whose AIS was deliberately hidden, the share the system still surfaces ' +
      'as unidentified contacts. Reported with a false unmatched-alert rate and a ' +
      'mistaken-promotion rate at a stated match gate, because a recovery figure on its ' +
      'own can be bought by flagging everything.',
  },
  disagreement: {
    title: 'Disagreement score',
    body: 'How differently the two leading explanations predict the slick will look at a ' +
      'future time: 1 minus the overlap of their predicted footprints. Higher means one ' +
      'more observation then would separate them. It is a simple disagreement score, not ' +
      'expected information gain — no observation likelihood is modelled.',
  },
};

export default function MetricInfo({ metric, label }) {
  const [open, setOpen] = useState(false);
  // `pinned` distinguishes "opened by hover" from "opened deliberately".
  // Without it, onMouseEnter opens the popover and the click that follows
  // toggles it straight back shut — which means a TAP can never open it,
  // since touch browsers synthesise mouseenter before click. Hover worked,
  // tap silently did nothing.
  const [pinned, setPinned] = useState(false);
  const id = useId();
  const ref = useRef(null);
  const entry = METRIC_TEXT[metric];

  useEffect(() => {
    if (!open) return undefined;
    const close = () => { setOpen(false); setPinned(false); };
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    const onClickAway = (e) => { if (ref.current && !ref.current.contains(e.target)) close(); };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClickAway);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClickAway);
    };
  }, [open]);

  if (!entry) return null;

  return (
    <span className="metric-info" ref={ref}>
      <button
        type="button"
        className="metric-info-trigger"
        aria-label={`What does ${entry.title} mean?`}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={() => {
          const next = !pinned;
          setPinned(next);
          setOpen(next);
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => { if (!pinned) setOpen(false); }}
        onFocus={() => setOpen(true)}
        onBlur={() => { if (!pinned) setOpen(false); }}
      >
        {label ?? 'i'}
      </button>
      {open && (
        <span className="metric-info-popover" role="tooltip" id={id}>
          <strong>{entry.title}</strong>
          <span>{entry.body}</span>
        </span>
      )}
    </span>
  );
}
