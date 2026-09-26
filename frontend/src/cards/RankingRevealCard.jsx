import { useEffect, useRef, useState } from 'react';
import { Badge, Card } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';
import { HowMeasured } from '../ui/viz';
import './rankingReveal.css';

/**
 * Naive vs forward replay, as one reveal.
 *
 * It opens on the naive answer: every vessel ranked by how near it was to the
 * slick when the image was taken. "Reveal forward-replay result" then shows what
 * the pipeline already computed - it does not re-run anything - and the rows
 * re-sort into forward-replay order, the bars become fit (mean IoU), the
 * proximity pick is struck through where replay does not support it, and the
 * leader is highlighted. Where no candidate clears the fit gate the reveal ends
 * with the system abstaining.
 *
 * It never says "right" or "wrong": the interface has no ground truth to judge
 * either method by. Every value is a field of attribution_result.json or
 * naive_baseline_result.json.
 */

const ROW = 46;
const STATUS = { excluded: 'excluded by historical filtering', unassessed: 'unassessed: no track for part of the window' };

export default function RankingRevealCard({ attribution, baseline, vessels }) {
  const [phase, setPhase] = useState(0);     // 0 proximity · 1 strike · 2 re-sort · 3 settled
  const phaseRef = useRef(0);
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const reveal = () => {
    if (reduce) { setPhase(3); return; }
    setPhase(1);
    setTimeout(() => setPhase(2), 380);
    setTimeout(() => setPhase(3), 1150);
  };
  // "Show in ranking" on the map and the graph's replay stage ask for the replay view
  const revealRef = useRef(reveal);
  useEffect(() => { revealRef.current = reveal; });
  useEffect(() => {
    const on = () => { if (phaseRef.current === 0) revealRef.current(); };
    window.addEventListener('slicktrace:reveal', on);
    return () => window.removeEventListener('slicktrace:reveal', on);
  }, []);

  if (!baseline?.ranking?.length || !attribution) return null;
  const unknown = attribution.unknown_source;
  const gate = attribution.abstention_iou_gate;
  const naiveKey = baseline.top_candidate_id;
  const leadKey = unknown ? null : attribution.top_candidate_id;
  const replayed = new Map(attribution.ranking.map((r, i) => [r.vessel_key, { ...r, rank: i + 1 }]));
  const maxDist = Math.max(...baseline.ranking.map((r) => r.distance_deg), 1e-6);
  const status = new Map((vessels ?? []).map((v) => [v.vessel_key, v.status]));

  // the two orders: proximity (every vessel), and replay (candidates by fit, then the rest)
  const naiveOrder = baseline.ranking.map((r) => r.vessel_key);
  const replayOrder = [...attribution.ranking.map((r) => r.vessel_key),
                       ...naiveOrder.filter((k) => !replayed.has(k))];
  const revealed = phase >= 2;
  const order = revealed ? replayOrder : naiveOrder;
  const agree = !unknown && naiveKey === leadKey;

  const rows = baseline.ranking.map((r) => {
    const rep = replayed.get(r.vessel_key);
    const pos = order.indexOf(r.vessel_key);
    let width, value, sub, cls = '';
    if (!revealed) {
      width = r.distance_deg / maxDist;
      value = `${r.distance_deg.toFixed(3)}°`;
      sub = r.vessel_key === naiveKey ? 'nearest · proximity pick' : null;
      if (r.vessel_key === naiveKey) cls = ' is-naive';
    } else if (rep) {
      width = rep.mean_iou;
      value = rep.mean_iou.toFixed(3);
      sub = `#${rep.rank} · best under ${rep.ensemble_win_count}/${rep.n_ensemble} variants`;
      if (r.vessel_key === leadKey) cls = phase >= 3 ? ' is-lead is-settled' : ' is-lead';
      else if (unknown) cls = ' is-below';
    } else {
      width = 0;
      value = '—';
      sub = `not replayed · ${STATUS[status.get(r.vessel_key)] ?? 'filtered out'}`;
      cls = ' is-out';
    }
    // struck only where replay names a different vessel; when it names no one, nothing is set aside
    const struck = phase >= 1 && r.vessel_key === naiveKey && !agree && !unknown;
    return (
      <div key={r.vessel_key} className={`rv-row${cls}${struck ? ' is-struck' : ''}`} role="row"
           data-rank-key={r.vessel_key} id={`rank-${revealed ? 'replay' : 'naive'}-${r.vessel_key}`}
           style={{ transform: `translateY(${pos * ROW}px)`, '--w': Math.max(0, Math.min(1, width)), '--d': pos }}>
        <span className="rv-pos" role="cell">{pos + 1}</span>
        <span className="rv-key" role="cell"><span className="rv-key-text">{r.vessel_key}</span></span>
        <span className="rv-track" role="cell" aria-hidden="true">
          <span className="rv-fill" />
          {revealed && <span className="rv-gate" style={{ left: `${gate * 100}%` }} />}
        </span>
        <span className="rv-value" role="cell">{value}</span>
        <span className="rv-sub" role="cell" key={`${phase >= 2}-${struck}`}>
          {struck ? 'proximity pick · not supported by forward replay'
            : revealed && agree && r.vessel_key === naiveKey ? 'proximity and forward replay agree'
              : revealed && unknown && r.vessel_key === naiveKey ? `proximity pick · below the fit gate, like every candidate` : sub}
        </span>
      </div>
    );
  });

  const badge = !revealed ? <Badge>proximity only</Badge>
    : <Badge tone={unknown ? 'warning' : 'accent'}>{unknown ? 'abstained' : 'named'}</Badge>;
  return (
    <Card title="Naive vs Forward-Replay" badge={badge}
          caption={revealed ? 'Which vessel’s drifted release best matches the slick.' : 'The shortcut: the vessel nearest the slick when the image was taken.'}
          className={`rv-card${unknown && revealed ? ' is-abstain' : ''}`}>
      <div className="rv-controls">
        {phase === 0
          ? <button type="button" className="rv-btn is-primary" onClick={reveal}>Reveal forward-replay result</button>
          : <button type="button" className="rv-btn" onClick={() => setPhase(0)}>Show proximity only</button>}
        <span className="rv-legend">
          {revealed ? <>Bar: mean IoU of the best replayed release · tick: fit gate {gate}</>
            : <>Bar: distance to the slick when the image was taken · shorter is nearer</>}
        </span>
      </div>
      <div className="rv-list" role="table" aria-label={revealed ? 'Vessels in forward-replay order' : 'Vessels by distance at image time'}
           style={{ height: baseline.ranking.length * ROW }}>
        {rows}
      </div>
      {revealed && unknown && (
        <div className="rv-abstain" role="status">
          <strong>No candidate meets the fit gate: the system abstains.</strong>
          <span>The best replayed fit is a mean IoU of {attribution.ranking[0]?.mean_iou?.toFixed(3) ?? '—'}, below
            the gate of {gate}. Declining to name a vessel is the output, not a failure to produce one.</span>
        </div>
      )}
      <HowMeasured>
        <dl>
          <dt>Proximity</dt><dd>{C.baselineMethod}</dd>
          <dt>Forward replay</dt><dd>{C.replayMethod}</dd>
          <dt>Fit gate</dt><dd>Below a mean IoU of {gate} no vessel is named.</dd>
          <dt>What the reveal does</dt><dd>It shows results the pipeline already computed; nothing is re-run.</dd>
        </dl>
      </HowMeasured>
    </Card>
  );
}
