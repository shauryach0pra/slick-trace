/**
 * Plain-language captions, shown under every non-obvious number by default.
 *
 * One sentence each, written for someone who has not read the method. They
 * describe what a value means, never what it proves: a caption that implied
 * guilt, certainty or a calibrated probability would be wrong.
 */

export const CAPTIONS = {
  // forward replay
  meanIou: 'How much the replayed slick overlaps the observed one, from 0 (none) to 1 (exact).',
  fitGate: 'Below this overlap no vessel is named, rather than naming the least-bad fit.',
  variants: 'In how many of the tested current and diffusion settings this vessel fit best.',
  lossGap: 'How far ahead the leader’s fit is; under 0.05 the top two are effectively tied.',
  replayMethod: 'Physics-based particle tracking: each release is drifted forward under the same set '
    + 'of forcing perturbations for every vessel.',
  firstEntry: 'Earliest hour before the image at which the vessel was inside the traced-back origin area.',

  // proximity baseline
  distance: 'Straight-line gap to the slick at image time; 0.01° is about 1.1 km.',
  baselineMethod: 'Picks whichever vessel was nearest the slick when the image was taken, from every '
    + 'vessel in the scene. It is the shortcut forward replay is measured against.',

  // historical filtering
  candidate: 'Inside the traced-back origin area at some tested hour, so it goes on to replay.',
  excluded: 'Tracked at every tested hour and never inside the origin area.',
  unassessed: 'Track data missing for part of the window, so the vessel is not cleared.',

  // scene and detection
  area: 'Sea surface covered by the detected outline.',
  perimeter: 'Length of the outline’s edge.',
  majorAxis: 'Extent of the slick along its long axis.',
  minorAxis: 'Extent of the slick across its long axis.',
  elongation: 'Length divided by width; 1 is round, higher is streak-like.',
  bearing: 'Direction of the long axis, clockwise from north.',
  truthIou: 'Agreement between this outline and the generator’s own slick mask, from 0 to 1. '
    + 'Available only because the case is synthetic.',
  darkness: 'Dark radar patches can also be calm water or natural films; darkness alone is not proof of oil.',
  pixelSpacing: 'Ground distance covered by one image pixel.',

  // replay map
  replay: 'Drag the slider to step back hour by hour. The shaded area is where the slick could have '
    + 'drifted from by then, widening because release time and spreading are unknown.',

  // fragility
  leadHeld: 'Share of the tested assumption changes that kept the same leader.',
  magnitude: 'Size of the smallest tested change that flips the leader; 1.0 means one setting pushed '
    + 'to the edge of its plausible range.',
  sweep: 'Pick one setting and a tested value to see who leads under it. Only computed runs are shown.',
  lossMargin: 'How far the leader’s fit is ahead of the next vessel under this setting.',

  // forecast
  horizon: 'Hours after the image.',
  envelopeArea: 'Area of image cells holding at least one modelled particle at that hour.',
  shoreline: 'Share of modelled particles on the coast side of the shoreline; not a damage estimate.',
  exposure: 'Share of modelled particles inside the named area at that hour.',

  // next observation
  recommended: 'The tested future time at which one more image would best tell the top two explanations apart.',
  disagreement: 'How differently the top two explanations predict the slick will look then; higher is more telling.',
  overlapIou: 'How much their predicted footprints overlap then, from 0 (none) to 1 (identical).',

  // coverage
  hiddenRecovery: 'Of vessels in the scene whose AIS was hidden in the test, the share still flagged as '
    + 'unidentified contacts; ones the radar missed count as not recovered. Higher is better.',
  falseAlert: 'Of contacts flagged unidentified, the share that were in fact broadcasting. Lower is better.',
  mistakenPromotion: 'Share of test runs in which hiding the leading vessel’s AIS lets an unrelated contact '
    + 'become the first thing an analyst would look at. Lower is better.',
  lossRanking: 'Leadership is decided by the overall fit loss, not overlap alone, so a new leader can show a lower IoU.',
  gateRadius: 'How close a radar contact and an AIS position must be to count as the same vessel.',
  notMeasured: '“Not measured” means the test had nothing to count, not a rate of zero.',

  // provenance
  seed: 'The number that regenerates this synthetic case exactly.',
  checksums: 'File fingerprints showing the artifacts were not altered, not that the observation is true.',

  // basemap
  basemap: 'The real map under this case: satellite imagery when an Esri key is set, otherwise the '
    + 'real coastline on a plain sea. Nothing from the case is drawn on it yet.',
  basemapGeography: 'The case uses this real coastline. Its vessels, slick and sensitive areas are '
    + 'synthetic, placed on real geography: at sea, or along the shore where that is where they belong.',

  // ask
  ask: 'Answers come from fixed question templates over this case’s files, each with its source cited. '
    + 'Questions outside those templates are declined.',
};
