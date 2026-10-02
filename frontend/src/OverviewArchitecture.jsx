/**
 * How Slick Trace works, in the dashboard's own language: the pipeline as Conclusion-Graph-style stage
 * cards joined by live connectors; then, as hairline sections like the case page's, what goes in, what
 * comes out and what it is built with; then the figures that make it practical, all in one style.
 * Every statement is true of the system as built (synthetic benchmark inputs; an overlap, boundary and
 * area fit; measured figures).
 */
const ICON = {
  radar: <path d="M4 15a8 8 0 0 1 16 0M7.5 15a4.5 4.5 0 0 1 9 0M12 15v4M9 19h6M12 11.5v.01" />,
  ship: <path d="M4 15.5 5.5 19h13l1.5-3.5-8-2.5-8 2.5ZM7 14V9h10v5M12 5v4" />,
  wave: <path d="M3 9c2 0 2-2 4.5-2S10 9 12 9s2-2 4.5-2S19 9 21 9M3 15c2 0 2-2 4.5-2S10 15 12 15s2-2 4.5-2 2.5 2 4.5 2" />,
  window: <path d="M4 5h16v14H4zM4 9h16M7 7h.01M9.5 7h.01" />,
  code: <path d="m9 8-4 4 4 4M15 8l4 4-4 4M13 6l-2 12" />,
  doc: <path d="M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 15h5M10 18h3" />,
};
function Icon({ name }) {
  return <span className="ovx-icon" aria-hidden="true"><svg viewBox="0 0 24 24">{ICON[name]}</svg></span>;
}

const STAGES = [
  { t: 'Detect and measure', h: '0.968 IoU', d: 'Lee filter, classical detector and a trained U-Net; area, axes, orientation' },
  { t: 'Trace back and filter', h: 'Origin envelope', d: 'Source region per hour; each vessel a candidate, excluded or unassessed' },
  { t: 'Forward replay', h: '6 forcing variants', d: "Each candidate's release drifted forward; ranked by overlap, boundary and area fit" },
  { t: 'Stress-test and abstain', h: '80 perturbed runs', d: 'The smallest change that flips the lead; no one named below the fit gate' },
];
const INPUTS = [
  ['radar', 'SAR radar imagery', 'Sentinel-1 / GeoTIFF · synthetic in the benchmark'],
  ['ship', 'AIS vessel tracks', '24 h before the image · MarineCadastre format'],
  ['wave', 'Currents and wind', 'Forcing fields · synthetic; reanalysis planned'],
];
const OUTPUTS = [
  ['window', 'Investigator dashboard', 'Replay map, fragility, exposure forecast'],
  ['code', 'API and cited answers', '31 routes · rule-based, no language model'],
  ['doc', 'PDF dossier', 'Four pages · SHA-256 checksums'],
];
const STACK = [
  ['Pipeline', ['Python', 'NumPy', 'SciPy']],
  ['Detection', ['PyTorch']],
  ['Service', ['FastAPI', 'Pydantic']],
  ['Interface', ['React', 'Vite', 'MapLibre GL']],
  ['Deploy', ['Docker']],
];
const FACTS = [
  ['7 of 7', 'sources found · nearest ship 0 of 7'],
  ['23 s', 'per case on one CPU core'],
  ['359', 'automated tests'],
  ['Offline', 'can run with no network'],
];

function Rows({ items }) {
  return (
    <ul className="ovx-rows">
      {items.map(([icon, t, s]) => (
        <li key={t}><Icon name={icon} /><span><b>{t}</b><span>{s}</span></span></li>
      ))}
    </ul>
  );
}

export default function ArchitecturePanel() {
  return (
    <section className="ovx" aria-label="How Slick Trace works">
      <div className="ovx-sec">
        <div className="ovx-head"><h2>Pipeline</h2><span className="ovx-tag"><i />From a satellite alert to a ranked lead</span></div>
        <ol className="ovx-flow">
          {STAGES.map((s, i) => (
            <li key={s.t} className="ovx-step" style={{ '--k': i }}>
              {i > 0 && <span className="ovx-link" aria-hidden="true"><span /></span>}
              <div className="ovx-node">
                <span className="ovx-node-head"><span className="ovx-dot">{i + 1}</span><span className="ovx-title">{s.t}</span></span>
                <span className="ovx-headline">{s.h}</span>
                <span className="ovx-detail">{s.d}</span>
              </div>
            </li>
          ))}
        </ol>
      </div>
      <div className="ovx-trio">
        <div className="ovx-sec"><div className="ovx-head"><h2>Data in</h2></div><Rows items={INPUTS} /></div>
        <div className="ovx-sec"><div className="ovx-head"><h2>Out to the investigator</h2></div><Rows items={OUTPUTS} /></div>
        <div className="ovx-sec">
          <div className="ovx-head"><h2>Built with</h2></div>
          <dl className="ovx-stack">
            {STACK.map(([k, v]) => (
              <div key={k}><dt>{k}</dt><dd>{v.map((x) => <span key={x} className="ovx-chip">{x}</span>)}</dd></div>
            ))}
          </dl>
        </div>
      </div>
      <div className="ovx-facts">
        {FACTS.map(([a, b]) => <div key={b} className="ovx-fact"><b>{a}</b><span>{b}</span></div>)}
      </div>
    </section>
  );
}
