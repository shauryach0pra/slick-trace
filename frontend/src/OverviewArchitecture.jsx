/**
 * Slick Trace's system architecture, as a data-flow diagram: sources -> ingest and validate -> the
 * analysis pipeline -> the case store and API -> the clients, with the parts that ship in the Docker image
 * inside its boundary, and the quality gates beneath. Every box is a real component of the repository
 * (adapters, slicktrace_core stages, the FastAPI service, the React dashboard), worded as built: the
 * benchmark's inputs are synthetic, and the fit is an overlap, boundary and area score.
 */
const ICON = {
  radar: <path d="M4 15a8 8 0 0 1 16 0M7.5 15a4.5 4.5 0 0 1 9 0M12 15v4M9 19h6" />,
  ship: <path d="M4 15.5 5.5 19h13l1.5-3.5-8-2.5-8 2.5ZM7 14V9h10v5M12 5v4" />,
  wave: <path d="M3 9c2 0 2-2 4.5-2S10 9 12 9s2-2 4.5-2S19 9 21 9M3 15c2 0 2-2 4.5-2S10 15 12 15s2-2 4.5-2 2.5 2 4.5 2" />,
  globe: <path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM3 12h18M12 3c2.5 2.6 3.7 5.6 3.7 9s-1.2 6.4-3.7 9c-2.5-2.6-3.7-5.6-3.7-9S9.5 5.6 12 3Z" />,
  shield: <path d="M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6l-7-3ZM9 12l2 2 4-4" />,
  db: <path d="M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3Zm0 0v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3" />,
  server: <path d="M4 5h16v6H4zM4 13h16v6H4zM8 8h.01M8 16h.01" />,
  window: <path d="M4 5h16v14H4zM4 9h16M7 7h.01M9.5 7h.01" />,
  doc: <path d="M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 15h5M10 18h3" />,
  code: <path d="m9 8-4 4 4 4M15 8l4 4-4 4M13 6l-2 12" />,
};
const Icon = ({ name }) => <span className="arc-icon" aria-hidden="true"><svg viewBox="0 0 24 24">{ICON[name]}</svg></span>;
const Box = ({ icon, t, s }) => <div className="arc-box">{icon && <Icon name={icon} />}<span><b>{t}</b>{s && <span>{s}</span>}</span></div>;
const Link = () => <span className="arc-link" aria-hidden="true"><span /></span>;

const SOURCES = [['radar', 'SAR imagery', 'Sentinel-1 / GeoTIFF'], ['ship', 'AIS tracks', 'MarineCadastre CSV'],
  ['wave', 'Ocean forcing', 'Currents and wind'], ['globe', 'Geography', 'Coastline, sensitive areas']];
const CHECKS = ['GeoTIFF and AIS adapters', 'Radiometry check · DN, linear, dB', 'AIS fields vs ITU-R M.1371', 'MMSI structure check', 'Pydantic schema contracts'];
const STAGES = [
  ['Detect and measure', 'Lee filter · classical detector + U-Net · geometry'],
  ['Trace back and filter', 'Origin envelope · candidate / excluded / unassessed'],
  ['Forward replay', '6 forcing variants · overlap, boundary, area fit · abstention gate'],
  ['Stress-test', '80 perturbed runs · coverage-aware matching'],
  ['Forecast and report', '+6 / +12 / +24 h exposure · dossier'],
];
const GATES = ['359 automated tests', 'Leak audit on every validation', 'Byte-identical regeneration in CI', '38 documented claims verified'];

export default function ArchitecturePanel() {
  return (
    <section className="arc" aria-label="Slick Trace system architecture">
      <div className="arc-grid">
        <div className="arc-boundary" aria-hidden="true"><span>Docker image · CPU-only · offline-capable</span></div>

        <div className="arc-col arc-c1">
          <h3 className="arc-label">Data sources</h3>
          {SOURCES.map(([i, t, s]) => <Box key={t} icon={i} t={t} s={s} />)}
          <p className="arc-note">Synthetic in the benchmark</p>
        </div>
        <div className="arc-c2"><Link /></div>

        <div className="arc-col arc-c3">
          <h3 className="arc-label">Ingest and validate</h3>
          <div className="arc-box is-tall">
            <Icon name="shield" />
            <span><b>Adapters and checks</b>
              <ul>{CHECKS.map((c) => <li key={c}>{c}</li>)}</ul>
            </span>
          </div>
        </div>
        <div className="arc-c4"><Link /></div>

        <div className="arc-col arc-c5">
          <h3 className="arc-label">Analysis pipeline <span className="arc-mono">slicktrace_core</span></h3>
          <ol className="arc-chain">
            {STAGES.map(([t, s], i) => (
              <li key={t} style={{ '--k': i }}>
                {i > 0 && <span className="arc-vlink" aria-hidden="true"><span /></span>}
                <div className="arc-stage"><span className="arc-dot">{i + 1}</span><span><b>{t}</b><span>{s}</span></span></div>
              </li>
            ))}
          </ol>
        </div>
        <div className="arc-c6"><Link /></div>

        <div className="arc-col arc-c7">
          <h3 className="arc-label">Serve</h3>
          <Box icon="db" t="Case store" s="Artifacts + manifest · SHA-256 checksums" />
          <Box icon="server" t="FastAPI service" s="31 API routes · ground truth stripped" />
          <Box icon="code" t="Ask Slick Trace" s="Rule-based, cited · no language model" />
        </div>
        <div className="arc-c8"><Link /></div>

        <div className="arc-col arc-c9">
          <h3 className="arc-label">Clients</h3>
          <Box icon="window" t="Investigator dashboard" s="React · MapLibre GL" />
          <Box icon="doc" t="PDF dossier" s="Four pages" />
          <Box icon="code" t="Reports" s="JSON and Markdown" />
        </div>
      </div>

      <div className="arc-gates">
        <span className="arc-label">Quality gates</span>
        {GATES.map((g) => <span key={g} className="arc-gate"><i />{g}</span>)}
      </div>
    </section>
  );
}
