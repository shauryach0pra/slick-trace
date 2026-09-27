import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import './confidenceBadge.css';

/**
 * One badge for what a finding is and is not, in the same place for every case:
 * the fit-gate status, the "lead, not proof" framing, and that the pipeline is
 * grounded - rule-based, with no language model in the loop. Every number comes
 * from the case's attribution result; nothing here is computed beyond comparing
 * the fit with the gate the artifact states.
 */
function jumpToProvenance() {
  const pane = document.querySelector('.finder-features');
  const h = [...(pane?.querySelectorAll('h2') ?? [])].find((x) => x.textContent.trim() === 'Traffic Filtering and Provenance');
  const card = h?.closest('.panel');
  if (!pane || !card) return;
  pane.scrollTo({ top: card.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop - 12, behavior: 'smooth' });
  card.classList.remove('cg-flash'); void card.offsetWidth; card.classList.add('cg-flash');
  setTimeout(() => card.classList.remove('cg-flash'), 1800);
}

export default function ConfidenceBadge({ attribution }) {
  const [open, setOpen] = useState(false);
  const [at, setAt] = useState(null);
  const btn = useRef(null);
  const pop = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const place = () => { const r = btn.current?.getBoundingClientRect(); if (r) setAt({ x: r.right, y: r.bottom + 8 }); };
    place();
    const away = (e) => { if (!pop.current?.contains(e.target) && !btn.current?.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('resize', place);
    document.addEventListener('mousedown', away);
    document.addEventListener('keydown', esc);
    return () => { window.removeEventListener('resize', place); document.removeEventListener('mousedown', away); document.removeEventListener('keydown', esc); };
  }, [open]);

  if (!attribution) return null;
  const unknown = attribution.unknown_source;
  const gate = attribution.abstention_iou_gate;
  const top = attribution.ranking?.[0];
  const disc = attribution.discrimination;
  const label = unknown ? 'Abstains' : 'Lead · not proof';

  return (
    <>
      <button type="button" ref={btn} className={`conf-badge${unknown ? ' is-abstain' : ''}${open ? ' is-open' : ''}`}
              aria-expanded={open} aria-haspopup="dialog" onClick={() => setOpen((o) => !o)}>
        <span className="conf-dot" aria-hidden="true" />{label}
      </button>
      {open && at && createPortal(
        <div className="conf-pop" ref={pop} role="dialog" aria-label="What this finding is" style={{ left: at.x, top: at.y }}>
          <div className="conf-row">
            <span className="conf-k">Fit gate</span>
            <span className="conf-v">
              {unknown
                ? <>Best fit <b>{top?.mean_iou?.toFixed(2) ?? '—'}</b> is below the gate of <b>{gate}</b>, so no vessel is named</>
                : <>Mean IoU <b>{top.mean_iou.toFixed(2)}</b> ≥ gate <b>{gate}</b>
                    {disc?.discriminated === true ? <>, separated from the runner-up by a loss gap of {disc.loss_gap}</>
                      : disc?.discriminated === false ? <>, but not separated from the runner-up (gap {disc.loss_gap} under {disc.tolerance})</> : null}</>}
            </span>
          </div>
          <div className="conf-row">
            <span className="conf-k">What it means</span>
            <span className="conf-v">{unknown
              ? 'Declining is the output: no vessel is implicated by this analysis.'
              : 'An investigative lead for an analyst to follow up — physical consistency under tested assumptions, not proof of responsibility.'}</span>
          </div>
          <div className="conf-row">
            <span className="conf-k">How it was made</span>
            <span className="conf-v">A grounded pipeline: physics-based particle tracking and rule-based templates. No language model is in the loop.</span>
          </div>
          <button type="button" className="conf-link" onClick={() => { setOpen(false); jumpToProvenance(); }}>
            Provenance and data sources →
          </button>
        </div>, document.body)}
    </>
  );
}
