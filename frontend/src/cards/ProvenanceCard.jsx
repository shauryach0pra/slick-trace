import { Badge, Card, Stat, StatGrid } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Traffic filtering and run provenance: how many vessels the traced-back
 * origin area removed, in three honestly separate states, and what
 * identifies this run. Counts come from the report artifact; the run fields
 * from the Case contract's meta.
 */
const STATES = [['candidate', 'Candidates'], ['excluded', 'Excluded'], ['unassessed', 'Unassessed']];

export default function ProvenanceCard({ meta, report }) {
  if (!meta) return null;
  const counts = report?.historical_filtering?.status_counts;
  const nFiles = report ? Object.keys(report.checksums_sha256 ?? {}).length : null;
  return (
    <Card title="Traffic Filtering and Provenance"
          badge={<Badge>{meta.provenance.status} data</Badge>}
          caption="Which vessels the traced-back origin area kept, and what identifies this run."
          footnote={report?.not_a}>
      <StatGrid cols={3}>
        {STATES.map(([k, label]) => (
          <Stat key={k} label={label} value={counts ? (counts[k] ?? 0) : '—'} caption={C[k]} />
        ))}
      </StatGrid>
      <div style={{ marginTop: 'var(--space-5)' }}>
        <StatGrid cols={3}>
          <Stat text label="AIS source" value={meta.ais_source} caption="Where the vessel tracks come from." />
          <Stat text label="Forcing" value={meta.forcing_product} caption="The current field the drift model uses." />
          <Stat label="Metric CRS" value={meta.metric_crs} mono caption="Map projection used for distances and areas." />
          <Stat label="Seed" value={meta.generator.seed} mono caption={C.seed} />
          <Stat label="Files hashed" value={nFiles == null ? '—' : `${nFiles} · SHA-256`} caption={C.checksums} />
          <Stat text label="Licence" value={meta.data_licence} caption="Terms the data is released under." />
        </StatGrid>
      </div>
    </Card>
  );
}
