import { Children, useCallback, useEffect, useRef, useState } from 'react';

/**
 * Height-balanced masonry.
 *
 * Panels are rendered once, in a flat grid, and positioned by measuring what
 * the browser actually laid out — no hidden duplicate to measure, which is
 * what broke the previous attempt. Heights change per case (the fragility
 * panel grows when a flip is found), so assignment is recomputed whenever any
 * panel resizes.
 */
export default function Masonry({ children, gap = 18 }) {
  const items = Children.toArray(children).filter(Boolean);
  const hostRef = useRef(null);
  const [layout, setLayout] = useState(null);

  const recompute = useCallback(() => {
    const host = hostRef.current;
    if (!host) return;
    const kids = Array.from(host.children);
    if (!kids.length) return;

    const width = host.getBoundingClientRect().width;
    const n = width < 780 ? 1 : width < 1180 ? 2 : 3;
    const colW = (width - gap * (n - 1)) / n;

    const tops = Array(n).fill(0);
    const lastIn = Array(n).fill(-1);
    const pos = kids.map((el, i) => {
      // measure the panel, not the wrapper: the wrapper carries the stretch
      // we applied last pass, and feeding that back in makes the layout drift
      const inner = el.firstElementChild ?? el;
      const h = inner.getBoundingClientRect().height;
      const c = tops.indexOf(Math.min(...tops));
      const p = { left: c * (colW + gap), top: tops[c], width: colW };
      tops[c] += h + gap;
      lastIn[c] = i;
      return p;
    });

    // Greedy packing cannot equalise columns: each one ends wherever its last
    // panel happens to end. Stretching that final panel down to the tallest
    // column squares the bottom edge. Panel content is top-aligned, so the
    // extra height reads as padding inside a bordered box.
    // Greedy packing leaves whichever column got the last tall panel sticking
    // out. Repeatedly move the final panel of the tallest column to the
    // shortest one while that genuinely narrows the spread. Pure repositioning
    // — no panel is stretched, so nothing ends up hollow.
    const heights = kids.map((el) => (el.firstElementChild ?? el).getBoundingClientRect().height);
    const colOf = pos.map((p) => Math.round(p.left / (colW + gap)));

    for (let pass = 0; pass < 12; pass += 1) {
      const colTops = Array(n).fill(0);
      kids.forEach((_, i) => { colTops[colOf[i]] += heights[i] + gap; });
      const tall = colTops.indexOf(Math.max(...colTops));
      const short = colTops.indexOf(Math.min(...colTops));
      if (tall === short) break;
      const spread = colTops[tall] - colTops[short];
      let moved = -1;
      for (let i = kids.length - 1; i >= 0; i -= 1) {
        if (colOf[i] !== tall) continue;
        const after = Math.abs((colTops[tall] - heights[i]) - (colTops[short] + heights[i]));
        if (after < spread) { moved = i; break; }
      }
      if (moved < 0) break;
      colOf[moved] = short;
    }

    const finalTops = Array(n).fill(0);
    kids.forEach((_, i) => {
      pos[i].left = colOf[i] * (colW + gap);
      pos[i].top = finalTops[colOf[i]];
      finalTops[colOf[i]] += heights[i] + gap;
    });

    setLayout({ pos, height: Math.max(...finalTops) - gap, colW });
  }, [gap]);

  useEffect(() => {
    recompute();
    const ro = new ResizeObserver(recompute);
    const host = hostRef.current;
    if (host) {
      ro.observe(host);
      Array.from(host.children).forEach((c) => ro.observe(c));
    }
    // fonts land after first paint and change every panel's height
    if (document.fonts?.ready) document.fonts.ready.then(recompute);
    window.addEventListener('resize', recompute);
    return () => { ro.disconnect(); window.removeEventListener('resize', recompute); };
  }, [recompute, items.length]);

  return (
    <div
      className={`masonry${layout ? ' is-placed' : ''}`}
      ref={hostRef}
      style={layout ? { height: layout.height } : undefined}
    >
      {items.map((child, i) => (
        <div
          className="masonry-item"
          key={i}
          style={
            layout
              ? {
                  position: 'absolute',
                  left: layout.pos[i].left,
                  top: layout.pos[i].top,
                  width: layout.pos[i].width,
                  minHeight: layout.pos[i].minHeight,
                }
              : undefined
          }
        >
          {child}
        </div>
      ))}
    </div>
  );
}
