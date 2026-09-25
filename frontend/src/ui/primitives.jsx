/**
 * Generic building blocks every case card is composed from.
 *
 * Card: a section in the shell's hairline style, with title, badge, an
 * always-visible caption and a footnote. Stat: a value with its plain
 * caption underneath. BarList: ranked horizontal bars for either direction
 * of "better", with an optional gate marker. None of these compute anything
 * beyond scaling a bar to its row.
 */

import './ui.css';

export function Card({ title, badge, caption, footnote, className = '', children }) {
  return (
    <section className={`panel card ${className}`.trim()}>
      <div className="panel-head">
        <h2>{title}</h2>
        {badge}
      </div>
      {caption && <p className="card-caption">{caption}</p>}
      {children}
      {footnote && <p className="card-foot">{footnote}</p>}
    </section>
  );
}

const TONE = { neutral: 'tag', accent: 'tag tag-teal', warning: 'tag tag-amber' };

export function Badge({ tone = 'neutral', children }) {
  return <span className={TONE[tone] ?? TONE.neutral}>{children}</span>;
}

export function Stat({ label, value, caption, mono = false, text = false }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value${mono ? ' is-mono' : ''}${text ? ' is-text' : ''}`}>{value}</div>
      {caption && <div className="stat-caption">{caption}</div>}
    </div>
  );
}

export function StatGrid({ cols = 3, children }) {
  return <div className="stat-grid" style={{ '--cols': cols }}>{children}</div>;
}

export function EmptyState({ children }) {
  return <p className="card-empty">{children}</p>;
}

/**
 * rows: [{ key, value, sub }]. max defaults to the largest value. marker draws
 * a tick at a fixed value (a gate) in every row. highlightKey marks one row.
 */
export function BarList({ rows, max, marker, format, highlightKey, label }) {
  const scale = max ?? Math.max(...rows.map((r) => r.value), 1e-9);
  const pct = (v) => `${Math.max(0, Math.min(1, v / scale)) * 100}%`;
  return (
    <div className="barlist" role="table" aria-label={label}>
      {rows.map((r, i) => (
        <div role="row" key={r.key} style={{ '--i': i }}
             className={`bar-row${r.key === highlightKey ? ' is-top' : ''}`}>
          <span role="cell" className="bar-key">{r.key}</span>
          <span role="cell" className="bar-track" aria-hidden="true">
            <span className="bar-fill" style={{ width: pct(r.value) }} />
            {marker && <span className="bar-marker" style={{ left: pct(marker.value) }} />}
          </span>
          <span role="cell" className="bar-value">
            {format(r.value)}
            {r.sub && <span className="bar-sub">{r.sub}</span>}
          </span>
        </div>
      ))}
      {marker && (
        <div className="bar-legend" aria-hidden="true">
          <span className="bar-legend-tick" /> {marker.label}
        </div>
      )}
    </div>
  );
}

export function CaptionList({ items }) {
  return (
    <dl className="caption-list">
      {items.map(([term, text]) => (
        <div key={term}>
          <dt>{term}</dt>
          <dd>{text}</dd>
        </div>
      ))}
    </dl>
  );
}
