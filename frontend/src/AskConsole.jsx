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
  // each exchange: the question at once, its reply when it arrives
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);
  const nextId = useRef(0);

  const reveal = (id) => requestAnimationFrame(() => requestAnimationFrame(() => {
    // bring the exchange into view from its question, never cutting off the top
    const box = scrollRef.current, el = box?.querySelector(`[data-ex="${id}"]`);
    if (box && el) box.scrollTo({ top: box.scrollTop + el.getBoundingClientRect().top - box.getBoundingClientRect().top - 4, behavior: 'smooth' });
  }));

  async function submit(question) {
    const q = question.trim();
    if (!q || busy) return;
    const id = nextId.current++;
    setBusy(true);
    setInput('');
    setHistory((h) => [...h, { id, question: q, result: null }]);
    reveal(id);
    let result;
    try {
      result = await api.ask(incidentId, q);
    } catch (e) {
      result = { question: q, intent: 'error', supported: false, answer: String(e.message ?? e), citations: [] };
    }
    setHistory((h) => h.map((x) => (x.id === id ? { ...x, result } : x)));
    setBusy(false);
    reveal(id);
  }

  return (
    <>
      <div className="ask-chat" ref={scrollRef} aria-live="polite">
        {history.length === 0 && <p className="ask-empty">Pick a question below, or ask your own.</p>}
        {history.map(({ id, question, result: r }) => (
          <div className="ask-ex" key={id} data-ex={id}>
            <div className="ask-q">{question}</div>
            {!r ? (
              <div className="ask-a is-pending" aria-label="Answering"><i /><i /><i /></div>
            ) : (
              <div className={`ask-a${r.supported ? '' : ' is-declined'}`}>
                <span className={`ask-tag ${r.supported ? 'ok' : 'refused'}`}>
                  {r.supported ? `answered · ${r.intent.replaceAll('_', ' ')}` : 'declined · no matching template'}
                </span>
                <p>{r.answer}</p>
                {r.citations?.length > 0 && (
                  <span className="ask-cites">cites: {r.citations[0]}{r.citations.length > 1 ? ` (+${r.citations.length - 1} more)` : ''}</span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      {/* suggestions stay, so a demo can keep asking; a tap sends at once */}
      <div className="ask-suggest" role="group" aria-label="Suggested questions">
        {SUGGESTIONS.map((q) => (
          <button key={q} type="button" className="ask-chip" disabled={busy} onClick={() => submit(q)}>{q}</button>
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
