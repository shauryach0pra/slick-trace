import { useRef, useState } from 'react';

// The same five for every case. Answers are read from that case's computed
// fields by rule-based templates. The last is deliberately out of scope and
// looks like any other question: clicking it shows the system declining
// rather than guessing.
const SUGGESTIONS = [
  'What is the top candidate and why?',
  'Why was the nearest vessel ruled out?',
  'How confident is the release time?',
  'What would change the conclusion?',
  'Who is legally responsible for this spill?',
];

export default function AskConsole({ incidentId, api }) {
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  async function submit(question) {
    if (!question.trim() || busy) return;
    setBusy(true);
    setInput('');
    try {
      const result = await api.ask(incidentId, question);
      setHistory((h) => [...h, result]);
    } catch (e) {
      setHistory((h) => [...h, {
        question, intent: 'error', supported: false,
        answer: String(e.message ?? e), citations: [],
      }]);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => {
        // show the new answer from its first line - scrolling to the bottom hid the top of long answers
        requestAnimationFrame(() => {
          const box = scrollRef.current;
          const entries = box?.querySelectorAll('.console-entry:not(.console-busy)');
          const last = entries?.[entries.length - 1];
          if (box && last) box.scrollTo({ top: box.scrollTop + last.getBoundingClientRect().top - box.getBoundingClientRect().top - 6, behavior: 'smooth' });
        });
      });
    }
  }

  return (
    <>
      <div className="console-history" ref={scrollRef}>
        {history.map((r, i) => (
          <div className="console-entry" key={i}>
            <div className="console-q">{r.question}</div>
            <div className={`console-tag ${r.supported ? 'ok' : 'refused'}`}>
              {r.supported ? `answered · ${r.intent.replaceAll('_', ' ')}` : 'declined · no matching template'}
            </div>
            <div className="console-a">{r.answer}</div>
            {r.citations?.length > 0 && (
              <div className="console-cites">cites: {r.citations[0]}{r.citations.length > 1 ? ` (+${r.citations.length - 1} more)` : ''}</div>
            )}
          </div>
        ))}
        {busy && <div className="console-entry console-busy">running query…</div>}
      </div>
      {/* suggestions stay, so a demo can keep asking */}
      <div className="ask-suggest" role="group" aria-label="Suggested questions">
        {SUGGESTIONS.map((s) => (
          <button key={s} type="button" className="ask-chip" disabled={busy} onClick={() => submit(s)}>{s}</button>
        ))}
      </div>
      <form className="ask-field" onSubmit={(e) => { e.preventDefault(); submit(input); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about this case…"
               disabled={busy} aria-label="Ask a question about this case" />
        <button type="submit" className="ask-send" disabled={busy || !input.trim()} aria-label="Ask">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" /></svg>
        </button>
      </form>
    </>
  );
}
