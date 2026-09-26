import { useEffect, useRef } from 'react';
import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import './tour.css';

/**
 * Guided tour: one exemplar of each case family, found from the case list's
 * `family` field (the generator's case plan), not assumed.
 *
 * At each stop the tour drives the Replay Map through its OWN controls - time
 * bar, play, speed - exactly as a person would; it changes no card logic. It
 * plays from -24 h and freezes on the frame where the top-ranked candidate is
 * inside the origin envelope nearest the start of its best-fitting release,
 * computed from attribution_result.json and the envelope timeline. Where no
 * vessel is named, it freezes on the image instead: freezing on the best-scoring
 * vessel would suggest an attribution the analysis declined to make.
 *
 * Advance is manual only: Space, the right arrow, Next, or a click anywhere.
 */

const ORDER = [
  { family: 'decoy', prefer: 'case_0001', title: 'A decoy nearby',
    notice: 'The vessel nearest the slick when the image was taken is not the one that released it.' },
  { family: 'moving_discharge', prefer: 'case_0002', title: 'A discharge under way',
    notice: 'The oil was released while the vessel was moving, not while it was stopped.' },
  { family: 'crowded', prefer: 'case_0004', title: 'Crowded traffic',
    notice: 'Many vessels passed through the area the oil could have come from.' },
  { family: 'along_track_ribbon', prefer: 'case_0009', title: 'A ribbon along a track',
    notice: 'A long release, laid out along the vessel’s route.' },
  { family: 'absent_source', prefer: 'case_0006', title: 'The source is not in the data',
    notice: 'Whatever released this oil is not among the vessels the data shows.' },
];

const ms = (s) => new Date(s).getTime();
const hhmm = (t) => new Date(t).toISOString().slice(11, 16);
const sleep = (n) => new Promise((r) => setTimeout(r, n));
const esc = (x) => String(x).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

async function waitFor(test, timeout = 15000) {
  const t0 = performance.now();
  while (performance.now() - t0 < timeout) { if (test()) return true; await sleep(60); }
  return false;
}

/** The frame to freeze on, from the ranking and the envelope timeline. */
function freezeFor(c, env) {
  const at = c.attribution;
  if (!at?.ranking?.length || at.unknown_source) return { hours: 0, named: false };
  const top = at.ranking[0];
  const release = Math.round((ms(c.meta.acquired_utc) - ms(top.release_start)) / 3600e3);
  const inside = (env?.frames ?? [])
    .filter((f) => f.vessels.some((v) => v.vessel_key === top.vessel_key && v.at_this_time === 'inside'))
    .map((f) => Math.abs(Math.round(f.hours_before_acquisition)));
  if (!inside.length) return { hours: 0, named: true };
  const hours = inside.reduce((a, b) => (Math.abs(b - release) < Math.abs(a - release)
    || (Math.abs(b - release) === Math.abs(a - release) && b < a) ? b : a));
  return { hours, named: true };
}

function stopText(stop, c, fz, others) {
  const at = c.attribution, nb = c.baseline, top = at.ranking[0];
  const nearest = nb?.ranking?.[0];
  if (!fz.named) {
    const wrong = others.filter((o) => o.named);
    return `<p>${esc(stop.notice)}</p><p>Every candidate fits below the ${at.abstention_iou_gate} fit gate `
      + `(best mean IoU ${top?.mean_iou?.toFixed(2) ?? '—'}), so <b>no vessel is named</b>: declining is the answer.</p>`
      + '<p class="st-when">Frozen at the image.</p>'
      + (wrong.length ? `<p class="st-caveat">In this family's other case, ${wrong.map((o) => esc(o.id.replace('_', ' '))).join(', ')}, `
        + 'a passing vessel clears the gate and is wrongly named: a known limitation, recorded as A10.</p>' : '');
  }
  const t = ms(c.meta.acquired_utc) - fz.hours * 3600e3;
  const same = nearest && nearest.vessel_key === at.top_candidate_id;
  return `<p>${esc(stop.notice)}</p><p>Forward replay names <b>${esc(top.vessel_key)}</b> `
    + `(mean IoU ${top.mean_iou.toFixed(2)}, best of ${at.ranking.length} replayed). `
    + (nearest ? (same ? 'Here the nearest vessel is the same one.'
      : `The vessel nearest the slick at image time was ${esc(nearest.vessel_key)}.`) : '') + '</p>'
    + `<p class="st-when">Frozen at ${hhmm(t)} UTC (−${fz.hours} h): ${esc(top.vessel_key)} is inside the origin `
    + 'envelope as its best-fitting release begins.</p>';
}

function setRange(v) {
  const el = document.querySelector('.scrub-input');
  if (!el) return;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, String(v));
  el.dispatchEvent(new Event('input', { bubbles: true }));
}

/** Scroll only the evidence column: scrollIntoView could move the locked window. */
function scrollPaneTo(sel) {
  const pane = document.querySelector('.finder-features'), el = document.querySelector(sel);
  if (!pane || !el) return;
  const top = el.getBoundingClientRect().top - pane.getBoundingClientRect().top + pane.scrollTop - 90;
  pane.scrollTo({ top, behavior: 'auto' });
}

// ---- the spotlight: a blurred, dimmed scrim with a cut-out, and a glowing ring

function roundedRect(x, y, w, h, r) {
  return `M${x + r},${y}H${x + w - r}A${r},${r} 0 0 1 ${x + w},${y + r}V${y + h - r}A${r},${r} 0 0 1 ${x + w - r},${y + h}`
    + `H${x + r}A${r},${r} 0 0 1 ${x},${y + h - r}V${y + r}A${r},${r} 0 0 1 ${x + r},${y}Z`;
}

function makeSpotlight() {
  const scrim = document.createElement('div'); scrim.className = 'st-scrim';
  const glow = document.createElement('div'); glow.className = 'st-glow';
  document.body.append(scrim, glow);
  let target = null;
  const place = () => {
    const W = window.innerWidth, H = window.innerHeight;
    if (!target) { scrim.style.clipPath = 'none'; glow.style.opacity = '0'; return; }
    const r = target.getBoundingClientRect(), p = 10, rad = 16;
    const x = r.left - p, y = r.top - p, w = r.width + 2 * p, h = r.height + 2 * p;
    scrim.style.clipPath = `path(evenodd, "M0,0H${W}V${H}H0Z ${roundedRect(x, y, w, h, rad)}")`;
    Object.assign(glow.style, { opacity: '1', left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${h}px` });
  };
  window.addEventListener('resize', place);
  window.addEventListener('scroll', place, true);
  return {
    focus(el) { target = el; place(); },
    place,
    remove() { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); scrim.remove(); glow.remove(); },
  };
}

export default function Tour({ incidents, api, selectCase, onExit }) {
  const exitRef = useRef(onExit);
  useEffect(() => { exitRef.current = onExit; }, [onExit]);

  useEffect(() => {
    let alive = true, token = 0, d = null;
    const spot = makeSpotlight();
    // driver.js's overlay covers the whole page, header included, so the top-bar
    // button cannot be clicked during a tour: a floating Exit Tour sits above it
    const exitBtn = document.createElement('button');
    exitBtn.type = 'button';
    exitBtn.className = 'st-exit';
    exitBtn.textContent = 'Exit Tour';
    exitBtn.addEventListener('click', () => { if (d?.isActive()) d.destroy(); else exitRef.current?.(); });
    document.body.append(exitBtn);
    const byFamily = (f) => incidents.filter((i) => i.family === f);

    (async () => {
      // stops: one exemplar per family present in the case list
      const stops = [];
      for (const o of ORDER) {
        const members = byFamily(o.family);
        if (!members.length) continue;
        const id = (members.find((m) => m.incident_id === o.prefer) ?? members[0]).incident_id;
        const [c, env] = await Promise.all([api.case(id), api.envelopeTimeline(id).catch(() => null)]);
        const others = await Promise.all(members.filter((m) => m.incident_id !== id).map(async (m) => {
          const oc = await api.case(m.incident_id).catch(() => null);
          return { id: m.incident_id, named: oc ? !oc.attribution?.unknown_source : false };
        }));
        const fz = freezeFor(c, env);
        stops.push({ ...o, id, fz, text: stopText(o, c, fz, others) });
      }
      if (!alive) return;

      const plan = [
        { el: '.finder-sidebar', title: 'A guided tour',
          body: `<p>${stops.length} kinds of case, one example of each. At every stop the replay plays and then freezes on the `
            + 'moment the analysis turns on.</p><p class="st-keys">Space or → to continue · ← back · Esc to leave</p>',
          side: 'right' },
        ...stops.map((s, i) => ({ el: '.rmap', caseId: s.id, freeze: -s.fz.hours, side: 'left',
          title: `${i + 1} · ${s.title}`, body: `<p class="st-case">${esc(s.id.replace('_', ' '))}</p>${s.text}` })),
        { el: '.cgx', title: 'Every finding, traced', side: 'left',
          body: '<p>Each case ends in the Conclusion Graph: detection, filtering, replay, fragility, finding. Click a stage to '
            + 'open its evidence. Start the tour again any time from the top bar.</p>' },
      ];

      const slider = () => Number(document.querySelector('.scrub-input')?.value);
      const playing = () => document.querySelector('.scrub-play')?.getAttribute('aria-label') === 'Pause';
      // Settle on an hour: the card applies a pause asynchronously, and a seek sent
      // in the same moment can be cancelled when the pause lands - so set the
      // bar, then confirm it arrived, and retry if it did not.
      const settleOn = async (h, my) => {
        for (let k = 0; k < 4 && my === token; k += 1) {
          setRange(h);
          if (await waitFor(() => my !== token || slider() === h, 2500)) return;
        }
      };
      const playTo = async (h, my) => {
        await settleOn(-24, my);                         // rewind, and wait until it is really there
        if (my !== token) return;
        const speed = document.querySelector('.scrub-speed');
        if (speed?.textContent.trim().startsWith('1')) speed.click();
        if (!playing()) document.querySelector('.scrub-play')?.click();
        await waitFor(() => my !== token || slider() >= h, 60000);
        if (playing()) document.querySelector('.scrub-play')?.click();
        await waitFor(() => my !== token || !playing(), 2000);
        await sleep(250);                                // let the pause land before seeking
        await settleOn(h, my);                           // land exactly on the computed frame
      };

      const go = async (i) => {
        if (!d) return;
        if (i >= plan.length) { d.destroy(); return; }
        if (i < 0) return;
        const my = ++token;
        const step = plan[i];
        document.querySelector('.driver-popover')?.classList.add('is-busy');
        if (step.caseId) {
          selectCase(step.caseId);
          await waitFor(() => {
            const fc = document.querySelector('.finder-content');
            return fc?.dataset.case === step.caseId && !fc.classList.contains('is-leaving')
              && document.querySelector('.rmap-canvas canvas') && document.querySelector('.scrub-input');
          });
          scrollPaneTo('.rmap');
          await sleep(200);
        }
        if (my !== token || !d) return;
        if (d.isActive()) d.moveTo(i); else d.drive(i);
        if (step.caseId) playTo(step.freeze, my);
      };

      d = driver({
        steps: plan.map((p) => ({ element: () => document.querySelector(p.el),
          popover: { title: p.title, description: p.body, side: p.side, align: 'start' } })),
        showProgress: true, progressText: '{{current}} of {{total}}',
        nextBtnText: 'Next', prevBtnText: 'Back', doneBtnText: 'Finish',
        overlayOpacity: 0, overlayClickBehavior: 'nextStep', stagePadding: 10, stageRadius: 16,
        smoothScroll: false, disableActiveInteraction: true, popoverClass: 'st-pop', popoverOffset: 18,
        onNextClick: () => go((d.getActiveIndex() ?? -1) + 1),
        onPrevClick: () => go((d.getActiveIndex() ?? 1) - 1),
        onHighlighted: (el) => spot.focus(el),
        onDestroyed: () => { token += 1; spot.focus(null); if (alive) exitRef.current?.(); },
      });
      const onKey = (e) => {
        if (e.key !== ' ' || /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName ?? '')) return;
        e.preventDefault();
        go((d.getActiveIndex() ?? -1) + 1);
      };
      document.addEventListener('keydown', onKey);
      d.__offKey = () => document.removeEventListener('keydown', onKey);
      go(0);
    })();

    return () => {
      alive = false;
      token += 1;
      d?.__offKey?.();
      if (d?.isActive()) d.destroy();
      spot.remove();
      exitBtn.remove();
      document.scrollingElement?.scrollTo(0, 0);        // never leave the window shifted
    };
  }, [incidents, api, selectCase]);

  return null;
}
