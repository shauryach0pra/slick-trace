/** The outcome symbol, shared by the sidebar and the overview: a vessel named, or an abstention. */
export default function OutcomeIcon({ abstain, className = '' }) {
  return (
    <span className={`sl-outcome ${abstain ? 'is-abstain' : 'is-named'} ${className}`.trim()} aria-hidden="true">
      <svg viewBox="0 0 16 16">
        {abstain ? <><circle cx="8" cy="8" r="6" /><path d="M4 12L12 4" /></>
          : <><circle cx="8" cy="8" r="6" /><path d="M5.2 8.2l2 2 3.8-4.2" /></>}
      </svg>
    </span>
  );
}
