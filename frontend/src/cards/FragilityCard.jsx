import { useState } from 'react';
import { Badge, Card, EmptyState } from '../ui/primitives';
import { HowMeasured } from '../ui/viz';
import { useCountUp } from '../ui/useCountUp';
import { useInView } from '../ui/useInView';
import './fragility.css';
import './whatIf.css';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Rank fragility: what would have to change for the leader to change.
 *
 * Every value is a precomputed run on the server's grid. Choosing a setting
 * selects a computed point; nothing is interpolated for a setting that was
 * not run. On an abstained case the leader was never named, and says so.
 */
const AXIS_ORDER = ['current_u_bias', 'current_v_bias', 'diffusivity_scale', 'mask_threshold', 'duration_shift_h'];
const SHORT = { current_u_bias: 'Along-shore current', current_v_bias: 'Cross-shore current', diffusivity_scale: 'Spreading',
                mask_threshold: 'Footprint threshold', duration_shift_h: 'Release duration' };

export default function FragilityCard({ fragility, attribution }) {
  const [axis, setAxis] = useState('current_u_bias');
  const [whatIf, setWhatIf] = useState(false);
  const [pointId, setPointId] = useState(null);


  if (!fragility) return null;
  if (!fragility.testable) {
    return (
      <Card title="Rank Fragility" badge={<Badge tone="warning">not testable</Badge>}>
        <EmptyState>Not testable for this incident: {fragility.reason}</EmptyState>
      </Card>
    );
  }
  const unnamed = fragility.baseline_unknown_source;
  const flip = fragility.smallest_flip;
  const selected = pointId ? fragility.grid.find((g) => g.point_id === pointId) : null;
  const label = (k) => fragility.axes[k]?.label ?? k;

  const pct = Math.round(fragility.lead_retained_fraction * 100);
  return (
    <Card title="Rank Fragility"
          badge={<Badge tone={fragility.flip_found ? 'warning' : 'accent'}>
            {fragility.flip_found ? 'lead can flip' : 'lead held'}</Badge>}
          caption="Does the leader survive small changes to the model's assumptions?">
      <div className="fr">
        <FlipMatrix fragility={fragility} label={label} />
        <div className="fr-hero">
          <span className="fr-big"><Count value={pct} />%</span>
          <span className="fr-hero-label">of {fragility.n_points_tested} tested changes kept
            {' '}<b className="mono">{fragility.baseline_top}</b>{unnamed ? ' (unnamed best fit)' : ''} in the lead</span>
          <div className="fr-counts">
            <span className="is-held"><i /><b>{fragility.n_points_tested - fragility.n_points_flipped}</b> held the lead</span>
            <span className="is-flip"><i /><b>{fragility.n_points_flipped}</b> flipped it</span>
          </div>
          {flip ? (
            <div className="fr-flip2">
              <div className="fr-flip2-top">
                <b>Smallest flip</b><span className="fr-flip2-mag">magnitude {flip.magnitude}</span>
              </div>
              <span className="fr-flip2-line">
                {Object.entries(flip.changed_axes).map(([k, v]) => `${label(k)} ${v}`).join(' + ')} → <b className="mono">{flip.top_candidate}</b> leads
              </span>
              {Object.entries(flip.changed_axes).map(([k, v]) => (
                <AxisTrack key={k} axis={k} fragility={fragility} label={label} mark={v} readOnly />
              ))}
            </div>
          ) : <span className="fr-flip is-held">No tested change moved the leader.</span>}
        </div>
      </div>

      {flip && <WhatIf fragility={fragility} attribution={attribution} flip={flip} on={whatIf} setOn={setWhatIf} label={label} />}

      <div className="fr-explore">
        <span className="fr-explore-label">Explore one setting</span>
        <div className="fr-tabs" role="tablist" aria-label="Assumption to explore">
          {AXIS_ORDER.filter((x) => fragility.axes[x]).map((x) => (
            <button key={x} type="button" role="tab" aria-selected={axis === x} className={`fr-tab${axis === x ? ' is-on' : ''}`}
                    onClick={() => { setAxis(x); setPointId(null); }}>{SHORT[x] ?? label(x)}</button>
          ))}
        </div>
        <AxisTrack axis={axis} fragility={fragility} label={label} selected={pointId}
                   onPick={(pt) => setPointId(pointId === pt.point_id ? null : pt.point_id)} />
        <p className={`fr-selected${selected ? ' is-on' : ''}`}>
          {selected ? <><b className="mono">{selected.top_candidate}</b> leads{selected.flipped ? ' — a different vessel' : ' — the same leader'}
            {' '}· IoU {selected.top_iou.toFixed(3)}{selected.loss_margin != null ? ` · margin ${selected.loss_margin}` : ''}</>
            : 'Tap a tested value to see who leads under it.'}
        </p>
      </div>

      <HowMeasured>
        <dl>
          <dt>Lead held</dt><dd>{C.leadHeld}</dd>
          <dt>Magnitude</dt><dd>{C.magnitude}</dd>
          <dt>Ranking</dt><dd>{C.lossRanking}</dd>
          <dt>Explore one setting</dt><dd>{C.sweep}</dd>
          <dt>What this is and is not</dt><dd>{fragility.interpretation_note} {fragility.coverage_note}</dd>
        </dl>
      </HowMeasured>
    </Card>
  );
}

/**
 * Every tested change as one dot, smallest change first: blue where the leader
 * held, amber where it flipped, the smallest flip ringed. Hover or focus a dot
 * for that change.
 */
function FlipMatrix({ fragility, label }) {
  const [hover, setHover] = useState(null);
  const pts = [...(fragility.grid ?? [])].sort((x, y) => x.magnitude - y.magnitude || x.point_id.localeCompare(y.point_id));
  const firstId = fragility.smallest_flip?.point_id;
  const describe = (pt) => `${Object.entries(pt.changed_axes).map(([k, v]) => `${label(k)} ${v}`).join(', ')} · `
    + `${pt.flipped ? `${pt.top_candidate} leads` : 'leader held'} · magnitude ${pt.magnitude}`;
  // the readout always describes a dot: the first (the smallest change) until another is hovered
  const shown = hover ?? pts[0] ?? null;
  return (
    <div className="fr-matrix-wrap">
      <div className="fr-matrix" role="list" aria-label={`${pts.length} tested changes, smallest first`}
           onMouseLeave={() => setHover(null)}>
        {pts.map((pt, i) => (
          <span key={pt.point_id} role="listitem" tabIndex={0} aria-label={describe(pt)}
                className={`fr-dot${pt.flipped ? ' is-flip' : ''}${pt.point_id === firstId ? ' is-first' : ''}${shown && pt.point_id === shown.point_id ? ' is-shown' : ''}`}
                style={{ '--i': i }} onMouseEnter={() => setHover(pt)} onFocus={() => setHover(pt)} onBlur={() => setHover(null)} />
        ))}
      </div>
      <span className="fr-axis"><span>smallest change</span><span>largest</span></span>
      <div className="fr-legend fr-legend-grid">
        <span><i className="is-held" />lead held</span><span><i className="is-flip" />lead flipped</span>
        {fragility.smallest_flip && <span><i className="is-first" />smallest flip</span>}
      </div>
      <p className="fr-readout is-on" aria-live="polite">{shown ? describe(shown) : ''}</p>
    </div>
  );
}

function Count({ value }) {
  const [ref, seen] = useInView();
  return <span ref={ref}>{useCountUp(value, { decimals: 0, duration: 1000, run: seen })}</span>;
}

/**
 * "What if conditions were slightly different?" - the tested ranking against the
 * smallest tested change that flips the lead, for the two vessels that swap.
 * Ranking is by loss (lower is better); IoU is shown alongside. Each tested change
 * stores only its leader and the tested leader's fit, so only those two rows are
 * shown under it - the rest of that ranking was not stored.
 */
function WhatIf({ fragility, attribution, flip, on, setOn, label }) {
  const a = fragility.baseline_top, b = flip.top_candidate;
  const rank = (k) => (attribution?.ranking ?? []).findIndex((r) => r.vessel_key === k) + 1;
  const iou0 = (k) => (attribution?.ranking ?? []).find((r) => r.vessel_key === k)?.mean_iou;
  const loss0 = fragility.nominal_mean_losses ?? {};
  const change = Object.entries(flip.changed_axes).map(([k, v]) => `${label(k)} ${v}`).join(', ');
  const rows = [
    { key: a, pos: on ? 1 : 0, iou: on ? flip.baseline_candidate_iou : iou0(a),
      note: on ? 'now behind' : `#${rank(a)} as tested · loss ${loss0[a]?.toFixed(3) ?? '—'}`, lead: !on },
    { key: b, pos: on ? 0 : 1, iou: on ? flip.top_iou : iou0(b),
      note: on ? `leads by a loss margin of ${flip.loss_margin}` : `#${rank(b)} as tested · loss ${loss0[b]?.toFixed(3) ?? '—'}`, lead: on },
  ];
  return (
    <div className="whatif">
      <div className="whatif-head">
        <span className="whatif-q">What if conditions were slightly different?</span>
        <div className="whatif-seg" role="group" aria-label="Show the ranking as tested or with the smallest flipping change">
          <button type="button" className={!on ? 'is-on' : ''} aria-pressed={!on} onClick={() => setOn(false)}>As tested</button>
          <button type="button" className={on ? 'is-on' : ''} aria-pressed={on} onClick={() => setOn(true)}>With {change}</button>
        </div>
      </div>
      <div className="whatif-rows" role="table" aria-label="The two vessels that swap">
        {rows.map((r) => (
          <div key={r.key} role="row" className={`whatif-row${r.lead ? ' is-lead' : ''}`}
               style={{ transform: `translateY(${r.pos * 46}px)`, '--w': Math.max(0, Math.min(1, r.iou ?? 0)) }}>
            <span className="whatif-pos" role="cell">{r.pos + 1}</span>
            <span className="whatif-key" role="cell">{r.key}</span>
            <span className="whatif-track" role="cell" aria-hidden="true"><span className="whatif-fill" /></span>
            <span className="whatif-iou" role="cell">{r.iou != null ? r.iou.toFixed(3) : '—'}</span>
            <span className="whatif-note" role="cell">{r.note}</span>
          </div>
        ))}
      </div>
      <p className="whatif-foot">
        {on ? `With ${change} (magnitude ${flip.magnitude}), ${b} leads instead of ${a}. `
          : `As tested, ${a} leads. `}
        Ranked by loss; the bar is mean IoU. Only these two vessels' fits are stored for each tested change, so the
        rest of the ranking under it is not shown.
      </p>
    </div>
  );
}

/**
 * One assumption as a track of its tested values: the value as tested is a hollow
 * stop; each changed value is blue where the leader held and amber where it
 * flipped. `mark` rings a value (the smallest flip); `onPick` makes stops tappable.
 */
function AxisTrack({ axis, fragility, label, mark = null, selected = null, onPick = null, readOnly = false }) {
  const values = fragility.axes[axis]?.tested_values ?? [];
  const single = (fragility.grid ?? []).filter((g) => Object.keys(g.changed_axes).length === 1 && axis in g.changed_axes);
  const at = new Map(single.map((g) => [g.changed_axes[axis], g]));
  return (
    <div className={`fr-track${readOnly ? ' is-static' : ''}`}>
      <span className="fr-track-name">{label(axis)}</span>
      <div className="fr-track-line" role={readOnly ? undefined : 'group'} aria-label={`Tested values for ${label(axis)}`}>
        <span className="fr-track-rail" aria-hidden="true" />
        {values.map((v, i) => {
          const pt = at.get(v);
          const kind = !pt ? 'nominal' : pt.flipped ? 'flip' : 'held';
          const cls = `fr-stop is-${kind}${mark === v ? ' is-mark' : ''}${pt && selected === pt.point_id ? ' is-sel' : ''}`;
          const inner = <><i /><span>{String(v)}</span></>;
          return (!pt || readOnly || !onPick)
            ? <span key={v} className={cls} style={{ '--i': i }} title={!pt ? 'as tested' : `${pt.flipped ? 'flips the lead' : 'lead held'}`}>{inner}</span>
            : <button key={v} type="button" className={cls} style={{ '--i': i }} aria-pressed={selected === pt.point_id}
                      aria-label={`${label(axis)} ${v}: ${pt.flipped ? 'the lead flips' : 'the lead holds'}`} onClick={() => onPick(pt)}>{inner}</button>;
        })}
      </div>
    </div>
  );
}

