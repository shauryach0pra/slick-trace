import { useEffect, useState } from 'react';
import { useCountUp } from './useCountUp';
import { useInView } from './useInView';
import './viz.css';

/**
 * Shared visual primitives: a fit gauge, a count-up number, and the disclosure
 * that holds method notes. Every value they show is passed in from an artifact;
 * they only draw it.
 */
const reduce = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * A 270° ring for a 0-1 fit: the arc draws in to the value; a tick marks the
 * gate below which no vessel is named, and a dot marks the runner-up.
 */
export function FitGauge({ value, gate, secondary = null, tone = 'accent', size = 132, label = 'mean IoU', compact = false }) {
  // draws and counts when it scrolls into view, not unseen on load
  const [ref, seen] = useInView();
  const [drawn, setDrawn] = useState(reduce());
  useEffect(() => { if (!seen) return undefined; const id = requestAnimationFrame(() => setDrawn(true)); return () => cancelAnimationFrame(id); }, [seen]);
  const n = useCountUp(value, { decimals: 2, run: seen });
  const r = 46, c = 2 * Math.PI * r, span = 0.75;                 // 270° of the circle
  const at = (f) => {                                              // angle along the arc for a fraction
    const a = (135 + 270 * Math.max(0, Math.min(1, f))) * Math.PI / 180;
    return [60 + r * Math.cos(a), 60 + r * Math.sin(a)];
  };
  const [gx, gy] = at(gate), [gx2, gy2] = [60 + (r + 9) * Math.cos((135 + 270 * gate) * Math.PI / 180), 60 + (r + 9) * Math.sin((135 + 270 * gate) * Math.PI / 180)];
  const [gx1, gy1] = [60 + (r - 9) * Math.cos((135 + 270 * gate) * Math.PI / 180), 60 + (r - 9) * Math.sin((135 + 270 * gate) * Math.PI / 180)];
  const sec = secondary != null ? at(secondary) : null;
  return (
    <div ref={ref} className={`fitg is-${tone}${compact ? ' is-compact' : ''}`} style={{ width: size, height: size }}
         role="img" aria-label={`${label} ${value?.toFixed(2)}, fit gate ${gate}${secondary != null ? `, runner-up ${secondary.toFixed(2)}` : ''}`}>
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <defs>
          <linearGradient id={`fitg-${tone}`} x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" stopColor={tone === 'accent' ? '#0a84ff' : '#ff9f0a'} />
            <stop offset="1" stopColor={tone === 'accent' ? '#64d2ff' : '#ffd60a'} />
          </linearGradient>
        </defs>
        <circle cx="60" cy="60" r={r} className="fitg-track" strokeDasharray={`${c * span} ${c}`} transform="rotate(135 60 60)" />
        <circle cx="60" cy="60" r={r} className="fitg-arc" stroke={`url(#fitg-${tone})`} transform="rotate(135 60 60)"
                strokeDasharray={`${c * span * (drawn ? Math.max(0, Math.min(1, value ?? 0)) : 0)} ${c}`} />
        <line x1={gx1} y1={gy1} x2={gx2} y2={gy2} className="fitg-gate" />
        {sec && <circle cx={sec[0]} cy={sec[1]} r="3.4" className="fitg-sec" />}
        <circle cx={gx} cy={gy} r="0" />
      </svg>
      <div className="fitg-center">
        <span className="fitg-num">{n}</span>
        <span className="fitg-label">{label}</span>
      </div>
    </div>
  );
}

/** Method notes and definitions, folded away until asked for. */
export function HowMeasured({ children, title = 'How this is measured' }) {
  return (
    <details className="howto">
      <summary><span className="howto-chev" aria-hidden="true" />{title}</summary>
      <div className="howto-body">{children}</div>
    </details>
  );
}
