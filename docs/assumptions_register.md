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

**Where:** `slicktrace_core/hindcast.py:112` (`_interp_track_position`)
**Enforced by:** `tests/test_invariants.py:190`

**Why.** AIS gaps are common. Unbounded interpolation invents vessel history and
then reasons over it.

**What breaks if it is wrong.** Fabricated positions would place vessels inside
or outside the origin envelope on the strength of data that does not exist —
producing both false candidates and false exclusions.

**How it is bounded.** Interpolation is confined strictly within a track's own
observed time range; outside it the function returns `None`, that queried time
is recorded as `no_data` in the vessel's `hourly_state`, and a vessel with any
`no_data` time cannot be summarised as `excluded` (A7). A single universal gap
threshold is not treated as proof of an outage.

---

### A7 · `unassessed` is not `excluded`

**Where:** `slicktrace_core/hindcast.py:24, 56, 222, 227`
**Enforced by:** `tests/test_invariants.py:97, 110, 341, 362`

**Why.** "No track data covering the queried window" and "data present
throughout, never compatible" are different findings.

**What breaks if it is wrong.** Collapsing the two silently converts missing
evidence into exoneration — the most consequential honesty failure available to
this system, because it would clear a vessel on the basis of an absence.

**How it is bounded.** Membership is decided per queried time first (`inside`,
`outside` or `no_data`, persisted as `hourly_state`) and only then summarised.
`excluded` requires track data at every queried time; partial coverage is
summarised as `unassessed`, with the span the data covers stated. Until
25 September 2026 a single covered time was enough to exclude, and the reason
string claimed coverage throughout the window: all 26 vessels then labelled
`excluded` had data at 11 of 25 queried times. The three states are carried
through the pipeline, the API, the text-equivalent table and the investigation
report, which states the distinction in words. The live map draws per-time
state; a vessel with no position at the selected time is not drawn.

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
exercised rather than trivially satisfied. Current result: 1/2 correct
abstentions, 1/2 false named attributions, with a 95% interval of 9 to 91% on
the abstention rate, which is the honest reading at n = 2.

**Where it fails.** In case_0003 a background vessel's best hypothetical release -
a half-hour pulse 8 h before the image - fits at mean IoU 0.325, just above the
0.3 gate and well ahead of the runner-up (0.19), so the system names it. The fit
gate alone cannot reject a plausible but imperfect alternative. Before the
benchmark fix (A21) this case could not arise: every innocent vessel was placed
far from the slick. A rule once considered - name no one when the top two are
not separated - would not catch it: here they are separated. Any change to the
gate is to be evaluated on held-out seeds, not on these cases, so that it is not
tuned to them.

---

### A11 · Ensemble and grid win frequency are not probabilities

**Where:** `slicktrace_core/fragility.py:204-206`; wording enforced across the
report and interface

**Why.** No calibration against *real* outcomes exists, and one cannot: that
would require confirmed source attributions this project does not have. A
calibration against *synthetic* truth is possible and has now been run — see
`docs/calibration_report.md` — but it measures the generator, not the ocean.

**What breaks if it is wrong.** "Leads in 8 of 10 variants" read as "80% likely
responsible" is the single most damaging misreading available, and it is an easy
one to invite by accident.

**How it is bounded.** Reported as an evidence score with its variant count.
Calibration language is avoided throughout the interface, the report and the
validation document. The fragility output carries the disclaimer inline rather
than relying on a footnote elsewhere.

**Measured, not merely asserted.** 60 separately generated cases yield 236
(score, outcome) pairs across all candidates, winners and losers. Held out:
Brier 0.0118, ECE 0.0395. Isotonic calibration halves ECE to 0.0169 and raises
Brier to 0.0169 — it sharpens near-extremes rather than correcting a real
miscalibration, because there was little to correct. The caution above stands
and is now conservative rather than unquantified: the score behaves well on this
generator, and that is still not a probability of responsibility.

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

**How it is bounded.** Two of eight cases are built this way, with the true
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

### A15 · Slick geometry uses a local azimuthal-equidistant projection

**Where:** `slicktrace_core/detection_geometry.py` (`characterise`)

**Why.** The manifest declares a metric CRS (EPSG:32643, UTM 43N) and the
repository has no reprojection dependency. The earlier version of this entry
treated the pixel grid as locally planar at the manifest's single
`pixel_spacing_m`, which was wrong in a measurable way: a degree of longitude
shrinks by cos(latitude) while a degree of latitude does not, so at 18.9 N a
pixel is 434 m north-south against 411 m east-west. Treating it as square
overstated area by about 5% and rotated the principal axes. Geometry is now
computed in local azimuthal-equidistant metres centred on the scene, where
distances and directions from the centre are true - which is exactly what area,
axis lengths and bearing require, and needs no reprojection library.

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

### A16 · Synthetic slick morphology is not drawn from the real distribution

**Where:** `slicktrace_core/synth_generator.py` (slick field construction);
measured in the characterisation table of `docs/validation_report.md`

**Why.** The generator builds a slick as a diffused, swirled blob so that the
release geometry stays interpretable and the truth mask is unambiguous. It was
never fitted to the shape statistics of real SAR oil slicks.

**What breaks if it is wrong.** It was wrong, measurably, and has been
partly corrected. Published morphology discriminators treat elongation above
about 2.0 and a ragged boundary as favouring oil; real bilge discharge from a
vessel under way is a ribbon, tens of kilometres by a few hundred metres. The
original eight cases measured between 1.02 and 1.29, so **scored against those
published thresholds every one would have been classified as a look-alike on
shape alone.**

The along-track ribbon family (case_0009) was added in response: elongation
4.34, 68.5 x 15.8 km, isoperimetric complexity 6.13 against 1.25-1.93 for the
compact cases. It is still at the low end of the real 5-20 range, and for a
blunt reason - at 111 km to the degree, a fully realistic ribbon runs off the
edge of a one-degree scene. The benchmark now spans both regimes rather than
only the unrealistic one, but it is not yet drawn from the real distribution.

**What the correction revealed.** The compact-slick defect was not cosmetic. A
continuous release smears along-track while a pulse stays compact, so on compact
slicks the attribution search preferred a 0.5 hour pulse on every single case,
despite every truth being a 2-4 hour continuous release. On the ribbon it
selected a continuous release for the first time. The morphology gap and the
release-type error were one problem, and the fix confirmed the diagnosis. Any morphology-based discriminator
calibrated on real imagery is therefore being applied out of domain when pointed
at this benchmark, and its output says more about the generator than the method.

**How it is bounded.** Stated here rather than left for a reader to notice.
Shape is not an input to attribution — ranking is driven by forward-replayed
footprint overlap, not by whether the slick looks like oil — so the defect does
not contaminate the headline result. It does two other things, both recorded:
it makes look-alike discrimination untestable on this benchmark, and it is the
reason the method prefers short pulses over continuous releases (A17-adjacent,
see the origin-error section of the validation report). An along-track ribbon
family is the fix; it is a diagnosed defect, not a roadmap aspiration.

---

### A17 · Stokes drift is not modelled, and neither is wind

**Where:** `slicktrace_core/synth_generator.py` (forcing fields: `u`, `v`,
`noise` only); `slicktrace_core/attribution.py` (advection)

**Why.** The masterplan warns against double-counting wind and Stokes effects
where a transport engine already configures them. This pipeline avoids that
problem by having neither: the forcing carries a current field and a noise term,
and no wind field exists at any point. The register did not previously say so,
which left a reader to infer that wind was handled somewhere.

**What breaks if it is wrong.** Surface oil moves at roughly 3% of wind speed
plus the Stokes drift of the wave field; omitting both means the modelled
trajectory is a pure current trajectory. On real data that is a first-order
error, not a refinement. It also removes the strongest physical discriminator
for look-alikes — the 4-10 m/s window in which a slick is separable at all —
which is why the look-alike rules that depend on wind report themselves as
unavailable rather than scoring zero.

**How it is bounded.** Truth and forward simulation share the same forcing, so
the comparison between candidates is internally consistent and the ranking is
unaffected. The omission is declared rather than approximated: adding a
synthetic wind field so that a wind-dependent rule could read it back would be
checking the system's own fiction against itself.

---

### A18 · Oil volume and tonnage are not estimated

**Where:** not implemented; `slicktrace_core/detection_geometry.py` reports
area, perimeter, axes, elongation and bearing only

**Why.** Volume from a single SAR scene requires a thickness estimate, and
thickness is not recoverable from an uncalibrated single-channel amplitude
image. The operational route is an appearance class — the Bonn Agreement scale
maps sheen, rainbow and metallic appearance to thickness bands spanning four
orders of magnitude — and that mapping is defined against calibrated
backscatter this pipeline does not produce.

**What breaks if it is wrong.** Nothing downstream: no stage consumes volume.
The cost is to the characterisation output, which answers "how large" in area
but not "how much".

**How it is bounded.** Declared rather than approximated. Multiplying area by an
assumed thickness would produce a number with four orders of magnitude of
unstated uncertainty, presented to three significant figures — the failure mode
this register exists to prevent. If it is added, it should be a wide interval
with an appearance class attached and a confidence field that cannot express
high, in the same shape as any age estimate.

**The route, identified and not taken.** NOAA's ADIOS Oil Database is the
public source for the missing half. It compiles oil assays aggregated from
Environment and Climate Change Canada's Emergencies Science and Technology
Section, the Norwegian Clean Seas Association, published ExxonMobil assays and
NOAA's own records, and carries per-oil density, kinematic and dynamic
viscosity, and emulsion water content. The working data is published as JSON on
NOAA-ORR-ERD's GitHub alongside an `adios_db` Python package, so there is no
licence obstacle and no account to obtain.

It is cited rather than integrated, deliberately. Volume needs thickness, and
thickness needs an appearance class this pipeline does not produce; oil density
and viscosity would additionally need somewhere to act, and the transport model
here carries neither windage nor Stokes drift (A17), so an oil record would be
loaded and never read. A database with no consumer is the pattern this
repository criticises elsewhere in competing work, and adding one to claim the
integration would be the same move.

What it would take to be real: oil properties entering spreading and windage,
which is a change to the transport model rather than a lookup. That is
post-freeze work, and it cannot be validated against synthetic forcing anyway —
a more sophisticated model of a fiction is still a fiction.

---

### A19 · Determinism holds for results, not for their containers

**Where:** verified on every push by `.github/workflows/tests.yml`

**Why.** Reproducibility is claimed in several places in this repository, and
the claim was originally unqualified: "regenerates bit-identically". Running the
regeneration in CI on Ubuntu x86-64, against artifacts committed from macOS
arm64, showed that is true of the analysis and false of the media.

Byte-identical across both platforms: attribution, fragility, hindcast,
coverage, forecast, next-observation and detection results. Every number any
reported figure derives from.

Not byte-identical, for reasons that have nothing to do with the analysis:
`scene.png` and `mask_groundtruth.png` serialise differently because PNG
encoding depends on the zlib build; `forcing.npz` is a zip archive and stores
member timestamps; `manifest.json` and the investigation reports carry SHA-256
checksums *of those files* and therefore differ too. The pixels and arrays are
identical; their containers are not.

One genuine numeric difference exists. `distance_deg` in
`naive_baseline_result.json` differs at the last representable digit between
x86-64 and arm64 — floating-point reduction order is not architecture-invariant.
At a typical value of 0.0062 that is a perturbation of about 1.4e-18, against a
smallest observed ranking gap of 0.1506: a ratio of 9e-18. It cannot reorder a
ranking, and the discrimination check would report it if it ever grew enough to
try.

**What breaks if it is wrong.** An unqualified determinism claim is falsifiable
in ten minutes by any reviewer who clones the repository on Linux and reruns the
pipeline. They would find 54 changed files and no explanation, and would be
right to distrust everything else on that basis.

**How it is bounded.** The CI check covers the analysis artifacts and excludes
the three media categories by name, with the reason written into the workflow
rather than applied silently. The README states what byte-identical covers. The
exclusion is visible, so a reader can disagree with where the line was drawn.

---

### A20 · Vessel positions are constrained by real coastline geometry

**Where:** `slicktrace_core/synth_generator.py` (`_keep_at_sea`, `_coast_lon_at`);
geometry in `data/geo/coastline_mumbai.json`

**Why.** The case coordinates were always real — 72.1–73.1 E, 18.4–19.4 N, off
the Maharashtra coast — but the coastline in each manifest was a synthetic
polyline, and vessel tracks were generated without reference to any land at all.
That was invisible while the only coast drawn was the synthetic one. Overlaying
Natural Earth 10m geometry made it obvious: **167 of 1024 vessel fixes, 16.3%,
sat east of the real shoreline.** Ships on hillsides, and in one case the
leading candidate inland.

Tracks are now clamped to stay 0.03° (~3.3 km) west of the interpolated coast
longitude at each latitude. The margin keeps a rendered marker off the shore
without pushing traffic implausibly far out.

**What breaks if it is wrong.** A scene with vessels on land is not one an
analyst would accept, and it undermines every other claim in the interface: a
reviewer who sees a ship parked inland has no reason to trust the attribution
beside it. The defect was cosmetic in the sense that no computation depended on
it — and consequential in the sense that it made the system look unserious.

**How it is bounded.** The constraint applies to generated vessel positions
only. Sensitive areas are not clamped: a mangrove reserve abuts the coast by
definition, and the one in these cases correctly does. The slick and its origin
envelope are not clamped either — oil does reach coastlines, and the forecast's
shoreline-contact figure exists to report exactly that.

The coastline is committed rather than fetched. A basemap from a tile provider
would end the offline operation verified in `docs/evidence/smoke_offline.txt`,
which is the same reason fonts are self-hosted. Natural Earth is public domain;
seven kilobytes in the repository costs less than a network dependency.

**What it did not change.** Every headline result was recomputed after the
constraint was applied and none moved: 7/7 source-present Top-1 against 0/7 for
the naive baseline, exact McNemar p = 0.0156, 2/2 correct abstentions. (These are
the numbers of that time. A21 later changed the benchmark itself, and the
current numbers are in the validation report.) The
attribution does not depend on coastline geometry, so constraining the scenarios
changed where the vessels are without changing what the method concludes about
them. That the numbers held is evidence the fix was cosmetic in the right way —
had they moved, the result would have been entangled with an artefact of the
generator.

---

### A21 · The benchmark does not hand over the answer

**The assumption.** Forward replay's accuracy is measured on cases where nothing
but the physics identifies the source.

**Why it was needed.** It was not true. The generator built the true source's
track from its release story, so its length (13 or 19 fixes against 21 for other
traffic and 6 for the near decoy), its start time and its speed were unlike any
other vessel's; it stopped reporting before the image in four cases; it loitered
at about 0.2 kn while reporting 9.5 kn; and no background vessel came near the
slick. A leak audit - rules that use only track bookkeeping, fixed before the
generator was changed - found 10 of 33 rules naming the source at or above the
flag threshold, four of them in 7 of 7 cases, matching forward replay's headline
without any physics.

**How it is bounded.** Every vessel is tracked over the whole 24 h AIS window and
published as an AIS query for the scene returns it - the fixes inside the scene,
so ships enter and leave through its edges - with the same reporting cadence
(30 min), speed (a shared mix of loitering and transit) and route distributions
whatever its role; 15% of vessels, of any role, switch their transponder off for
1 to 3 h; reported speed
and course are its actual motion; half of background traffic passes the slick as
closely as a polluter does (0.5 to 3.3 km, the range the sources were measured
at). Innocent vessels are kept physically identifiable: none is within 8 km of
the source while it releases, because a vessel at the release point during the
release is indistinguishable from the polluter by drift physics and a case
containing one tests nothing. The audit runs in every validation: 3 of 33 rules
flag, where about 2.7 are expected by chance, and no rule exceeds 5 of 7.

**What remains.** "Second-closest approach to the slick" names the source in 5 of
7. Its cause is physical rather than bookkeeping - the source was at the release
point hours before the image and the slick drifts only a few kilometres, while
the near decoy is placed on the slick at image time - so it is reported, not
engineered away. The fairer benchmark first cost the headline - the naive baseline
named the source once and McNemar p rose to 0.0312 - and full-day tracks then
brought the naive baseline back to 0/7 (p = 0.0156). One absent-source case names
a vessel (A10). An earlier version started every track 10 to 16 h before the
image, so ships appeared in open water rather than entering the scene.

---

### A22 · One real coastline, used everywhere

**The assumption.** Where the cases put land, sea, vessels and oil matches the
real coast the map draws underneath them.

**Why it was needed.** Three approximations stood in for the coast: the generator
invented one about 19 km east of the real shore, the detector interpolated a
coastline longitude per row (which zig-zags on a creek-cut shore), and the
forecast counted anything east of the coastline's westernmost point as ashore.
On real imagery a synthetic mangrove reserve sat over Mumbai, part of case_0009's
slick lay on land, and a forecast plume could drift inland.

**How it is bounded.** slicktrace_core/geography.py closes the committed Natural
Earth 10 m coastline around the land to its east and tests points against that
polygon. Every manifest carries the real coastline clipped to its scene; vessels
steer clear of land; the truth slick is sea only; the fishing ground is placed at
sea and the mangrove fringe straddles the shore; the radar scene renders land
bright, as SAR shows it; and forecast particles that reach land strand there,
checked hourly. Forecasts whose particles never touch land are unchanged to the
last digit. Natural Earth 10 m resolves narrow creeks and harbour detail only
coarsely; it is a scene-scale shoreline, not a harbour chart.

---

### A23 · Release times are searched at a fixed resolution

**The assumption.** Forward replay tries enough release start times to find the
one that happened.

**Why it was needed.** It tried three per vessel - the start, middle and end of
the vessel's observed track - so the resolution depended on how long a track
happened to be. With full-day tracks those were 12 h apart, a release 6 h before
the image was never tried, and the true source's fit fell from 0.69 to 0.50 in
case_0001 (still ranked first, but below the frozen case's 0.55 floor).

**How it is bounded.** A start is tried every hour across each vessel's observed
window, the same for every vessel, crossed with the same three durations. It was
fixed on that principle before rescoring, not tuned to the result; case_0001's
best hypothesis now starts at the true release time. Attribution does about
eight times the work; the slowest case takes about 25 s, within the 5 min budget.

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
