# CHANGELOG

Everything that changed, so you can diff this against whatever you have locally
rather than guessing.

---

## 25 September 2026

**Historical filtering: partial coverage no longer counts as exclusion.**
`slicktrace_core/hindcast.py` marked a vessel `excluded` if it had a position at
any one of the 25 queried times and was never inside the envelope, and the
reason string then claimed track data "present throughout window". Every one of
the 26 vessels excluded across the nine cases had data at 11 of 25 queried
times: generated tracks cover the last ten hours of a 24-hour window. Membership
is now decided per queried time (`inside`, `outside`, `no_data`, persisted as
`hourly_state` with `hours_with_data` and `data_intervals_hours_before`) and
only then summarised; `excluded` requires data at every queried time, as A7
always defined it. The 26 vessels are now `unassessed`, with the span their data
covers stated. Candidate sets, rankings, fragility and the headline are
unchanged (7/7 against 0/7, exact McNemar p = 0.0156), because neither state is
replayed. No vessel in the benchmark now qualifies as excluded: that needs
tracks spanning the window the manifest declares, a generator change not made
here. The NLP suite's "filtered out before ranking" question now draws on
excluded or unassessed vessels, so it resolves to the same two vessels as
before. Two invariant tests added; 199 pass.

**Canonical Case contract.** `slicktrace_core/case_contract.py` defines one
validated object per incident, assembled verbatim from the committed artifacts
(manifest, historical mapping, detection, baseline, attribution, fragility,
coverage, forecast, next observation) and never from the truth sidecar.
Unknown fields are rejected, so artifact drift fails the suite. The family label
is checked against `CASE_PLAN`: nine cases across five families (decoy x3,
moving_discharge x2, absent_source x2, crowded, along_track_ribbon). Not yet
served or read by the interface. Thirteen tests added; 212 pass.

**Case served.** `GET /api/incidents/{id}/case` returns the contract for one
incident; each section equals what its per-stage endpoint already serves, a
missing stage is an actionable 404, and a contract mismatch is a 500 naming it.
Nothing in the interface reads it yet. Three tests added; 215 pass.

**Time-slider replay served from an artifact, not computed per request.**
`/api/incidents/{id}/envelope` rebuilt the backward simulation, re-ran the
density contours and re-tested every vessel on each request, with its own copy
of the 0.045° inclusion radius; the query console did the same for time-window
questions with a third copy. None of it was covered by the determinism check.
The historical-mapping stage now also writes `envelope_timeline.json` (25 hourly
frames: particles, 50/75/90% contours, every vessel's position and membership)
from the same snapshots and per-time pass it summarises. `/envelope` serves the
nearest frame, `/envelope-timeline` serves all 25, and time-window questions
read `hourly_state` from `historical_mapping.json`. The served API no longer
reads the ground-truth mask at request time; the pipeline still seeds the
hindcast from it. Measured: every frame's per-vessel state equals the historical
mapping's in all nine cases; the old and new `/envelope` agree on every field
for all 25 hours of all nine cases, contours to the 5-decimal rounding the
artifact applies; the NLP suite returns the same 40 answers. CI now diffs the
new artifact. Two tests added; 217 pass.

**README brought in line with the repository.** It stated eight cases, four
families, 197 tests and a 4/4 against 0/4 headline. `CASE_PLAN` defines nine
cases across five families (along_track_ribbon was missing), 217 tests pass,
and validation reports 7/7 against 0/7, exact McNemar p = 0.0156.

**Interface: three displays that showed values nothing computed.**
`CoveragePanel` printed a null rate (denominator zero, e.g. mistaken promotion
on absent-source cases, 0/0) as 0.0%; it now reads "not measured".
`ConclusionGraph` read three fields no artifact has (`detection.iou`,
`historical.candidates`, `fragility.flip_delta`), so it showed "N/A" and
"0 candidates" on every case and "Source: null" on abstentions, and drew
attribution before historical mapping; it is removed, as the verdict band
already states the finding. `api.js` no longer defines `detection` twice.

**Display geometry computed in the pipeline.** The attribution stage now also
writes `replay_footprints.json`: for every ranked candidate, the footprint its
best hypothesis produces under the nominal forcing member, rasterised exactly as
scored and traced to lon/lat. The forecast stage writes `forecast_contours.json`:
50/75/90% contours over the particles behind each horizon's figures. Both are
served (`/replay-footprints`, `/forecast-contours`) and carried in the Case
contract, now schema 2; `attribution_result.json` and `forecast_result.json` are
unchanged. Fixed on the way: since matplotlib 3.8 a contour level returns all of
its loops in one path, and `density_contours` took it whole, so 4 of 675 rings
across the nine envelope timelines joined two lobes into one polygon with a false
edge between them. Levels are now split at each loop; the single-loop rings are
unchanged. Six tests added; 223 pass.

**Track display: gap windows, rendering-only paths, no invented vessel type.**
A new pipeline stage writes `track_display.json`. Per vessel it records every
window inside the declared AIS window with no usable position report (leading,
internal, trailing), counting sentinel positions as missing and wording them as
no position reported rather than as an outage; a test holds the leading and
trailing windows to exactly the hours the hindcast marks `no_data`. It adds a
centripetal Catmull-Rom path through the fixes for drawing, never across a gap,
with its largest departure from the straight segments stated; every analysis
still uses the original fixes. Vessel type is `null` with the reason: an MMSI
does not encode ship type and the source carries no AIS static data. Served at
`/track-display` and carried in the Case contract, schema 3.
`scripts/track_summary.py` prints the per-case table. Seven tests added; 230 pass.

**Interface: a native macOS design system and shell.** Tokens for light and dark
(system colours, vibrancy materials, separators, labels) with the legacy variable
names aliased onto them, so every panel follows the theme unedited; an
appearance control (System, Light, Dark) applied before first paint. System
fonts replace the web fonts. The shell is a translucent toolbar, a vibrant
sidebar whose single selection slides between rows, sections divided by
hairlines with sticky translucent headers instead of boxed cards, and a
translucent inspector. Hover and press use a lightly damped spring; reduced
motion and reduced transparency are honoured. Shell rules moved out of
`dashboard.css`, whose translucent white fills now use a token so dark mode
holds. No data, request or case logic changed.

**Conclusion graph rebuilt from real fields.** The graph removed on 25 September
for reading fields no artifact has returns as the same side-scrolling chain, in
pipeline order:
detection, historical filtering, forward replay beside the proximity baseline,
rank fragility, finding. Each value is an artifact field (status_counts,
discrimination, lead_retained_fraction, smallest_flip, abstention gate); a stage
whose artifact has not loaded says so. It now shows what the old one hid: on
case_0009 the top two candidates are not separated.

**Interface: generic, schema-driven cards.** Every panel is rebuilt from shared
primitives (Card, Stat, BarList, Badge, CaptionList, EmptyState) and reads the Case
contract from `/case`, plus `/report` for status counts and checksums and `/tracks`
for the map; a response for a case no longer selected is dropped. Every non-obvious
number carries a plain-language caption, visible by default, each checked against
the code that computes it. Fixed on the way: the finding said "tested N release
hypotheses" where N was candidate vessels; "Top Pick Right/Wrong" needed ground
truth the interface does not have and now says how the baseline relates to forward
replay; red and green verdict colours are gone; the next-observation card reads the
artifact's recommended window instead of recomputing it; a null shoreline fraction
reads "not modelled"; the scene card carries the note that downstream stages are
seeded from the generator mask; card state resets on case switch. Recharts is
replaced by native bars (bundle 619 KB to 271 KB).

---

## 13 September 2026

**Detect and characterise (PS part (a)) — new pipeline stage.**
`slicktrace_core/detection_geometry.py` runs the classical baseline detector over
each case scene, vectorises the retained region and measures area, perimeter,
principal axes, elongation and bearing. Served at
`/api/incidents/{id}/detection`, drawn as an outline over the scene in the
interface. IoU 0.91–0.92 against the generator truth mask across all six cases —
reported separately from the 0.676/0.688 benchmark-split figures, which measure
a deliberately harder task. Recorded as assumption A15: geometry is measured on
the pixel grid, not reprojected into the declared metric CRS.

**Interface — the finding now precedes the evidence.**
A verdict band states the outcome in plain language before any panel: the
proximity baseline's pick struck through, the forward-replay candidate beside
it, and on absent-source cases an explicit refusal to name anyone. A case
switcher exposes all six cases with their family and outcome, so the
cherry-picking objection can be checked rather than argued. Forecast, coverage,
next-observation and provenance panels surface results the API already served
but nothing displayed.

**Fresh-start rehearsal — two README defects found and fixed.**
Performed on a clean macOS account following the README literally. The Usage
section assumed an activated virtualenv and failed at its first command with
`ModuleNotFoundError`; the Docker section referenced a container name Compose
does not create. Both would have blocked a reviewer. Recorded in
`docs/evidence/fresh_start_rehearsal.md`.

**Docker — three executions recorded.**
Clean build, acceptance check online, and acceptance check with the container's
network disconnected, all 6/6. The build revealed that the Dockerfile still
copied `varuna_core/`, which the rename had removed — the image had never been
buildable. Logs in `docs/evidence/`.

**Dependencies pinned.** `requirements.lock` (34 packages) and
`requirements-dev.lock`. Case artifacts regenerate byte-identically under the
pinned set.

**Documentation.** Licence appendix now records four evaluated-but-unadopted
dependencies and their licence consequences — notably that OpenDrift is GPL v2
and would require relicensing this repository. README names the real-data
integration path per layer. Maintainer, licence holder and host matrix recorded.

---

## Before you merge: check which baseline you have

Two versions of this project have been in play.

**If your local repo has `slicktrace_core/fragility.py`**, you have the newer tree
and only the "Session changes" section below is new to you.

**If it does not**, your repo is the older build and the "Already present"
section is new to you as well — that is a much larger delta, and you should
treat this zip as the reference rather than cherry-picking from it.

Quick check:

```bash
ls slicktrace_core/fragility.py 2>/dev/null && echo "newer tree" || echo "older tree"
```

---

## Session changes — 12 files

### Fixed: release-acceptance check failed against its own tree

`scripts/smoke_test.py`

Hardcoded `V-TRUE-0001` and `V-DECOY-NEAR`, identifiers the generator no longer
produces. It failed 4/6 while the system underneath was entirely correct — a
broken test reporting a broken product.

Expected vessels now resolve from `truth.json` **by role** (`true_source`,
`near_decoy`) at run time, read from the local checkout and never from the API.
When the sidecar is unavailable — smoke-testing a remote host without the repo —
it falls back to structural checks and prints a note saying it is testing less,
rather than silently weakening.

**Both numeric tolerances are unchanged: `0.55` and `0.30`.** Loosening either
would have falsified the result rather than tested it. Verified 6/6 in both
modes, and 5/6 when the artifact is deliberately tampered with, which proves the
check can still fail.

### Fixed: Docker named volume shadowed baked-in cases

`Dockerfile`, `scripts/docker-entrypoint.sh`

A named volume is populated from the image only when first created. Cases were
copied straight to `/app/data`, the mount point, so every `build && up` after the
first would serve stale results while reporting a new image — silent, and exactly
the failure that bites during a rehearsal.

Cases now bake into `data_seed/`, the image carries a `.seed_id` content hash,
and the entrypoint syncs seed → volume when the ids differ, before the startup
check runs. Verified by executing the sync logic against a simulated volume
across three scenarios: fresh, restart, and rebuild-with-changed-cases. The
rebuild correctly served new data while a user-created extra case survived
untouched.

### Fixed: metric popovers were unreachable by tap

`frontend/src/MetricInfo.jsx`

`onMouseEnter` opened the popover and `onClick` toggled it, so the click
immediately closed what the hover had opened. Touch browsers synthesise
`mouseenter` before `click`, so on mobile the explanation never appeared. Hover
worked; tap silently did nothing — which is precisely the interaction the plan
asks for ("hover or tap").

Fixed with a separate `pinned` state distinguishing hover-open from
deliberate-open, plus `onBlur` for keyboard users.

### Wired up: the live slider, fragility control and metric help

`frontend/src/App.jsx`, `frontend/src/api.js`, `frontend/src/dashboard.css`

`TimeSliderMap.jsx`, `FragilityPanel.jsx` and `MetricInfo.jsx` existed but
`App.jsx` never imported them and `api.js` exposed no method for six endpoints.
They were tree-shaken out of the built bundle entirely.

This was more than an import. **None of the CSS these components needed
existed** — every class they referenced was undefined, which is presumably why
they were never wired. Added ~200 lines to `dashboard.css` using only existing
design tokens; no new colours.

Browser-verified on desktop and mobile: slider present and keyboard-operable
(6 × ArrowRight moves 04:30 → 22:30 UTC), `aria-valuetext` correct, 7-row
text-equivalent table, 4 fragility sweep steps, 2 metric popovers, zero console
errors, zero external requests.

Also fixed a header-wrap regression this introduced — the fourth topbar tag
squeezed the wordmark onto two lines at narrow widths.

### Added: recall and precision

`slicktrace_core/baseline_detector.py`, `scripts/run_validation.py`

The plan asks for recall ≥ 0.85 and precision alongside IoU. Neither was
measured.

**This surfaced a finding worth knowing before the deck is written: the
classical baseline reaches recall 0.68 on val and 0.70 on test, against a 0.85
target.** Precision is 0.89–0.99 and false-positive rates are 0.000, so the
detector is conservative rather than inaccurate — it rejects patchy regions,
which buys precision and costs recall.

The report states the miss in bold rather than reporting IoU alone and letting
the target go unmentioned. It is also a sharper argument for the U-Net than
existed before: the number to beat is recall, not IoU.

### Added: runtime reporting

`scripts/run_pipeline.py`, `scripts/run_validation.py`

Per-stage timings were already being measured and then discarded at exit, which
forfeited a feasibility claim the run had already earned. Now written to
`docs/runtime.json` with the hardware named, and surfaced in the validation
report.

Query latency is split four ways after a first version reported "0 ms" for both
cold and warm — the timer was starting after the knowledge base had already
loaded, and the cheapest intent finishes in microseconds. Now: 1.2 ms cold /
0.01 ms warm for a lookup intent, 3.9 ms cold / 1.0 ms warm for the
envelope-backed time-window query, against a 2-second target.

### Added: regression test for the frozen case

`tests/test_frozen_case.py` — 6 tests

Pins the demo invariant **by role** so it survives regeneration, and asserts no
vessel key contains "true", "decoy", "source" and similar. Reverting to
hardcoded identifiers now fails loudly instead of silently reintroducing the
ground-truth leak.

### Added: dependency pins

`requirements.txt`

All nine packages pinned exactly to the versions every number in the validation
report was produced under, verified programmatically against the installed
environment. torch remains deliberately absent from the served path.

### Added: LICENSE

MIT, which `manifest.provenance.license` already referenced but which did not
exist. Includes scope notes separating code from data.

**Two fields are yours to confirm:** the licence choice, and the copyright
holder line, currently "Slick Trace team (SIH26143)".

### Added: three appendices

- `docs/assumptions_register.md` — 13 entries, each with a verified `file:line`
  locator and its failure mode
- `docs/licence_and_data_rights.md` — what ships, under what terms, what a real
  source would need
- `docs/sustainability_and_ownership.md` — running costs, refresh cadence,
  handover position, roadmap

### Changed: `.dockerignore`

`truth.json` excluded from the image. This was blocked before, because
excluding it would have broken in-container smoke tests — the role-resolution
fix unblocked it. Also excluded `tests/` and `.pytest_cache/`.

### Rewritten: README

Was five steps out of date and still cited identifiers that no longer exist. Now
matches the tree, links the appendices, and lists known limitations including the
recall miss.

---

## Already present — only new to you if your repo lacks `fragility.py`

Five modules: `fragility.py`, `coverage.py`, `forecast.py`,
`next_observation.py`, `report.py`. Six independently seeded cases across four
families, replacing the single case. A locked detection test split. Neutral MMSI
identifiers with ground truth moved to a dev-only `truth.json` sidecar and a
`_strip_truth` guard on every API response. `tests/test_invariants.py`,
`tests/nlp_suite.py`, `tests/test_api_and_suite.py`. `scripts/run_pipeline.py`
and `scripts/run_validation.py`. Eleven new API endpoints. The three frontend
components this session wired up.

---

## Verification of this package

Run from a clean extraction of this zip:

```bash
pip install -r requirements.lock -r requirements-dev.lock
python3 scripts/run_pipeline.py --regenerate   # ~32 s, six cases
python3 scripts/run_validation.py
python3 -m pytest tests/ -q                    # 119 passed

cd frontend && npm ci && npm run build && cd ..
./run.sh &                                     # or: uvicorn backend.app:app --port 8000
python3 scripts/smoke_test.py                  # 6/6
```

`frontend/dist`, `node_modules`, `__pycache__`, `.pytest_cache` and `.venv` are
excluded from this archive — build artefacts, regenerated by the commands above.

---

## Not verified anywhere, still on you

**Docker has never been built or run.** No daemon was available. The plan names
three executions that must happen and be recorded: `docker build` from a clean
context, a network-disconnected acceptance run, and a fresh-user start by a
teammate who did not write the code following only the README. A written
Dockerfile proves nothing.

**The U-Net is untrained.** torch does not fit the sandbox disk quota. It stays
labelled implemented-but-unevaluated everywhere, which is the correct framing.

**No real data.** Zenodo, DMA, NOAA and Copernicus are unreachable. Every result
is synthetic and labelled as such.

**No git history.** There is no `.git` directory, so there is no tagged build —
and the plan requires video, deck and code to demonstrably match. Initialise a
repository before recording anything.

Plus: host matrix, SPOC confirmation of the official rubric, the demo video, the
presentation, a named maintainer in the README, and one outside conversation.
