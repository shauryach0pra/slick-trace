import { useId } from 'react';
import './charts.css';

/**
 * Small, quiet SVG charts: lines that draw in, points you can hover for their
 * value, and bars that grow. They only draw values passed in from artifacts.
 */

/** A line (with optional soft area) over a few labelled x positions. */
export function LineChart({ xs, series, yMax, yFormat = (v) => v, height = 150, ariaLabel }) {
  const gid = useId().replace(/:/g, '');
  const W = 420, H = height, L = 38, R = 14, T = 12, B = 26;
  const X = (i) => L + (xs.length === 1 ? 0.5 : i / (xs.length - 1)) * (W - L - R);
  const Y = (v) => T + (1 - v / (yMax || 1)) * (H - T - B);
  const ticks = [0, yMax / 2, yMax];
  return (
    <svg className="lc" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={ariaLabel}>
      <defs>
        {/* the area fades from the line down to nothing */}
        <linearGradient id={`lcf-${gid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0a84ff" stopOpacity="0.32" />
          <stop offset="1" stopColor="#0a84ff" stopOpacity="0" />
        </linearGradient>
      </defs>
      {ticks.map((t) => (
        <g key={t}><line x1={L} x2={W - R} y1={Y(t)} y2={Y(t)} className="lc-grid" />
          <text x={L - 6} y={Y(t) + 3} className="lc-ytick">{yFormat(t)}</text></g>
      ))}
      {xs.map((x, i) => <text key={x} x={X(i)} y={H - 8} className="lc-xtick">{x}</text>)}
      {series.map((s, si) => {
        const pts = s.values.map((v, i) => [X(i), Y(v ?? 0)]);
        const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0]},${p[1]}`).join(' ');
        return (
          <g key={s.name} className={`lc-series tone-${s.tone ?? 'accent'}`} style={{ '--k': si }}>
            {s.area && <path d={`${d} L${pts[pts.length - 1][0]},${Y(0)} L${pts[0][0]},${Y(0)} Z`} className="lc-area" fill={`url(#lcf-${gid})`} />}
            <path d={d} className="lc-line" pathLength="100" />
            {pts.map((p, i) => (
              <circle key={i} cx={p[0]} cy={p[1]} r="3.6" className="lc-dot" style={{ '--i': i }}>
                <title>{`${s.name} at ${xs[i]}: ${yFormat(s.values[i] ?? 0)}`}</title>
              </circle>
            ))}
          </g>
        );
      })}
    </svg>
  );
}

/** Vertical bars over labelled windows; one can be highlighted. */
export function BarTimeline({ bars, highlight, format = (v) => v, height = 140, ariaLabel }) {
  const max = Math.max(...bars.map((b) => b.value), 1e-9);
  return (
    <div className="bt" role="img" aria-label={ariaLabel} style={{ height }}>
      {bars.map((b, i) => (
        <div key={b.key} className={`bt-col${b.key === highlight ? ' is-on' : ''}`} style={{ '--i': i }}>
          <span className="bt-val">{format(b.value)}</span>
          <div className="bt-bar" style={{ '--h': b.value / max }} />
          <span className="bt-lab">{b.label}</span>
        </div>
      ))}
    </div>
  );
}
