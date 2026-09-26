/**
 * Hover tilt for every card: the side under the pointer leans away, and a soft
 * light follows it. One listener for the whole app, throttled to animation
 * frames, writing only CSS variables - no layout, no card logic.
 *
 * Tilt scales with size (small tiles lean more, large cards barely) so big
 * panels never swing. The Replay Map card does not rotate at all - a skewed map
 * would put clicks off target - but keeps the light. Off with reduced motion.
 */
const SELECTOR = '.finder-features > .panel, .finder-details > .cg, .finder-details > .panel, .ov-tile';

export function attachTilt() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return () => {};
  let active = null, raf = 0, px = 0, py = 0;
  const reset = (el) => {
    el.classList.remove('is-tilting');
    el.style.setProperty('--rx', '0deg');
    el.style.setProperty('--ry', '0deg');
  };
  const apply = () => {
    raf = 0;
    if (!active || !active.isConnected) return;
    const r = active.getBoundingClientRect();
    const x = (px - r.left) / r.width, y = (py - r.top) / r.height;
    const still = !!active.querySelector('.rmap');                 // the map card: light, no rotation
    const max = still ? 0 : Math.min(10, 3600 / Math.max(r.width, r.height));
    // the side under the pointer recedes (measured): pointer right -> positive rotateY
    // pushes the right edge back; pointer at the top -> positive rotateX pushes the top back
    active.style.setProperty('--ry', `${((x - 0.5) * max).toFixed(2)}deg`);
    active.style.setProperty('--rx', `${((0.5 - y) * max).toFixed(2)}deg`);
    active.style.setProperty('--mx', `${(x * 100).toFixed(1)}%`);
    active.style.setProperty('--my', `${(y * 100).toFixed(1)}%`);
    active.classList.add('is-tilting');
  };
  const onMove = (e) => {
    const el = e.target.closest?.(SELECTOR) ?? null;
    if (el !== active) { if (active) reset(active); active = el; }
    if (!el) return;
    px = e.clientX; py = e.clientY;
    if (!raf) raf = requestAnimationFrame(apply);
  };
  const onLeave = () => { if (active) reset(active); active = null; };
  document.addEventListener('pointermove', onMove, { passive: true });
  document.addEventListener('pointerleave', onLeave);
  window.addEventListener('blur', onLeave);
  return () => {
    cancelAnimationFrame(raf);
    document.removeEventListener('pointermove', onMove);
    document.removeEventListener('pointerleave', onLeave);
    window.removeEventListener('blur', onLeave);
  };
}
