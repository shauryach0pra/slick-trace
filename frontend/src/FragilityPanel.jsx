import { useMemo, useState } from 'react';
import MetricInfo from './MetricInfo';

/**
 * Rank-fragility explorer (masterplan p.12 — P0).
 *
 * Answers "what would have to be different for this answer to change?".
 *
 * Every value shown here comes from a precomputed run on the server grid.
 * Moving the control selects a COMPUTED point; it never animates an invented
 * ranking change for a setting that was not run. Points are marked cached for
 * exactly that reason — an interpolated curve would look better and mean
 * nothing.
 */

const AXIS_ORDER = [
  'current_u_bias', 'current_v_bias', 'diffusivity_scale', 'mask_threshold', 'duration_shift_h',
];

export default function FragilityPanel({ fragility }) {
  const [axis, setAxis] = useState('current_u_bias');
  const [pointId, setPointId] = useState(null);

  const singleAxisPoints = useMemo(() => {
    if (!fragility?.grid) return [];
    return fragility.grid
      .filter((g) => Object.keys(g.changed_axes).length === 1 && axis in g.changed_axes)
      .sort((a, b) => a.changed_axes[axis] - b.changed_axes[axis]);
  }, [fragility, axis]);

  if (!fragility) return null;

  if (!fragility.testable) {
    return (
      <div className="panel">
        <div className="panel-head">
          <h2>Rank Fragility</h2>
          <span className="tag tag-amber">Not Testable</span>
        </div>
        <p className="empty-state">
          Not testable for this incident: {fragility.reason}
        </p>
      </div>
    );
  }

  const selected = pointId
    ? fragility.grid.find((g) => g.point_id === pointId)
    : null;
  const flip = fragility.smallest_flip;
  const retention = Math.round((fragility.lead_retained_fraction ?? 0) * 100);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Rank Fragility</h2>
        <span className={fragility.flip_found ? 'tag tag-amber' : 'tag tag-green'}>
          {fragility.flip_found ? 'Lead Can Flip' : 'Lead Stable'}
        </span>
      </div>

      <p className="frag-headline">
        <strong>{fragility.baseline_top}</strong> leads in{' '}
        <strong>{retention}%</strong> of {fragility.n_points_tested} tested perturbations
        <MetricInfo metric="leadRetention" />
      </p>

      {flip ? (
        <div className="frag-flip" role="note">
          <div className="frag-flip-head">
            Smallest tested rank-changing perturbation
            <MetricInfo metric="fragilityMagnitude" />
          </div>
          <ul className="frag-changes">
            {Object.entries(flip.changed_axes).map(([k, v]) => (
              <li key={k}>
                <span className="frag-axis">{fragility.axes[k]?.label ?? k}</span>
                <span className="frag-value">{String(v)}</span>
              </li>
            ))}
          </ul>
          <p className="frag-outcome">
            Leader becomes <strong>{flip.top_candidate}</strong> (IoU {flip.top_iou.toFixed(3)});{' '}
            {fragility.baseline_top} falls to IoU {flip.baseline_candidate_iou.toFixed(3)}.
            Standardised magnitude {flip.magnitude}.
          </p>
        </div>
      ) : (
        <p className="frag-outcome">
          No tested perturbation changed the leader.
        </p>
      )}

      <div className="frag-controls">
        <label htmlFor="frag-axis">Sweep one axis</label>
        <select id="frag-axis" value={axis}
                onChange={(e) => { setAxis(e.target.value); setPointId(null); }}>
          {AXIS_ORDER.filter((a) => fragility.axes[a]).map((a) => (
            <option key={a} value={a}>{fragility.axes[a].label}</option>
          ))}
        </select>

        <div className="frag-steps" role="group" aria-label={`Tested values for ${fragility.axes[axis]?.label}`}>
          {singleAxisPoints.map((p) => (
            <button
              key={p.point_id}
              type="button"
              className={`frag-step${pointId === p.point_id ? ' is-active' : ''}${p.flipped ? ' is-flip' : ''}`}
              aria-pressed={pointId === p.point_id}
              onClick={() => setPointId(pointId === p.point_id ? null : p.point_id)}
            >
              {String(p.changed_axes[axis])}
              {p.flipped && <span aria-hidden="true"> ⚑</span>}
              <span className="visually-hidden">
                {p.flipped ? ' — changes the leader' : ' — leader unchanged'}
              </span>
            </button>
          ))}
        </div>
      </div>

      {selected && (
        <dl className="frag-detail">
          <div>
            <dt>Selected run</dt>
            <dd>{selected.point_id}</dd>
          </div>
          <div>
            <dt>Leader under this setting</dt>
            <dd>{selected.top_candidate}{selected.flipped ? ' (changed)' : ' (unchanged)'}</dd>
          </div>
          <div>
            <dt>Leader IoU<MetricInfo metric="iou" /></dt>
            <dd>{selected.top_iou.toFixed(3)}</dd>
          </div>
          <div>
            <dt>Loss margin over runner-up</dt>
            <dd>{selected.loss_margin ?? '—'}</dd>
          </div>
        </dl>
      )}

      <p className="ranking-caption">
        {fragility.interpretation_note} {fragility.coverage_note}
      </p>
    </div>
  );
}
