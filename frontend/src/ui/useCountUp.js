import { useEffect, useRef, useState } from 'react';

const reduce = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * A number that counts up to its value when it first appears. Under reduced
 * motion, or with no value, it simply shows the value.
 */
const easeOutCubic = (k) => 1 - Math.pow(1 - k, 3);

export function useCountUp(value, { duration = 900, decimals = 2, run = true, easing = easeOutCubic } = {}) {
  const still = reduce() || value == null;
  const [shown, setShown] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (still || !run) return undefined;
    let raf = 0;
    const start = performance.now(), a = from.current;
    const tick = (t) => {
      const k = Math.min(1, (t - start) / duration), e = easing(k);
      setShown(a + (value - a) * e);
      if (k < 1) raf = requestAnimationFrame(tick); else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, still, run, easing]);   // easing is a fixed, top-level function
  if (value == null) return '—';
  return Number(still ? value : shown).toFixed(decimals);
}
