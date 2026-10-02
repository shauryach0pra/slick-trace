/**
 * How Slick Trace works, on one screen: what goes in, the four pipeline stages, what comes out,
 * the stack, and the figures that make it practical. Every statement is true of the system as
 * built: the benchmark's inputs are synthetic (with the real-data adapters that exist named), the
 * fit is an overlap, boundary and area score, and the figures are measured ones.
 */
const INPUTS = [
  { t: 'SAR radar imagery', s: 'Sentinel-1 / GeoTIFF scenes · synthetic in the benchmark' },
  { t: 'AIS vessel tracks', s: '24 h before the image · MarineCadastre format' },
  { t: 'Currents and wind', s: 'Forcing fields · synthetic in the benchmark; reanalysis planned' },
];
const STAGES = [
  { t: 'Detect and measure', s: 'Lee speckle filter, classical detector and a trained U-Net (0.968 IoU on unseen scenes) · area, axes, orientation' },
  { t: 'Trace back and filter', s: 'Origin envelope in space and time · each vessel a candidate, excluded or unassessed' },
  { t: 'Forward replay', s: "Each candidate's release drifted under six forcing variants · ranked by overlap, boundary and area fit" },
  { t: 'Stress-test and abstain', s: '80 perturbed runs per case · a fit gate names no one when no vessel fits' },
];
const OUTPUTS = [
  { t: 'Investigator dashboard', s: 'Replay map, fragility, exposure forecast, conclusion graph' },
  { t: 'API and cited answers', s: '31 API routes · rule-based questions, no language model' },
  { t: 'PDF dossier', s: 'Four pages · SHA-256 checksums on every file' },
];
const STACK = ['Python', 'NumPy · SciPy', 'PyTorch', 'FastAPI', 'Pydantic', 'React', 'Vite', 'MapLibre GL', 'Docker'];
const FACTS = [
  ['~23 s', 'per case on one CPU core'],
  ['Offline', 'can run with no network'],
  ['359', 'automated tests'],
  ['Hidden', 'answer key never visible to the method'],
];

function Arrow() {
  return (
    <span className="ova-arrow" aria-hidden="true">
      <svg viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </span>
  );
}

export default function ArchitecturePanel() {
  return (
    <section className="ova" aria-label="How Slick Trace works">
      <div className="ova-flow">
        <div className="ova-col">
          <h3 className="ova-label">Inputs</h3>
          {INPUTS.map((x) => <div key={x.t} className="ova-card is-in"><b>{x.t}</b><span>{x.s}</span></div>)}
        </div>
        <Arrow />
        <div className="ova-core">
          <h3 className="ova-label">The pipeline</h3>
          {STAGES.map((x, i) => (
            <div key={x.t} className="ova-step" style={{ '--k': i }}>
              <span className="ova-n">{i + 1}</span>
              <span><b>{x.t}</b><span>{x.s}</span></span>
            </div>
          ))}
          <div className="ova-stack">{STACK.map((s) => <span key={s} className="ova-chip">{s}</span>)}</div>
        </div>
        <Arrow />
        <div className="ova-col">
          <h3 className="ova-label">Outputs</h3>
          {OUTPUTS.map((x) => <div key={x.t} className="ova-card is-out"><b>{x.t}</b><span>{x.s}</span></div>)}
        </div>
      </div>
      <div className="ova-facts">
        {FACTS.map(([a, b]) => <div key={b} className="ova-fact"><b>{a}</b><span>{b}</span></div>)}
      </div>
    </section>
  );
}
