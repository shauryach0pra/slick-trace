import { useMemo, useState } from 'react';
import { Badge, Card, EmptyState, Stat, StatGrid } from '../ui/primitives';
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

export default function FragilityCard({ fragility, attribution }) {
  const [axis, setAxis] = useState('current_u_bias');
  const [whatIf, setWhatIf] = useState(false);
  const [pointId, setPointId] = useState(null);

  const points = useMemo(() => (fragility?.grid ?? [])
    .filter((g) => Object.keys(g.changed_axes).length === 1 && axis in g.changed_axes)
    .sort((a, b) => a.changed_axes[axis] - b.changed_axes[axis]), [fragility, axis]);

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

  return (
    <Card title="Rank Fragility"
          badge={<Badge tone={fragility.flip_found ? 'warning' : 'accent'}>
            {fragility.flip_found ? 'lead can flip' : 'lead held'}</Badge>}
          caption="What would have to change in the assumptions for a different vessel to lead."
          footnote={`${fragility.interpretation_note} ${fragility.coverage_note}`}>
      <StatGrid cols={2}>
        <Stat label={unnamed ? 'Unnamed leader (no source was named)' : 'Leader'} mono
              value={fragility.baseline_top} caption="The vessel with the best fit before any change." />
        <Stat label="Lead held"
              value={`${Math.round(fragility.lead_retained_fraction * 100)}% of ${fragility.n_points_tested}`}
              caption={C.leadHeld} />
      </StatGrid>

      {flip ? (
        <div className="flip-box">
          <StatGrid cols={2}>
            <Stat label="Smallest change that flips the lead"
                  value={Object.entries(flip.changed_axes).map(([k, v]) => `${label(k)} ${v}`).join(', ')}
                  caption={`Magnitude ${flip.magnitude}. ${C.magnitude}`} />
            <Stat label="Leader under that change" mono value={flip.top_candidate}
                  caption={`IoU ${flip.top_iou.toFixed(3)}; ${fragility.baseline_top} is now at IoU ${flip.baseline_candidate_iou.toFixed(3)}. `
                    + (flip.top_iou < flip.baseline_candidate_iou ? C.lossRanking : C.meanIou)} />
          </StatGrid>
          <WhatIf fragility={fragility} attribution={attribution} flip={flip} on={whatIf} setOn={setWhatIf} label={label} />
        </div>
      ) : (
        <p className="card-caption" style={{ marginTop: 'var(--space-4)' }}>
          No tested perturbation changed the leader.
        </p>
      )}

      <div style={{ marginTop: 'var(--space-5)' }}>
        <div className="ui-row">
          <label className="stat-label" htmlFor="frag-axis">Try one setting</label>
          <select id="frag-axis" className="ui-select" value={axis}
                  onChange={(e) => { setAxis(e.target.value); setPointId(null); }}>
            {AXIS_ORDER.filter((a) => fragility.axes[a]).map((a) => (
              <option key={a} value={a}>{label(a)}</option>
            ))}
          </select>
        </div>
        <p className="stat-caption">{C.sweep} Outlined values change the leader.</p>
        <div className="chip-steps" role="group" aria-label={`Tested values for ${label(axis)}`}
             style={{ marginTop: 'var(--space-2)' }}>
          {points.map((p) => (
            <button key={p.point_id} type="button"
                    className={`chip${pointId === p.point_id ? ' is-active' : ''}${p.flipped ? ' is-flag' : ''}`}
                    aria-pressed={pointId === p.point_id}
                    onClick={() => setPointId(pointId === p.point_id ? null : p.point_id)}>
              {String(p.changed_axes[axis])}
              <span className="visually-hidden">{p.flipped ? ' changes the leader' : ' leader unchanged'}</span>
            </button>
          ))}
        </div>
        {selected && (
          <div style={{ marginTop: 'var(--space-4)' }}>
            <StatGrid cols={3}>
              <Stat label="Leader under this setting" mono value={selected.top_candidate}
                    caption={selected.flipped ? 'A different vessel leads.' : 'Same leader as before.'} />
              <Stat label="Leader IoU" value={selected.top_iou.toFixed(3)} caption={C.meanIou} />
              <Stat label="Margin over next vessel" value={selected.loss_margin ?? '—'} caption={C.lossMargin} />
            </StatGrid>
          </div>
        )}
      </div>
    </Card>
  );
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
