import { useEffect, useRef, useState } from 'react';

/** True once the element has scrolled into view (and from then on). */
export function useInView({ threshold = 0.3 } = {}) {
  const ref = useRef(null);
  const [seen, setSeen] = useState(() => typeof IntersectionObserver === 'undefined'
    || (typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches));
  useEffect(() => {
    if (seen || !ref.current) return undefined;
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setSeen(true); io.disconnect(); } }, { threshold });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [seen, threshold]);
  return [ref, seen];
}
