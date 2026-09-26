import { Badge, Card } from '../ui/primitives';
import { HowMeasured } from '../ui/viz';
import './supporting.css';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Traffic filtering and run provenance: how many vessels the traced-back
 * origin area removed, in three honestly separate states, and what
 * identifies this run. Counts come from the report artifact; the run fields
 * from the Case contract's meta.
 */
const STATES = [['candidate', 'Candidates'], ['excluded', 'Excluded'], ['unassessed', 'Unassessed']];

export default function ProvenanceCard({ meta, report, attribution }) {
  if (!meta) return null;
  const counts = report?.historical_filtering?.status_counts ?? {};
  const nFiles = report ? Object.keys(report.checksums_sha256 ?? {}).length : null;
  const total = STATES.reduce((t, [k]) => t + (counts[k] ?? 0), 0);
  const replayed = attribution?.candidates_considered?.length ?? counts.candidate ?? 0;
  const named = attribution ? (attribution.unknown_source ? 0 : 1) : null;
  // the funnel: every vessel in the scene, down to the one named (or none)
  const steps = [
    { k: 'scene', label: 'In the scene', n: total },
    { k: 'kept', label: 'Kept by the origin area', n: counts.candidate ?? 0 },
    { k: 'replayed', label: 'Replayed', n: replayed },
    ...(named != null ? [{ k: 'named', label: named ? 'Named' : 'Named — system abstains', n: named }] : []),
  ];
  const facts = [
    ['AIS', meta.ais_source], ['Forcing', meta.forcing_product], ['Projection', meta.metric_crs],
    ['Seed', meta.generator.seed], ['Integrity', nFiles == null ? '—' : `${nFiles} files · SHA-256`], ['Licence', meta.data_licence],
  ];
  return (
    <Card title="Traffic Filtering and Provenance" badge={<Badge>{meta.provenance.status} data</Badge>}
          caption="From every vessel in the scene to the one named, and what identifies this run.">
      <div className="pv-funnel" role="list" aria-label={steps.map((st) => `${st.label}: ${st.n}`).join(', ')}>
        {steps.map((st, i) => (
          <div key={st.k} role="listitem" className={`pv-step is-${st.k}${st.k === 'named' && !named ? ' is-none' : ''}`} style={{ '--i': i }}>
            <span className="pv-bar" style={{ '--w': total ? Math.max(st.n / total, 0.04) : 0 }}><b>{st.n}</b></span>
            <span className="pv-label">{st.label}</span>
          </div>
        ))}
      </div>
      {(counts.excluded || counts.unassessed) ? (
        <div className="pv-side">
          {counts.excluded ? <span className="pv-chip">{counts.excluded} excluded — never inside the origin area</span> : null}
          {counts.unassessed ? <span className="pv-chip is-warn">{counts.unassessed} unassessed — track gaps, so not cleared</span> : null}
        </div>
      ) : null}
      <dl className="pv-facts">
        {facts.map(([k, v]) => <div key={k}><dt>{k}</dt><dd title={String(v)}>{v}</dd></div>)}
      </dl>
      <HowMeasured>
        <dl>
          <dt>Kept, excluded, unassessed</dt><dd>{C.candidate} {C.excluded} {C.unassessed}</dd>
          <dt>Seed</dt><dd>{C.seed}</dd>
          <dt>Integrity</dt><dd>{C.checksums}</dd>
          {report?.not_a && <><dt>What this is not</dt><dd>{report.not_a}</dd></>}
        </dl>
      </HowMeasured>
    </Card>
  );
}
