# VARUNA / OilTrace (SIH26143) — build log

Oil-spill source attribution: detect a slick, reconstruct plausible releases from
candidate vessel tracks, and report how well each one explains the observation —
or that none of them does.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 scripts/run_pipeline.py --regenerate   # rebuild all cases from seeds, run every stage
python3 scripts/run_validation.py              # score them, write docs/validation_report.md
python3 -m pytest tests/ -q                    # invariant + API + NLP suite
```

`run_pipeline.py` is the reproducibility entry point. From a clean checkout it
rebuilds every artifact the API, the UI and the report read, so nothing shown to
a reviewer depends on a file that cannot be regenerated. A full run is ~32 s for
six cases on CPU.

Running the app:

```bash
./run.sh                       # builds the frontend if needed, serves API + UI on :8000
python3 scripts/smoke_test.py  # release-acceptance check against the running instance
```

## Pipeline

Strictly ordered and artifact-mediated. Changing an upstream stage makes every
downstream artifact on disk stale, which is the easiest way for this repo to
look healthy while being wrong — regenerate rather than trusting what is checked in.

```
synth_generator → hindcast → attribution → fragility → coverage
                                        → forecast → next_observation → report
                                                   ↓
                                       backend serves JSON → frontend renders
```

| Module | Role |
| --- | --- |
| `varuna_core/schema.py` | The join contract. Everything else conforms to it |
| `varuna_core/synth_generator.py` | Writes `data/cases/<id>/{manifest,truth}.json`, scene, mask, forcing |
| `varuna_core/hindcast.py` | Backward envelope → `historical_mapping.json` |
| `varuna_core/attribution.py` | Forward-replay ranking + naive baseline |
| `varuna_core/fragility.py` | Smallest tested perturbation that flips the top rank |
| `varuna_core/coverage.py` | Hidden-AIS recovery experiment |
| `varuna_core/forecast.py` | 6/12/24 h exposure envelopes |
| `varuna_core/next_observation.py` | Which future observation best separates hypotheses |
| `varuna_core/report.py` | Investigation report export (JSON + Markdown) |
| `varuna_core/nlp_query.py` | "Ask VARUNA" — 11 regex intents, no LLM call, read-only |
| `varuna_core/{detection_data,baseline_detector,unet_model}.py` | Detection stage (semi-detached) |

## Status

- [x] **Incident schema + synthetic case generator.** Four case families —
      `decoy`, `moving_discharge`, `absent_source`, `crowded` — across six
      independently seeded cases (`CASE_PLAN` in `synth_generator.py`). The
      generator advects under a spatially varying current field while the
      attribution simulator assumes a constant one, so the method is not solving
      an exact copy of the simulator that produced the answer.

- [x] **Ground truth is not in the manifest.** It lives in a per-case
      `truth.json` that the API never loads and the UI never reads;
      `backend/app.py:_strip_truth` removes any stray ground-truth field from
      every response as a second line of defence. Vessel keys are neutral
      fictional MMSIs (419xxxxxx) in shuffled order.

      This matters more than it looks. Earlier builds used identifiers like
      `V-TRUE-0001` and `V-DECOY-NEAR`, which announced the answer in every
      chart, screenshot and video frame — a system that "finds" a vessel called
      V-TRUE has demonstrated nothing. Four tests in `tests/test_invariants.py`
      enforce this, and `tests/test_frozen_case.py` pins the demo result by
      **role** so it survives regeneration.

- [x] **Detection.**
      - `baseline_detector.py`: classical CV baseline, runs anywhere. Val IoU
        0.676, test IoU 0.688, 0.000 false-positive rate on look-alikes and on
        clean water.
      - `unet_model.py` + `scripts/train_unet.py`: a real trainable PyTorch
        U-Net, **implemented but unevaluated**. Installing torch pulls ~5 GB of
        CUDA dependencies that do not fit the sandbox disk quota. Until it is
        trained and compared on the identical split, the defensible detection
        claim is the baseline number alone — an architected-but-untrained model
        is a design, not a result.

- [x] **Historical mapping.** `hindcast.py` seeds particles from the observed
      slick, backtracks under reversed forcing with growing uncertainty
      (diffusion, not convergence), and tests each vessel's bounded-interpolated
      position against the particle cloud at each backward hour. Three outcomes
      per vessel — candidate / excluded / **unassessed** — never a forced binary.
      `unassessed` means no track data covered the window: missing evidence, not
      exoneration.

- [x] **Forward-replay attribution.** Samples release hypotheses (pulse and
      continuous) per surviving candidate, runs forward twins under a *shared*
      6-member ensemble of wind/current/diffusivity perturbations — identical
      perturbations for every candidate, which is what makes the comparison
      fair — scores IoU + boundary distance + area error + a complexity penalty,
      and refuses to name a top candidate below the absolute IoU gate.

      Dispersion grows with elapsed drift time (`~sqrt(hours)`) in **both** the
      truth generator and the forward simulator. Without this, a vessel sitting
      at the slick's location could fake a good fit regardless of how implausible
      its timing was, and the comparison against proximity would be circular.

      Result across six cases: forward replay gets 4/4 Top-1 on source-present
      cases where naive proximity gets 0/4, and abstains correctly on 2/2
      source-absent cases. Per-case results and Wilson intervals are in
      `docs/validation_report.md`.

- [x] **Rank-fragility explorer.** Walks a grid of plausible perturbations in
      increasing standardised magnitude and reports the smallest one that changes
      the leader, with both runs available for inspection. A sensitivity
      counterfactual, not proof of causal responsibility.

- [x] **Coverage-aware matching, forecast, next-observation advisor, report
      export.** See `docs/validation_report.md` for measured results, including
      the hidden-AIS recovery rate with its operating point stated.

- [x] **Ask VARUNA.** Eleven intents via regex/keyword parsing — no LLM call, so
      behaviour is fully inspectable and testable. Every answer returns the
      interpreted filters and citations alongside the templated text. Refuses
      rather than guesses on similarity search (no indexed corpus beyond these
      cases) and on out-of-domain questions; those refusals are scored as passes
      in the 40-question frozen suite, because a system that answers everything
      has not been tested for grounding.

      Not yet done: the masterplan's "typed query compiled to allowlisted SQL
      over DuckDB" (p.5) is simplified here to bounded read-only Python functions
      over the JSON artifacts. Same intent/resolver shape, no DuckDB wired up.

- [x] **FastAPI + React app.** `backend/app.py` is a thin wrapper over the
      artifacts; the `StaticFiles` mount stays last, since it is mounted at `/`
      and shadows anything registered after it. `frontend/` is Vite + React with
      self-hosted `@fontsource` fonts — no runtime CDN call, which the offline
      packaging requires anyway.

- [x] **Live historical replay, fragility control, and inline metric help.**
      `TimeSliderMap.jsx`, `FragilityPanel.jsx` and `MetricInfo.jsx` are wired
      into `App.jsx`, with the six previously-missing endpoint methods added to
      `api.js` and the styles they needed added to `dashboard.css`.

      The UTC control is a live instrument, not a rendered filmstrip: it queries
      `/envelope` for the requested time, so a reviewer can stop anywhere and
      watch candidates enter and leave the envelope. It is a native range input,
      keyboard operable with a visible focus ring, publishes `aria-valuetext`,
      and the same state appears as a text table under the map. Vessel state is
      carried by shape as well as colour.

- [x] **Docker packaging.** Multi-stage build (node builds the frontend, python
      serves it). No torch/CUDA in the served image. `startup_check.py` reports
      host arch, dependencies and data presence, and the entrypoint refuses to
      serve if it fails.

      The compose file mounts a named volume at `/app/data` so incident data
      survives restarts. Demo cases are therefore baked into `data_seed/` rather
      than `data/`, and the entrypoint syncs seed → volume whenever their ids
      differ. Copying straight into the mount point would mean every rebuild
      after the first was silently masked by a stale volume.

      **Not executed:** there is no Docker daemon in this sandbox. The build, the
      network-disconnected run and the fresh-user start have not happened. Until
      they do and their output is recorded, treat the Dockerfile as reviewed, not
      verified.

## Verification status

| Check | Command | Last result |
| --- | --- | --- |
| Syntax + imports | `py_compile`, import graph | pass |
| Startup check | `python3 scripts/startup_check.py` | pass |
| Determinism | regenerate, diff all artifacts | **bit-identical**, 6 cases |
| Test suite | `python3 -m pytest tests/ -q` | 119 passed |
| Dependency pins | every `==` vs installed | all match |
| Validation | `python3 scripts/run_validation.py` | 4/4, 0/4 naive, 2/2 abstentions, NLP 40/40 |
| Acceptance | `python3 scripts/smoke_test.py` | 6/6 |
| API | 16 endpoints + 404 paths | pass, no 500s |
| Frontend | `npm run lint && npm run build` | 0 errors, 2 warnings |
| Browser | headless Chromium, desktop + mobile | 0 console errors, 0 external requests |
| Slider | keyboard-driven, 6 × ArrowRight | 04:30 → 22:30 UTC, both viewports |
| Metric popovers | click and tap | open on both viewports |
| Docker | — | **reviewed, not executed** (no daemon) |

The smoke test resolves the expected winner from `truth.json` **by role**, not by
a hardcoded identifier, and reads that sidecar from the local checkout — never
from the API. Running it against a remote host without the repo falls back to
structural checks and says so rather than silently testing less. Its two numeric
tolerances are the real acceptance criteria: loosening either would falsify the
result rather than test it.

## Documents

| Document | Contents |
| --- | --- |
| `docs/validation_report.md` | Measured results: attribution, abstention, detection, NLP, coverage, next-observation, runtime, ablations |
| `docs/assumptions_register.md` | Appendix A — 13 modelling assumptions, each with its code locator and failure mode |
| `docs/licence_and_data_rights.md` | Appendix B — what ships, under what terms, what a real source would need |
| `docs/sustainability_and_ownership.md` | Appendix C — running costs, refresh cadence, handover position, roadmap |
| `docs/runtime.json` | Per-stage timings with the hardware they were measured on |
| `LICENSE` | MIT, plus scope notes separating code from data |

## Real data is not included

This sandbox cannot reach Zenodo, DMA, NOAA or Copernicus. Everything here runs
on `synth_generator`, labelled `DataStatus.SYNTHETIC` in every manifest.
Synthetic ranking accuracy is not a measurement of real-world attribution
accuracy. To go from demo to real:

1. Download the Zenodo Sentinel-1 oil-spill dataset (Parts I/II/III) and DMA or
   NOAA AIS extracts.
2. Write an adapter mapping them into `varuna_core.schema.SceneObservation` /
   `VesselTrack` with `Provenance.status = OBSERVED`.
3. Nothing else changes — every later stage reads the schema, not the source format.

## Known limitations

- No DuckDB/Parquet layer; no unstructured evidence index or similarity search.
- No geometry in a metric projection (`metric_crs` is recorded but unused).
- U-Net unevaluated; detection recall and precision not yet reported.
- The classical baseline misses the recall target: 0.68 val / 0.70 test against
  0.85 (masterplan p.15). IoU and false-positive rates clear their targets, so
  the detector is conservative rather than inaccurate. Reported as a miss in
  `docs/validation_report.md` rather than omitted — closing it is what training
  the U-Net is for.
- Coverage, forecast and next-observation results are computed, served by the
  API and included in the report export, but are not yet on the dashboard.
- `--reveal-truth` on `scripts/visualize_case.py` is dev-only. It must never
  become a default or be reachable from the API or UI.
