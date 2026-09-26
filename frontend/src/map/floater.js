/**
 * A macOS-style popover that floats above the whole app, anchored to a point on
 * the map. It is not clipped by the map's frame: like a native popover it can
 * extend past the view it points into, and it stays inside the window instead.
 * It follows its anchor as the map moves, time plays or the page scrolls, flips
 * below the anchor when there is no room above, and hides while the anchor is
 * out of the map's view.
 */
export class Floater {
  constructor(map, { className = '', closeButton = false, interactive = true, onClose } = {}) {
    this.map = map;
    this.lngLat = null;
    this.onClose = onClose;
    const el = document.createElement('div');
    el.className = `rfloat ${className}`;
    el.style.pointerEvents = interactive ? 'auto' : 'none';
    el.innerHTML = '<div class="rfloat-arrow"></div><div class="rfloat-card">'
      + (closeButton ? '<button type="button" class="rfloat-close" aria-label="Close">'
        + '<svg viewBox="0 0 10 10" width="8" height="8" aria-hidden="true"><path d="M1.5 1.5l7 7M8.5 1.5l-7 7"/></svg></button>' : '')
      + '<div class="rfloat-body"></div></div>';
    document.body.appendChild(el);
    this.el = el;
    this.body = el.querySelector('.rfloat-body');
    el.querySelector('.rfloat-close')?.addEventListener('click', () => this.remove());
    this.place = this.place.bind(this);
    map.on('move', this.place);
    window.addEventListener('scroll', this.place, true);   // any scrolling pane, capture phase
    window.addEventListener('resize', this.place);
  }

  setHTML(html) {
    if (this._html !== html) { this.body.innerHTML = html; this._html = html; }
    return this;
  }

  at(lngLat) {
    this.lngLat = lngLat;
    this.place();
    return this;
  }

  place() {
    if (!this.el || !this.lngLat) return;
    const r = this.map.getContainer().getBoundingClientRect();
    const p = this.map.project(this.lngLat);
    const x = r.left + p.x, y = r.top + p.y;
    const inView = x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
    this.el.style.visibility = inView ? '' : 'hidden';
    if (!inView) return;
    const w = this.el.offsetWidth, h = this.el.offsetHeight, gap = 16, m = 8;
    const below = y - h - gap < m;                   // no room above: flip below
    const top = below ? y + gap : y - h - gap;
    const left = Math.max(m, Math.min(window.innerWidth - w - m, x - w / 2));
    this.el.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`;
    this.el.classList.toggle('is-below', below);
    this.el.style.setProperty('--arrow-x', `${Math.round(Math.max(14, Math.min(w - 14, x - left)))}px`);
  }

  remove() {
    if (!this.el) return;
    this.map.off('move', this.place);
    window.removeEventListener('scroll', this.place, true);
    window.removeEventListener('resize', this.place);
    this.el.remove();
    this.el = null;
    this.onClose?.();
  }
}
