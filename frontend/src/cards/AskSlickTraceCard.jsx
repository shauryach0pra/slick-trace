import AskConsole from '../AskConsole';
import { Card } from '../ui/primitives';
import { CAPTIONS as C } from '../ui/glossary';
import { HowMeasured } from '../ui/viz';
import './ask.css';

/**
 * Ask Slick Trace, shell only: the shared Card around the existing console.
 * The console's content is unchanged until Phase 6.
 */
export default function AskSlickTraceCard({ incidentId, api }) {
  return (
    <Card title="Ask Slick Trace"
          caption="Fixed templates over this case's files; every answer cited. No language model." className="console-panel">
      <AskConsole incidentId={incidentId} api={api} />
      <HowMeasured title="How answers are made"><p>{C.ask}</p></HowMeasured>
    </Card>
  );
}
