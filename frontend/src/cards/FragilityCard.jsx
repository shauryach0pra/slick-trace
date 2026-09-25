import { useMemo, useState } from 'react';
import { Badge, Card, EmptyState, Stat, StatGrid } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Rank fragility: what would have to change for the leader to change.
 *
 * Every value is a precomputed run on the server's grid. Choosing a setting
 * selects a computed point; nothing is interpolated for a setting that was
 * not run. On an abstained case the leader was never named, and says so.
 */
const AXIS_ORDER = ['current_u_bias', 'current_v_bias', 'diffusivity_scale', 'mask_threshold', 'duration_shift_h'];

export default function FragilityCard({ fragility }) {
  const [axis, setAxis] = useState('current_u_bias');
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
