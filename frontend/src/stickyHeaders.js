/**
 * The scroll-edge effect for pinned card headers, as macOS and iOS do it: a
 * header is clear while its card sits in place, and takes the pane's own solid
 * background - with a hairline and a soft fade below - only while that card's
 * content is actually scrolling beneath it. A translucent blur here smeared
 * whatever passed under it (map imagery, charts) into a textured band.
 */
export function attachStickyHeaders(pane) {
  if (!pane) return () => {};
  let raf = 0;
  const update = () => {
    raf = 0;
    const top = pane.getBoundingClientRect().top;
    for (const head of pane.querySelectorAll('.panel > .panel-head')) {
      const card = head.parentElement.getBoundingClientRect();
      const h = head.getBoundingClientRect();
      // stuck: pinned to the pane's top while its card has scrolled past it
      head.classList.toggle('is-stuck', h.top <= top + 0.5 && card.top < top - 1 && card.bottom > h.bottom);
    }
  };
  const onScroll = () => { if (!raf) raf = requestAnimationFrame(update); };
  pane.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  const ro = new ResizeObserver(onScroll);
  ro.observe(pane);
  update();
  return () => {
    cancelAnimationFrame(raf);
    pane.removeEventListener('scroll', onScroll);
    window.removeEventListener('resize', onScroll);
    ro.disconnect();
  };
}
