import { useRef, useState } from 'react';

const SUGGESTIONS = [
  'What is the top candidate and why?',
  'Which vessels crossed the likely origin zone from 02:00 to 05:00 UTC?',
  'Find the current-field source used in this report.',
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
              [{r.intent}{r.supported ? '' : ' | refused'}]
            </div>
            {r.filters && Object.keys(r.filters).length > 0 && (
              <div className="console-filters">filters: {JSON.stringify(r.filters)}</div>
            )}
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
