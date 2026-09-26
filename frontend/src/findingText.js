/**
 * The one-line finding for a case, from its attribution and proximity results.
 * Shared by the Case Finding card and the overview, so both say exactly the
 * same thing: one rule, not two texts to keep in step.
 */
export function findingHeadline({ unknown, nCandidates, differs }) {
  if (unknown) {
    return `No vessel is named. Forward replay tested ${nCandidates} candidate vessel${nCandidates === 1 ? '' : 's'}, `
      + 'and none fit the observed slick well enough to reach the gate.';
  }
  return differs
    ? 'The nearest vessel is not supported by forward replay; the best physical fit is another vessel.'
    : 'The nearest vessel is also the best physical fit under forward replay.';
}
