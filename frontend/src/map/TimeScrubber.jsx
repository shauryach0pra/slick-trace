import './TimeScrubber.css';

/**
 * Time control for the replay: -24 h to +24 h around the image, hour by hour.
 *
 * The track is coloured by what each stretch shows - modelled history before
 * the image, the observed image itself, modelled drift after it - so the
 * evidence status of any hour is visible before it is selected. A native range
 * input underneath keeps it keyboard operable (arrows, Home, End, Page keys)
 * with no extra handling; the buttons step, play and change speed.
 */
function Glyph({ name }) {
  const paths = {
    play: <path d="M5 3.5v9l7.5-4.5z" fill="currentColor" />,
    pause: <><rect x="4" y="3.5" width="3" height="9" rx="0.8" fill="currentColor" />
             <rect x="9" y="3.5" width="3" height="9" rx="0.8" fill="currentColor" /></>,
    back: <path d="M10.5 4 6 8l4.5 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />,
    fwd: <path d="M5.5 4 10 8l-4.5 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />,
  };
  return <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">{paths[name]}</svg>;
}

const hhmm = (d) => `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
const day = (d) => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });

export default function TimeScrubber({ t, pos, onChange, min, max, playing, onPlay, speed, onSpeed,
                                       acquiredUtc, marks = [] }) {
  const span = max - min;
  const at = pos ?? t;                         // the thumb follows the continuous clock
  const pct = (v) => `${((v - min) / span) * 100}%`;
  const when = new Date(new Date(acquiredUtc).getTime() + t * 3600e3);
  const rel = t === 0 ? 'image time' : `${t > 0 ? '+' : '−'}${Math.abs(t)} h`;
  const phase = t < 0 ? 'before' : t === 0 ? 'image' : 'after';

  return (
    <div className="scrub" data-phase={phase}>
      <div className="scrub-controls">
        <button type="button" className="scrub-btn" onClick={() => onChange(Math.max(min, t - 1))}
                disabled={t <= min} aria-label="One hour earlier"><Glyph name="back" /></button>
        <button type="button" className="scrub-btn scrub-play" onClick={onPlay}
                aria-label={playing ? 'Pause' : 'Play'}><Glyph name={playing ? 'pause' : 'play'} /></button>
        <button type="button" className="scrub-btn" onClick={() => onChange(Math.min(max, t + 1))}
                disabled={t >= max} aria-label="One hour later"><Glyph name="fwd" /></button>
        <button type="button" className="scrub-speed" onClick={onSpeed}
                aria-label={`Playback speed ${speed}x`}>{speed}×</button>
        <div className="scrub-readout" aria-live="polite">
          <span className="scrub-time">{hhmm(when)} <small>UTC · {day(when)}</small></span>
          <span className={`scrub-rel is-${phase}`}>{rel}</span>
        </div>
      </div>

      <div className="scrub-track-wrap">
        <div className="scrub-track" aria-hidden="true"
             style={{ '--zero': pct(0), '--pos': pct(at) }}>
          <span className="scrub-fill"
                style={{ left: pct(Math.min(at, 0)), width: `${(Math.abs(at) / span) * 100}%` }} />
          {marks.map((m) => (
            <span key={m.label} className="scrub-mark" style={{ left: pct(m.t) }} title={m.label}>
              <span className="scrub-mark-label">{m.label}</span>
            </span>
          ))}
          {Array.from({ length: span + 1 }, (_, i) => min + i).map((h) => (
            <span key={`tick${h}`} className={`scrub-tick${h % 6 === 0 ? ' is-major' : ''}`}
                  style={{ left: pct(h) }} />
          ))}
          <span className="scrub-zero" />
          <span className="scrub-thumb" />
        </div>
        <input className="scrub-input" type="range" min={min} max={max} step={1} value={t}
               onChange={(e) => onChange(Number(e.target.value))}
               aria-label="Replay time, hours from the image"
               aria-valuetext={`${rel}, ${hhmm(when)} UTC ${day(when)}`} />
        <div className="scrub-scale" aria-hidden="true">
          {/* deduplicated: before the forecast loads max is 0, and repeated values
              would share a key and leave a stale label behind */}
          {[...new Set([min, Math.round(min / 2), 0, Math.round(max / 2), max])].map((v) => (
            <span key={v} style={{ left: pct(v) }} className={v === 0 ? 'is-zero' : ''}>
              {v === 0 ? 'image' : `${v > 0 ? '+' : '−'}${Math.abs(v)} h`}
            </span>
          ))}
        </div>
        <div className="scrub-phases" aria-hidden="true">
          <span style={{ left: 0, width: pct(0) }}>modelled · where it came from</span>
          <span style={{ left: pct(0), right: 0 }}>modelled · where it goes</span>
        </div>
      </div>
    </div>
  );
}
