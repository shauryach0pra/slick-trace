/**
 * The case page's playback, as a function of time: 1x (an hour every 0.7 s), easing to a third of that
 * speed within 1.2 h of each key moment (the image, and the case's release), from min to max hours.
 * The overview's replay tiles use it to play each case exactly as the case page's Play does.
 */
const RATE = 1 / 0.7;                                   // hours per second at 1x, as on the case page
const easeAt = (h, keys) => { const d = Math.min(...keys.map((k) => Math.abs(h - k))); return d >= 1.2 ? 1 : 0.32 + 0.68 * (d / 1.2) ** 2; };
export function playProfile(keys, min = -24, max = 24) {
  const ts = [0], hs = [min];
  for (let h = min, t = 0; h < max;) { const dh = Math.min(0.01, max - h); t += dh / (RATE * easeAt(h, keys)); h += dh; ts.push(t); hs.push(h); }
  const at = (x) => {                                  // the hour at x seconds into the play
    if (x <= 0) return min;
    if (x >= ts[ts.length - 1]) return max;
    let lo = 0, hi = ts.length - 1;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (ts[m] <= x) lo = m; else hi = m; }
    return hs[lo] + (hs[hi] - hs[lo]) * ((x - ts[lo]) / (ts[hi] - ts[lo] || 1));
  };
  const toImage = ts[Math.round((0 - min) / 0.01)] ?? 0;
  return { at, toImage, total: ts[ts.length - 1] };
}
// the reference: a case with a release mid-window; every named case takes this long to its image
export const REFERENCE = playProfile([0, -6]);
export const END_HOLD = 2.5;
export const LOOP_S = REFERENCE.total + END_HOLD;
