import AskConsole from '../AskConsole';
import { Badge, Card } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';

/**
 * Ask Slick Trace, shell only: the shared Card around the existing console.
 * The console's content is unchanged until Phase 6.
 */
export default function AskSlickTraceCard({ incidentId, api }) {
  return (
    <Card title="Ask Slick Trace" badge={<Badge>rule-based intent matching</Badge>}
          caption={C.ask} className="console-panel">
      <AskConsole incidentId={incidentId} api={api} />
    </Card>
  );
}
