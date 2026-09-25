/**
 * Traffic filtering and run provenance.
 *
 * Two things a reviewer otherwise has to open the report to find: how many
 * vessels the space-time envelope actually removed (PS part (c) — "the
 * irrelevant traffic is to be filtered out"), and what identifies this run.
 * Checksums verify file integrity; they do not establish that an observation
 * is true.
 */
const STATE_COPY = {
  candidate: ['Candidate', 'compatible with the origin envelope at some time'],
  excluded: ['Excluded', 'track present throughout; never compatible'],
  unassessed: ['Unassessed', 'never inside where data exists; no track data for part or all of the window'],
};

export default function ProvenancePanel({ report, manifest }) {
  if (!report || !manifest) return null;
  const counts = report.historical_filtering?.status_counts ?? {};
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const meta = report.run_metadata ?? {};
  const nFiles = Object.keys(report.checksums_sha256 ?? {}).length;

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Traffic Filtering and Provenance</h2>
        <span className="tag tag-teal">{total} vessels</span>
      </div>

      <ul className="prov-states">
        {['candidate', 'excluded', 'unassessed'].map((k) => {
          const n = counts[k] ?? 0;
          const [label, note] = STATE_COPY[k];
          return (
            <li key={k} className={`prov-state prov-${k}${n === 0 ? ' is-zero' : ''}`}>
              <span className="prov-n">{n}</span>
              <span className="prov-label">{label}</span>
              <span className="prov-note">{note}</span>
            </li>
          );
        })}
      </ul>

      <p className="ranking-caption">
        Unassessed is reported separately from excluded: missing evidence is not
        exoneration, and collapsing the two would silently convert one into the other.
      </p>

      <dl className="meta prov-meta">
        <div><dt>Data status</dt><dd>{report.scene?.data_status}</dd></div>
        <div><dt>AIS source</dt><dd>{report.evidence_layers?.ais_source?.split('(')[0].trim()}</dd></div>
        <div><dt>Forcing</dt><dd>{report.evidence_layers?.forcing_product}</dd></div>
        <div><dt>Metric CRS</dt><dd>{report.scene?.metric_crs}</dd></div>
        {meta.seed != null && <div><dt>Seed</dt><dd>{meta.seed}</dd></div>}
        <div><dt>Files hashed</dt><dd>{nFiles} · SHA-256</dd></div>
      </dl>

      <p className="ranking-caption">{report.checksum_note ?? report.not_a}</p>
    </div>
  );
}
