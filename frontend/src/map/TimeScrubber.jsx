import './TimeScrubber.css';

/**
 * Time control for the replay, -24 h to +24 h around the image, laid out like Apple's video player
 * controls: one slim bar - the transport (step back, play, step forward), the time, a thin track that
 * fills as it plays with the release and the image marked on it, and the playback speed. A pill says
 * what the hour shows: modelled before the image, the image itself, or modelled after it.
 * A native range input over the track keeps it keyboard operable (arrows, Home, End, Page keys).
 */
function Glyph({ name }) {
  const paths = {
    play: <path d="M6 3.8v12.4c0 .6.7 1 1.2.7l9.6-6.2c.5-.3.5-1 0-1.4L7.2 3.1C6.7 2.8 6 3.2 6 3.8Z" fill="currentColor" />,
    pause: <><rect x="5" y="3.5" width="3.6" height="13" rx="1.1" fill="currentColor" /><rect x="11.4" y="3.5" width="3.6" height="13" rx="1.1" fill="currentColor" /></>,
    back: <path d="M12.5 4.5 7 10l5.5 5.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />,
    fwd: <path d="M7.5 4.5 13 10l-5.5 5.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />,
  };
  return <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">{paths[name]}</svg>;
}

const hhmm = (d) => `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
const day = (d) => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const signed = (v) => (v === 0 ? '0 h' : `${v > 0 ? '+' : '−'}${Math.abs(v)} h`);

export default function TimeScrubber({ t, pos, onChange, min, max, playing, onPlay, speed, onSpeed,
                                       acquiredUtc, marks = [] }) {
  const span = max - min;
  const at = pos ?? t;                         // the knob follows the continuous clock
  const pct = (v) => `${((v - min) / span) * 100}%`;
  const when = new Date(new Date(acquiredUtc).getTime() + t * 3600e3);
  const rel = t === 0 ? 'image time' : `${t > 0 ? '+' : '−'}${Math.abs(t)} h`;
  const phase = t < 0 ? 'before' : t === 0 ? 'image' : 'after';
  const state = t === 0 ? 'Image time'
    : `Modelled · ${Math.abs(t)} h ${t < 0 ? 'before' : 'after'} the image`;
  const allMarks = [...marks, { t: 0, label: 'image', kind: 'image' }];

  return (
    <div className="scrub" data-phase={phase}>
      <div className="scrub-bar">
        <div className="scrub-transport">
          <button type="button" className="scrub-btn" onClick={() => onChange(Math.max(min, t - 1))}
                  disabled={t <= min} aria-label="One hour earlier"><Glyph name="back" /></button>
          <button type="button" className="scrub-btn scrub-play" onClick={onPlay}
                  aria-label={playing ? 'Pause' : 'Play'}><Glyph name={playing ? 'pause' : 'play'} /></button>
          <button type="button" className="scrub-btn" onClick={() => onChange(Math.min(max, t + 1))}
                  disabled={t >= max} aria-label="One hour later"><Glyph name="fwd" /></button>
        </div>

        <div className="scrub-now" aria-live="polite">
          <b>{hhmm(when)}</b><small>{day(when)} · UTC</small>
        </div>

        <div className="scrub-track-wrap">
          <div className="scrub-track" aria-hidden="true">
            <span className="scrub-rail" />
            <span className="scrub-fill" style={{ width: pct(at) }} />
            {allMarks.map((m) => (
              <span key={m.label} className={`scrub-mark is-${m.kind ?? 'release'}`} style={{ left: pct(m.t) }}>
                <span className="scrub-mark-label">{m.label}</span>
              </span>
            ))}
            <span className="scrub-knob" style={{ left: pct(at) }} />
          </div>
          <input className="scrub-input" type="range" min={min} max={max} step={1} value={t}
                 onChange={(e) => onChange(Number(e.target.value))}
                 aria-label="Replay time, hours from the image"
                 aria-valuetext={`${rel}, ${hhmm(when)} UTC ${day(when)}`} />
          <div className="scrub-ends" aria-hidden="true"><span>{signed(min)}</span><span>{signed(max)}</span></div>
        </div>

        <button type="button" className="scrub-speed" onClick={onSpeed}
                aria-label={`Playback speed ${speed}x`}>{speed}×</button>
      </div>
      <div className={`scrub-state is-${phase}`}>{state}</div>
    </div>
  );
}
