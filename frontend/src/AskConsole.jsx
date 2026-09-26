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
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
      });
    }
  }

  return (
    <>
      {history.length === 0 && (
        <div className="suggestions-section">
          <p>Try a question, or pick one below.</p>
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="suggestion" onClick={() => submit(s)}>{s}</button>
            ))}
          </div>
        </div>
      )}
      <div className="console-history" ref={scrollRef}>
        {history.map((r, i) => (
          <div className="console-entry" key={i}>
            <div className="console-q">&gt;&gt;&gt; {r.question}</div>
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
      <form className="console-input-row" onSubmit={(e) => { e.preventDefault(); submit(input); }}>
        <span className="prompt">&gt;</span>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about candidates, routes, or the forcing field…"
          disabled={busy}
        />
        <button type="submit" disabled={busy}>Ask</button>
      </form>
    </>
  );
}
