import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

function BaselineChart({ naive, topAttributed }) {
  if (!naive) return null;
  const data = naive.ranking.map((r) => ({ name: r.vessel_key, value: r.distance_deg }));
  const wrong = naive.top_candidate_id !== topAttributed;
  return (
    <div className="ranking-block">
      <div className="ranking-block-head">
        <h3>Naive historical-proximity baseline</h3>
        <span className={wrong ? 'tag tag-red' : 'tag tag-green'}>
          top pick: {naive.top_candidate_id} {wrong ? '— wrong' : ''}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={22 * data.length + 20}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" width={110} tick={{ fill: 'var(--text-mid)', fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ background: 'var(--ink-800)', border: '1px solid var(--line)' }} />
          <Bar dataKey="value" radius={[0, 2, 2, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={i === 0 ? (wrong ? 'var(--red)' : 'var(--green)') : 'var(--text-dim)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="ranking-caption">distance to slick, degrees — lower is a stronger naive pick</p>
    </div>
  );
}

function AttributionChart({ attribution }) {
  if (!attribution) return null;
  const data = attribution.ranking.map((r) => ({ name: r.vessel_key, value: r.mean_iou }));
  const correct = !attribution.unknown_source;
  return (
    <div className="ranking-block">
      <div className="ranking-block-head">
        <h3>Forward-replay attribution</h3>
        <span className={correct ? 'tag tag-green' : 'tag tag-amber'}>
          {correct ? `top pick: ${attribution.top_candidate_id}` : 'unknown source'}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={22 * data.length + 20}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
          <XAxis type="number" domain={[0, 1]} hide />
          <YAxis type="category" dataKey="name" width={110} tick={{ fill: 'var(--text-mid)', fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ background: 'var(--ink-800)', border: '1px solid var(--line)' }} />
          <Bar dataKey="value" radius={[0, 2, 2, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={i === 0 ? 'var(--teal)' : 'var(--text-dim)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="ranking-caption">
        mean IoU vs observed slick, across {attribution.n_ensemble_variants} shared forcing variants
        — abstention gate at {attribution.abstention_iou_gate}
      </p>
    </div>
  );
}

export default function RankingPanel({ naive, attribution }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Candidate ranking</h2>
      </div>
      <BaselineChart naive={naive} topAttributed={attribution?.top_candidate_id} />
      <AttributionChart attribution={attribution} />
    </div>
  );
}
