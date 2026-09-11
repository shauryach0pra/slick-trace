# CHANGELOG

Everything that changed, so you can diff this against whatever you have locally
rather than guessing.

---

## Before you merge: check which baseline you have

Two versions of this project have been in play.

**If your local repo has `varuna_core/fragility.py`**, you have the newer tree
and only the "Session changes" section below is new to you.

**If it does not**, your repo is the older build and the "Already present"
section is new to you as well — that is a much larger delta, and you should
treat this zip as the reference rather than cherry-picking from it.

Quick check:

```bash
ls varuna_core/fragility.py 2>/dev/null && echo "newer tree" || echo "older tree"
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

`varuna_core/baseline_detector.py`, `scripts/run_validation.py`

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
holder line, currently "Slick Trace / OilTrace team (SIH26143)".

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
pip install -r requirements.txt
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
