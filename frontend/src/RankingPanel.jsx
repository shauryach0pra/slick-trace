import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

function BaselineChart({ naive, topAttributed }) {
  if (!naive) return null;
  const data = naive.ranking.map((r) => ({ name: r.vessel_key, value: r.distance_deg }));
  const wrong = naive.top_candidate_id !== topAttributed;
  return (
    <div className="ranking-block">
      <div className="ranking-block-head">
        <h3>Naive Historical-Proximity Baseline</h3>
        <span className={wrong ? 'tag tag-red' : 'tag tag-green'}>
          {wrong ? 'Top Pick Wrong' : 'Top Pick Right'}
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
      <p className="ranking-caption">Distance to slick, degrees — lower is a stronger naive pick</p>
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
        <h3>Forward-Replay Attribution</h3>
        <span className={correct ? 'tag tag-green' : 'tag tag-amber'}>
          {correct ? 'Top Pick Right' : 'Unknown Source'}
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
        Mean IoU vs observed slick, across {attribution.n_ensemble_variants} shared forcing variants
        — Abstention gate at {attribution.abstention_iou_gate}
      </p>
    </div>
  );
}

export default function RankingPanel({ naive, attribution }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Candidate Ranking</h2>
      </div>
      <BaselineChart naive={naive} topAttributed={attribution?.top_candidate_id} />
      <AttributionChart attribution={attribution} />
    </div>
  );
}
