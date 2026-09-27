import { useEffect, useState } from 'react';
import { Badge, Card } from '../ui/primitives';
import { useCountUp } from '../ui/useCountUp';
import { useInView } from '../ui/useInView';
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

// one dot appears every STEP ms, left to right and row by row
const STEP = 80, POP = 420;

export default function ProvenanceCard({ meta, report, attribution }) {
  // the dots and their numbers play when the dots themselves are on screen
  const [dotsRef, dotsSeen] = useInView({ threshold: 0.6 });
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
  // one dot per vessel at each stage: candidates first, then excluded, then unassessed
  const nc = counts.candidate ?? 0, ne = counts.excluded ?? 0, nu = counts.unassessed ?? 0;
  const dots = (k) => k === 'scene' ? [...Array(nc).fill('candidate'), ...Array(ne).fill('excluded'), ...Array(nu).fill('unassessed')]
    : k === 'kept' ? Array(nc).fill('candidate') : k === 'replayed' ? Array(replayed).fill('candidate') : ['named'];
  const starts = [];
  steps.reduce((acc, st) => { starts.push(acc); return acc + (st.k === 'named' && !named ? 1 : dots(st.k).length); }, 0);
  const chips = [
    ['AIS', String(meta.ais_source).split(' (')[0]], ['Projection', meta.metric_crs], ['Seed', meta.generator.seed],
    ['Integrity', nFiles == null ? '—' : `${nFiles} files · SHA-256`],
  ];
  const facts = [
    ['AIS', meta.ais_source], ['Forcing', meta.forcing_product], ['Projection', meta.metric_crs],
    ['Seed', meta.generator.seed], ['Integrity', nFiles == null ? '—' : `${nFiles} files · SHA-256`], ['Licence', meta.data_licence],
  ];
  return (
    <Card title="Traffic Filtering and Provenance" badge={<Badge>{meta.provenance.status} data</Badge>}
          caption="Every vessel in the scene, down to the one named.">
      <div ref={dotsRef} className={`pv-dots${dotsSeen ? ' is-playing' : ''}`} role="list" aria-label={steps.map((st) => `${st.label}: ${st.n}`).join(', ')}>
        {steps.map((st, row) => (
          <div key={st.k} role="listitem" className={`pv-row is-${st.k}`}>
            <span className="pv-row-label">{st.label}</span>
            <span className="pv-row-dots">
              {st.k === 'named' && !named ? <span className="pv-none">no vessel named</span>
                : dots(st.k).map((kind, i) => <i key={i} className={`pv-dot is-${kind}`} style={{ '--i': starts[row] + i }} />)}
            </span>
            <span className="pv-row-n"><RowCount n={st.n} run={dotsSeen} delay={starts[row] * STEP} span={Math.max(1, st.n) * STEP + POP} /></span>
          </div>
        ))}
      </div>
      <div className="pv-legend">
        <span><i className="pv-dot is-candidate" />candidate</span>
        {counts.excluded ? <span><i className="pv-dot is-excluded" />excluded</span> : null}
        {counts.unassessed ? <span><i className="pv-dot is-unassessed" />unassessed — not cleared</span> : null}
      </div>
      <div className="pv-chips">
        {chips.map(([k, v]) => <span key={k} className="pv-chip" title={String(v)}><em>{k}</em>{v}</span>)}
      </div>
      <HowMeasured>
        <dl>
          <dt>Kept, excluded, unassessed</dt><dd>{C.candidate} {C.excluded} {C.unassessed}</dd>
          <dt>Seed</dt><dd>{C.seed}</dd>
          <dt>Integrity</dt><dd>{C.checksums}</dd>
          {facts.flatMap(([k, v]) => [<dt key={`${k}-t`}>{k}</dt>, <dd key={`${k}-d`}>{v}</dd>])}
          {report?.not_a && <><dt>What this is not</dt><dd>{report.not_a}</dd></>}
        </dl>
      </HowMeasured>
    </Card>
  );
}

/** A row's number, rising from 0 in step with its dots as they appear. */
function RowCount({ n, run, delay, span }) {
  const [go, setGo] = useState(false);
  useEffect(() => {
    if (!run) return undefined;
    const t = setTimeout(() => setGo(true), delay);
    return () => clearTimeout(t);
  }, [run, delay]);
  return useCountUp(n, { decimals: 0, duration: span, run: go, easing: (k) => k });
}

