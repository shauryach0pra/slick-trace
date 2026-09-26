/**
 * Scroll-triggered motion: each card is marked is-inview the first time it
 * scrolls into view, and its animations - charts drawing, bars growing, the
 * card fading up - wait until then, instead of playing unseen on load.
 * Without IntersectionObserver, or under reduced motion, everything is shown.
 */
const CARDS = '.finder-features > .panel, .finder-features > .card-row > .panel, .finder-details > .cg, .finder-details > .panel';

export function attachInView(root) {
  if (!root) return () => {};
  const all = () => root.querySelectorAll(CARDS);
  if (typeof IntersectionObserver === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    all().forEach((el) => el.classList.add('is-inview'));
    return () => {};
  }
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) { e.target.classList.add('is-inview'); io.unobserve(e.target); }
    }
  }, { threshold: 0.12 });
  const watch = () => all().forEach((el) => { if (!el.classList.contains('is-inview') && !el.dataset.inviewWatched) { el.dataset.inviewWatched = '1'; io.observe(el); } });
  watch();
  // cards can arrive later (lazy chunks, data loading): watch them as they appear
  const mo = new MutationObserver(watch);
  mo.observe(root, { childList: true, subtree: true });
  return () => { io.disconnect(); mo.disconnect(); };
}
