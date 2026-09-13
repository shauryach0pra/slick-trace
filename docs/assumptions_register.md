# Appendix A — Assumptions register

Every modelling choice this system makes, why it is made, what breaks if it is
wrong, and where it lives in the code.

Collected here so a reviewer finds the boundaries of the method in one place
rather than inferring them from source. Each entry is testable, and several are
varied deliberately in the ensemble or the fragility grid rather than being
fixed beliefs.

Any number in the submission that depends on one of these is reported with the
assumption named, so the result and its boundary can be judged together.

---

### A1 · Dispersion grows with elapsed drift time (≈ Fickian, √t)

**Where:** `slicktrace_core/attribution.py:148`, `slicktrace_core/synth_generator.py:117`
**Enforced by:** `tests/test_invariants.py:155`

**Why.** A parcel adrift for eight hours is more smeared than one released ten
minutes ago. A fixed-width perturbation independent of drift duration is not
physical.

**What breaks if it is wrong.** This is the assumption whose absence would most
quietly invalidate the headline result. With a fixed spread, a vessel that was
near the observed slick only briefly can reproduce a plausible-looking footprint
regardless of how implausible its timing was. The ranking then measures
proximity in disguise, and the comparison against the proximity baseline becomes
circular — the method would appear to beat a baseline it had silently become.

**How it is bounded.** Applied in both the truth generator and the forward
simulator, and they must stay consistent; changing one alone makes the
comparison meaningless while everything still runs. Diffusivity is varied across
the shared ensemble and again along the fragility grid's `diffusivity_scale`
axis.

---

### A2 · The backward envelope diffuses rather than converging

**Where:** `slicktrace_core/hindcast.py`, `build_backward_envelope`
**Enforced by:** `tests/test_invariants.py:201`

**Why.** Release time, duration and diffusivity are all unknown. Reverse
advection does not recover a point source, and particles may separate or remain
diffuse.

**What breaks if it is wrong.** Forcing convergence in the visual would
manufacture a false precise origin — a confident-looking answer with nothing
behind it. This is a presentation failure as much as a modelling one: a tight
converging cloud reads as certainty to a viewer.

**How it is bounded.** Envelope width grows with hours-back and is displayed
rather than hidden. The `MetricInfo` entry for the envelope states in the
interface that it is not converging on a point source and is not drawn as if it
does. Reverse advection is used only to propose candidates; consistency is
tested by forward runs.

---

### A3 · All candidates are scored under one shared ensemble and an equal budget

**Where:** `slicktrace_core/attribution.py:42-49` (module-level `ENSEMBLE_VARIANTS`)
**Enforced by:** `tests/test_invariants.py:181`

**Why.** A comparison is only fair if every candidate is tested under identical
perturbations with the same search budget.

**What breaks if it is wrong.** A candidate-specific ensemble invalidates the
ranking outright. The failure is silent: every number still computes, the chart
still renders, and the winner is an artefact of who got the easier draw.

**How it is bounded.** Enforced by construction — the variant list is a module
constant, not a per-candidate argument — and asserted by test. Release
hypotheses use the same sampling grid for every vessel
(`sample_release_hypotheses`, `n_start_samples=3` × three durations).

---

### A4 · Loss weights a, b, c, d

**Where:** `slicktrace_core/attribution.py:51`
`{a_iou: 0.5, b_boundary: 0.2, c_area: 0.2, d_complexity: 0.1}`

**Why.** The four terms balance overlap, boundary agreement, area error and a
penalty for more complex explanations (longer or continuous releases), so that a
hypothesis cannot win purely by being more elaborate.

**What breaks if it is wrong.** These are validation settings, not scientific
constants and not calibrated probabilities. A ranking that depends heavily on
them is fragile in a way the reader deserves to see.

**How it is bounded.** The weights are recorded in every
`attribution_result.json` and printed in the investigation report. Sensitivity to
them is exposed by the rank-fragility control rather than asserted to be small.

---

### A5 · Footprint rasterisation threshold

**Where:** `slicktrace_core/attribution.py:83` (`thresh_frac=0.15`),
`slicktrace_core/fragility.py:57` (varied over 0.10 / 0.15 / 0.22)

**Why.** Simulated particles must be converted into a mask comparable with the
observed one, and that requires choosing a cut-off.

**What breaks if it is wrong.** A rank that survives only at one threshold is
not a result, it is a coincidence of the rendering step.

**How it is bounded.** The threshold is documented and included in the
perturbation grid as its own axis. A rank that flips under a threshold change is
reported as fragile, with the specific value that flipped it.

---

### A6 · Track interpolation is bounded; gaps are marked, never filled

**Where:** `slicktrace_core/hindcast.py:109` (`_interp_track_position`)
**Enforced by:** `tests/test_invariants.py:190`

**Why.** AIS gaps are common. Unbounded interpolation invents vessel history and
then reasons over it.

**What breaks if it is wrong.** Fabricated positions would place vessels inside
or outside the origin envelope on the strength of data that does not exist —
producing both false candidates and false exclusions.

**How it is bounded.** Interpolation is confined strictly within a track's own
observed time range; outside it the function returns `None` and the vessel is
recorded as `unassessed` rather than guessed at. A single universal gap
threshold is not treated as proof of an outage.

---

### A7 · `unassessed` is not `excluded`

**Where:** `slicktrace_core/hindcast.py:24, 56, 149`
**Enforced by:** `tests/test_invariants.py:97, 110`

**Why.** "No track data covering the queried window" and "data present
throughout, never compatible" are different findings.

**What breaks if it is wrong.** Collapsing the two silently converts missing
evidence into exoneration — the most consequential honesty failure available to
this system, because it would clear a vessel on the basis of an absence.

**How it is bounded.** Three distinct states throughout the pipeline, the API,
the map (by shape as well as colour), the text-equivalent table and the
investigation report, which states the distinction in words.

---

### A8 · Vessel identity is time-bounded

**Where:** `slicktrace_core/synth_generator.py:327-328`, `slicktrace_core/schema.py:73-74`

**Why.** MMSI, IMO and name mappings change. An identifier does not describe the
same vessel forever.

**What breaks if it is wrong.** A stale identifier silently attributes one
vessel's history to another.

**How it is bounded.** Identity is stored with its source and a validity
interval. A stale identity is a disclosure, not a match.

---

### A9 · The generator's forcing differs from the simulator's

**Where:** `slicktrace_core/synth_generator.py:101-107` (spatially varying `swirl`)
versus `slicktrace_core/attribution.py:128` (constant `u`, `v`)

**Why.** If the evaluated method inverted exactly the simulator that produced the
answer, good scores would measure nothing but self-consistency.

**What breaks if it is wrong.** An identical forward model would inflate every
attribution result by an unknown and unmeasurable amount.

**How it is bounded.** The mismatch is deliberate and documented. The `swirl`
parameter is written to the truth sidecar, never to the manifest, so the
simulator cannot see it. All results remain synthetic and labelled
`DataStatus.SYNTHETIC`; synthetic ranking accuracy is not a claim about
real-world attribution accuracy.

---

### A10 · An absolute fit gate must be cleared before any candidate is named

**Where:** `slicktrace_core/attribution.py:52` (`ABSTENTION_IOU_GATE = 0.30`), `:255`
**Enforced by:** `tests/test_invariants.py:131, 142`

**Why.** A pure ranking always has a top entry. Without an absolute floor, the
system would name a source in cases that have none.

**What breaks if it is wrong.** Best-of-bad-options naming — the failure mode
with real-world consequences attached, since the output is meant to direct a
human investigator's attention.

**How it is bounded.** Below the gate the system returns `unknown source` rather
than the least-bad name. Tested on the two source-absent cases, where the near-
miss decoy deliberately survives hindcast filtering so the gate is genuinely
exercised rather than trivially satisfied. Current result: 2/2 correct
abstentions, 0/2 false named attributions — with a 95% interval of 0 to 66%,
which is the honest reading at n = 2.

---

### A11 · Ensemble and grid win frequency are not probabilities

**Where:** `slicktrace_core/fragility.py:204-206`; wording enforced across the
report and interface

**Why.** No calibration against held-out outcomes exists. Calibration would
require observed source outcomes this project does not have.

**What breaks if it is wrong.** "Leads in 8 of 10 variants" read as "80% likely
responsible" is the single most damaging misreading available, and it is an easy
one to invite by accident.

**How it is bounded.** Reported as an evidence score with its variant count.
Calibration language is avoided throughout the interface, the report and the
validation document. The fragility output carries the disclaimer inline rather
than relying on a footnote elsewhere.

---

### A12 · SAR darkness is not proof of oil

**Where:** `slicktrace_core/detection_data.py` (look-alike class),
`slicktrace_core/baseline_detector.py:68-69` (uniformity rejection)

**Why.** Low wind, biogenic films and wind shadows dampen backscatter too.

**What breaks if it is wrong.** A detector that treats every dark patch as oil
feeds false incidents into the entire downstream pipeline, and attribution would
faithfully rank candidate sources for a slick that never existed.

**How it is bounded.** Look-alike negatives are generated and reported against
separately, with their masks correctly zero-valued rather than outlining the
look-alike. Detection confidence and source confidence are kept separate
throughout — the attribution stage never consumes a detection score. Current
false-positive rate on look-alikes and clean water: 0.000 on both val and test.

---

### A13 · A source vessel may have left the scene entirely

**Where:** `slicktrace_core/synth_generator.py:217-227` (`absent_source` family)

**Why.** A vessel can discharge and transit out of the imaged area before
acquisition, or stop broadcasting. Same-scene detection cannot recover a contact
that is absent from the image.

**What breaks if it is wrong.** Assuming the source is always among the observed
candidates guarantees a wrong answer in exactly the cases that matter most.

**How it is bounded.** Two of six cases are built this way, with the true
source's track removed from the manifest entirely. The correct output is
`unknown source`, and it is tested rather than assumed.

---

### A14 · The truth sidecar is excluded from the shipped image

**Where:** `Dockerfile:35-41` (copies `backend/`, `slicktrace_core/`,
`scripts/startup_check.py`, `scripts/docker-entrypoint.sh`,
`scripts/smoke_test.py` and `data/cases/` — the truth sidecar is not among them)

**Why.** If the container held both the question and its answer key, the offline
result could not be cleanly distinguished from a system that had been told what
to find. Keeping the sidecar out means the shipped artifact cannot self-confirm
an identity it was handed. `--reveal-truth` remains a development-only flag and
is not reachable from the API or the interface.

**What breaks if it is wrong.** The offline acceptance check cannot verify *which*
vessel was expected, only that the structure of the result holds. A wrong answer
would have to survive both IoU tolerances and still disagree with the naive
baseline in the right direction.

**How it is bounded.** The offline check falls back to structural verification and
says so in its own output rather than passing silently. Identity is verified
separately from the repo checkout, where the sidecar is present. Both runs on
12 Sep produced identical figures — IoU 0.688 / 0.087, top 419336692, naive
419824090 — recorded in `docs/evidence/smoke_online.txt` and
`docs/evidence/smoke_offline.txt`.

---

### A15 · Slick geometry is measured on the pixel grid, not reprojected

**Where:** `slicktrace_core/detection_geometry.py` (`characterise`)

**Why.** The manifest declares a metric CRS (EPSG:32643, UTM 43N), but the
repository has no reprojection dependency and adding one days before a freeze
would put a working pipeline at risk for a second-order gain. Over a scene one
degree across, treating the pixel grid as locally planar at the manifest's
`pixel_spacing_m` introduces error well below the uncertainty already present in
the detector's own boundary.

**What breaks if it is wrong.** Area, axis lengths and bearing would be
systematically distorted — increasingly so at higher latitudes or across a wider
scene. Elongation, being a ratio, is the most robust of the reported figures;
absolute area is the least.

**How it is bounded.** The approximation is stated in every artifact that carries
the geometry (`measurement_note` in `detection_result.json`) and in the interface,
rather than the declared CRS being allowed to imply a rigour the method does not
have. Axis lengths are 2-sigma extents along the principal axes, not maximum
calipers. The perimeter carries a 0.90 correction because a pixelated outline is
roughly 11% longer than the smooth curve beneath it; that factor is a documented
convention, not a measurement.

---

## Assumptions this system does *not* make

Recorded because their absence is deliberate and a reviewer may look for them:

- **No slick age from single-scene area.** Area alone cannot identify release age
  when volume, oil properties and forcing are unknown. Release-time *intervals*
  are estimated instead; no Fay-based age claim appears anywhere.
- **No AIS-gap culpability bonus.** A gap in broadcasting does not raise a
  candidate's score. Coverage is assessed separately
  (`slicktrace_core/coverage.py`) and unmatched contacts keep identity unknown.
- **No vessel class treated as automatically innocent.** Vessel type is not an
  input to ranking at any point; physical compatibility drives retention.
- **No claim that ranked output constitutes proof.** The output is an
  investigative lead for a human analyst. It is not a legal finding, and the
  report says so in its first line.
