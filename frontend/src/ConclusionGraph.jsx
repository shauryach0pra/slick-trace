import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import './ConclusionGraph.css';

/**
 * Conclusion graph: how the finding was reached, stage by stage.
 *
 * Fully data-driven. buildStages() turns the case's artifacts into an ordered
 * list of stages - each with its state, what it found, a plain-language caption
 * of what it computes, and the evidence card it summarises - plus optional
 * branch stages (the proximity baseline hangs beneath forward replay as a
 * comparison). Layout and every edge are computed from the rendered nodes, so
 * nothing here fixes a node count or a position.
 *
 * Every value is a field an artifact already carries; nothing here computes
 * beyond formatting. The CONFIRMED path - stages that completed - glows and
 * carries particles; where the evidence stops (an abstention, an unseparated
 * ranking) the path turns amber; a stage whose artifact has not loaded is grey.
 */

const f3 = (x) => (typeof x === 'number' ? x.toFixed(3) : '—');

const CAPTION = {
  detection: 'Finds dark, smooth patches in the radar image that could be oil, and measures the outline.',
  filtering: 'Traces the slick backwards in time and keeps only vessels whose tracks passed through where it could have come from.',
  replay: 'For each remaining vessel, simulates oil released along its track and scores how well it recreates the observed slick.',
  baseline: 'The naive shortcut: whichever vessel was nearest the slick when the image was taken. Shown for comparison, not used.',
  fragility: 'Nudges the assumptions - currents, spreading, timing - to see whether the leading vessel stays on top.',
  finding: 'What the evidence supports: a lead for an analyst to follow up, never proof of responsibility.',
};

function buildStages({ attribution, naive, report, detection, fragility }) {
  const counts = report?.historical_filtering?.status_counts;
  const top = attribution?.ranking?.[0];
  const unknown = attribution?.unknown_source === true;
  const disc = attribution?.discrimination;
  const nearest = naive?.ranking?.[0];
  const stages = [];

  stages.push(!detection ? { id: 'detection', title: 'Detection', state: 'pending' } : {
    id: 'detection', title: 'Detection', state: detection.detected ? 'done' : 'abstain',
    value: detection.detected ? `${detection.geometry.area_km2} km² slick` : 'No slick detected',
    detail: detection.detected ? `${detection.n_regions} region${detection.n_regions === 1 ? '' : 's'} · classical baseline detector` : null,
  });
  stages.push(!counts ? { id: 'filtering', title: 'Historical filtering', state: 'pending' } : {
    id: 'filtering', title: 'Historical filtering', state: 'done',
    value: `${counts.candidate ?? 0} candidates`,
    detail: `${counts.unassessed ?? 0} unassessed · ${counts.excluded ?? 0} excluded by the backward origin envelope`,
  });
  const replay = !attribution ? { id: 'replay', title: 'Forward replay', state: 'pending' } : {
    id: 'replay', title: 'Forward replay', state: (unknown || disc?.discriminated === false) ? 'abstain' : 'done',
    value: unknown ? 'No candidate cleared the fit gate' : top?.vessel_key, mono: !unknown,
    detail: unknown ? `best mean IoU ${f3(top?.mean_iou)} against a gate of ${attribution.abstention_iou_gate}`
      : `mean IoU ${f3(top?.mean_iou)} · best under ${top?.ensemble_win_count}/${top?.n_ensemble} forcing variants`,
    note: disc && disc.discriminated !== null && !unknown
      ? (disc.discriminated ? `separated from the runner-up by a loss gap of ${disc.loss_gap}`
        : `not separated from the runner-up: loss gap ${disc.loss_gap} is under ${disc.tolerance}`) : null,
  };
  if (nearest) {
    replay.branches = [{
      id: 'baseline', title: 'Proximity baseline', state: 'compare', value: naive.top_candidate_id, mono: true,
      detail: `${f3(nearest.distance_deg)}° from the slick — ${unknown ? 'replay names no one'
        : naive.top_candidate_id === attribution?.top_candidate_id ? 'the same vessel as replay' : 'a different vessel from replay'}`,
    }];
  }
  stages.push(replay);
  stages.push(!fragility ? { id: 'fragility', title: 'Rank fragility', state: 'pending' } : {
    id: 'fragility', title: 'Rank fragility', state: fragility.flip_found ? 'abstain' : 'done',
    value: `${unknown ? 'Unnamed leader' : 'Leader'} held in ${Math.round(fragility.lead_retained_fraction * 100)}% of ${fragility.n_points_tested} perturbations`,
    detail: fragility.flip_found && fragility.smallest_flip
      ? `smallest change that flips it: ${Object.entries(fragility.smallest_flip.changed_axes)
        .map(([k, v]) => `${k.replaceAll('_', ' ')} ${v}`).join(', ')} (magnitude ${fragility.smallest_flip.magnitude})`
      : 'no tested perturbation changed the leader',
  });
  stages.push(!attribution ? { id: 'finding', title: 'Finding', state: 'pending', final: true } : {
    id: 'finding', title: 'Finding', final: true, state: unknown ? 'abstain' : 'done',
    value: unknown ? 'Unknown source' : `${attribution.top_candidate_id} is physically consistent`,
    detail: unknown ? 'no vessel is named; declining is the output'
      : `under the tested assumptions — an investigative lead, not proof of responsibility${disc?.discriminated === false ? '; its ordering against the runner-up carries no weight' : ''}`,
  });
  // what each stage summarises in the evidence column
  const TARGET = { detection: 'Observed Scene', filtering: 'Traffic Filtering and Provenance', replay: 'Naive vs Forward-Replay',
                   baseline: 'Naive vs Forward-Replay', fragility: 'Rank Fragility', finding: 'Case Finding' };
  const decorate = (s) => ({ ...s, caption: CAPTION[s.id], target: TARGET[s.id], branches: s.branches?.map(decorate) });
  return stages.map(decorate);
}

/** An edge's state: glowing along the confirmed path, amber where the evidence stops. */
const edgeState = (from, to) => (to.state === 'compare' ? 'compare'
  : from.state === 'pending' || to.state === 'pending' ? 'pending'
    : from.state === 'done' && to.state === 'done' ? 'done' : 'abstain');

function jumpTo(title, stage) {
  // the replay stage opens the ranking on its forward-replay view
  if (stage === 'replay') window.dispatchEvent(new CustomEvent('slicktrace:reveal'));
  const pane = document.querySelector('.finder-features');
  const h = [...(pane?.querySelectorAll('h2') ?? [])].find((x) => x.textContent.trim() === title);
  const card = h?.closest('.panel') ?? h?.closest('section');
  if (!pane || !card) return;
  const top = card.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop - 12;
  pane.scrollTo({ top, behavior: 'smooth' });
  card.classList.remove('cg-flash'); void card.offsetWidth; card.classList.add('cg-flash');
  setTimeout(() => card.classList.remove('cg-flash'), 1800);
}

function NodeCard({ s, index, register }) {
  const ref = useRef(null);
  useLayoutEffect(() => register(s.id, ref.current), [register, s.id]);
  return (
    <button type="button" ref={ref} className={`cgx-node is-${s.state}${s.final ? ' is-final' : ''}${s.state === 'compare' ? ' is-compare' : ''}`}
            style={{ '--k': index }} onClick={() => s.target && jumpTo(s.target, s.id)}
            title={s.target ? `Open ${s.target}` : undefined}
            aria-label={`${s.title}: ${s.value ?? 'not loaded'}. ${s.caption ?? ''}`}>
      <span className="cgx-head">
        <span className="cgx-dot" aria-hidden="true">{s.state === 'compare' ? 'vs' : index + 1}</span>
        <span className="cgx-title">{s.title}</span>
      </span>
      {s.state === 'pending' ? <span className="cgx-detail">not loaded</span> : (
        <>
          <span className={`cgx-value${s.mono ? ' is-mono' : ''}`}>{s.value}</span>
          {s.detail && <span className="cgx-detail">{s.detail}</span>}
          {s.note && <span className="cgx-detail">{s.note}</span>}
        </>
      )}
    </button>
  );
}

export default function ConclusionGraph(props) {
  const { attribution, naive, report, detection, fragility } = props;
  // memoised on the artifacts themselves: the props object is new every render
  const stages = useMemo(() => buildStages({ attribution, naive, report, detection, fragility }),
                         [attribution, naive, report, detection, fragility]);
  const track = useRef(null);
  const nodes = useRef({});
  const [edges, setEdges] = useState([]);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [viewH, setViewH] = useState(null);
  const register = useCallback((id, el) => { nodes.current[id] = el; }, []);

  // every edge from the rendered nodes: card to card left to right, and each
  // branch hanging below its parent
  const layout = useCallback(() => {
    const t = track.current;
    if (!t) return;
    // Layout positions (offsetLeft/offsetTop), not getBoundingClientRect: the cards'
    // staggered entrance animation moves them with a transform, and measuring
    // mid-animation left the connectors a few pixels out of level.
    const box = (id) => {
      const el = nodes.current[id];
      if (!el) return null;
      let l = 0, tp = 0;
      for (let n = el; n && n !== t; n = n.offsetParent) { l += n.offsetLeft; tp += n.offsetTop; }
      return { l, r: l + el.offsetWidth, t: tp, b: tp + el.offsetHeight, cx: l + el.offsetWidth / 2 };
    };
    const out = [];
    stages.forEach((s, i) => {
      const a = box(s.id);
      if (!a) return;
      const n = stages[i + 1] && box(stages[i + 1].id);
      if (n) {
        const y1 = a.t + 26, y2 = n.t + 26, dx = (n.l - a.r) / 2;
        out.push({ id: `${s.id}-${stages[i + 1].id}`, state: edgeState(s, stages[i + 1]),
                   d: `M${a.r},${y1} C${a.r + dx},${y1} ${n.l - dx},${y2} ${n.l},${y2}` });
      }
      (s.branches ?? []).forEach((br) => {
        const b = box(br.id);
        if (b) out.push({ id: `${s.id}-${br.id}`, state: edgeState(s, br),
                          d: `M${a.cx},${a.b} C${a.cx},${a.b + 12} ${b.cx},${b.t - 12} ${b.cx},${b.t}` });
      });
    });
    setEdges(out);
    setSize({ w: t.scrollWidth, h: t.scrollHeight });
    // the window fits the main row of cards; branches below are scrolled to
    const main = Math.max(0, ...stages.map((st) => { const b = box(st.id); return b ? b.b : 0; }));
    setViewH(Math.ceil(main) + 16);
  }, [stages]);

  useLayoutEffect(() => {
    layout();
    const ro = new ResizeObserver(layout);
    if (track.current) ro.observe(track.current);
    return () => ro.disconnect();
  }, [layout]);

  const confirmed = stages.filter((s) => s.state === 'done').length;
  return (
    <section className="cg cgx" aria-label="How the finding was reached">
      <div className="cg-head">
        <h2>Conclusion Graph</h2>
        <span className="tag">{confirmed} of {stages.length} stages confirmed</span>
      </div>
      <div className="cgx-scroll" tabIndex={0} role="group" style={viewH ? { height: viewH } : undefined}
           aria-label="Pipeline stages, left to right; scroll sideways, and down for the comparison">
        <div className="cgx-track" ref={track} role="list">
          <svg className="cgx-edges" width={size.w} height={size.h} aria-hidden="true">
            <defs>
              <linearGradient id="cgx-done" x1="0" x2="1"><stop offset="0" stopColor="#0a84ff" /><stop offset="1" stopColor="#5ac8fa" /></linearGradient>
              <filter id="cgx-glow" x="-20%" y="-100%" width="140%" height="300%"><feGaussianBlur stdDeviation="3" /></filter>
            </defs>
            {edges.map((e, i) => (
              <g key={e.id} className={`cgx-edge is-${e.state}`} style={{ '--k': i }}>
                {e.state === 'done' && <path d={e.d} className="cgx-edge-glow" filter="url(#cgx-glow)" />}
                <path d={e.d} className="cgx-edge-base" pathLength="100" />
                {(e.state === 'done' || e.state === 'abstain') && <path d={e.d} className="cgx-edge-flow" />}
                {(e.state === 'done' || e.state === 'abstain') && [0, 1].map((n) => (
                  <circle key={n} r="2.3" className="cgx-particle">
                    <animateMotion dur={e.state === 'done' ? '1.8s' : '2.8s'} begin={`${n * (e.state === 'done' ? 0.9 : 1.4) + i * 0.2}s`}
                                   repeatCount="indefinite" path={e.d} />
                  </circle>
                ))}
              </g>
            ))}
          </svg>
          {stages.map((s, i) => (
            <div className="cgx-col" key={s.id} role="listitem">
              <NodeCard s={s} index={i} register={register} />
              {(s.branches ?? []).map((br) => (
                <NodeCard key={br.id} s={br} index={i} register={register} />
              ))}
            </div>
          ))}
        </div>
      </div>
      <p className="cg-foot">Click a stage to jump to its evidence. Scroll sideways for every stage, and down for the
        proximity baseline. Replay and fragility are scored against the generator's slick mask, not the detected outline.</p>
    </section>
  );
}
