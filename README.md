<div align="center">

### Slick Trace

</div>

<div align="center">

[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=fff)](#) [![FastAPI](https://img.shields.io/badge/FastAPI-009485.svg?logo=fastapi&logoColor=white)](#) [![NumPy](https://img.shields.io/badge/NumPy-4DABCF?logo=numpy&logoColor=fff)](#) [![Matplotlib](https://custom-icon-badges.demolab.com/badge/Matplotlib-71D291?logo=matplotlib&logoColor=fff)](#) [![PyTorch](https://img.shields.io/badge/PyTorch-ee4c2c?logo=pytorch&logoColor=white)](#) [![React](https://img.shields.io/badge/React-%2320232a.svg?logo=react&logoColor=%2361DAFB)](#) [![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=fff)](#)

</div>

---

### Overview

Slick Trace detects oil slicks in radar imagery and works out which vessel most plausibly caused them. Instead of naming the ship nearest the slick, it replays a release from every candidate vessel's AIS track, drifts the oil forward through modelled currents under six forcing variants, and ranks each candidate by how well its replayed oil recreates the observed slick. When no candidate fits well enough, it declines to name anyone.

On nine synthetic cases with known ground truth, forward replay names the true source in 7 of 7 source-present cases, against 0 of 7 for nearest-vessel proximity (exact McNemar p = 0.0156). Every result is an investigative lead, not proof of responsibility.

---

### Demo

- Demo Video: [Watch on Youtube](https://www.youtube.com/watch?v=oEyRfSFHWvo)
- Live Dashboard: [shauryachopra.dev/slicktrace](https://shauryachopra.dev/slicktrace) 

### Project Structure

```
slick-trace/
├── backend/                  # FastAPI app: 31 API routes, serves the built dashboard
├── frontend/                 # React + Vite dashboard
│   └── src/
│       ├── cards/            # Evidence cards: Case Finding, Rank Fragility, Forward Exposure, ...
│       ├── map/              # Replay Map (MapLibre GL), time bar, replay timeline
│       ├── tour/             # Guided tour (driver.js)
│       └── ui/               # Shared primitives, charts, count-up and in-view hooks
├── slicktrace_core/          # The pipeline
│   ├── schema.py             # Data contracts every stage reads
│   ├── synth_generator.py    # Synthetic cases with known ground truth
│   ├── baseline_detector.py  # Classical detector: local-contrast threshold, connected components
│   ├── unet_model.py         # U-Net detector (PyTorch)
│   ├── detection_geometry.py # Area, perimeter, axes and orientation of the slick
│   ├── hindcast.py           # Backtracking; each vessel candidate, excluded or unassessed
│   ├── attribution.py        # Forward replay: ranks candidates by physical fit
│   ├── fragility.py          # Rank fragility under perturbed assumptions
│   ├── coverage.py           # Coverage-aware matching of vessels with hidden AIS
│   ├── forecast.py           # +6, +12 and +24 h forward exposure
│   ├── next_observation.py   # Next-observation advisory
│   ├── nlp_query.py          # Ask Slick Trace: rule-based intents, no language model
│   ├── leak_audit.py         # Checks that no answer leaks into the benchmark
│   ├── report.py             # Investigation report (JSON and Markdown)
│   ├── dossier.py            # Four-page PDF investigation dossier
│   ├── ais_quality.py        # AIS field validation against ITU-R M.1371 sentinels
│   ├── identity.py           # MMSI structure validation and flag state lookup
│   ├── radiometry.py         # SAR radiometry scale inference (DN, linear, dB)
│   ├── speckle.py            # Lee adaptive speckle filtering
│   └── adapters/             # GeoTIFF scenes and MarineCadastre AIS CSV
├── scripts/                  # Pipeline, validation, U-Net training and evaluation, smoke test
├── tests/                    # 359 tests (pytest)
├── docs/                     # Validation, calibration, assumptions, licences, sustainability
├── data/                     # Generated cases and detection data
├── Dockerfile                # CPU image: builds the dashboard, bakes in the cases
├── docker-compose.yml        # CPU deployment with a persistent data volume
└── run.sh                    # Builds the dashboard if needed and serves it on :8000
```

---

### Tech Stack

**Backend and pipeline**
- Python 3.12, FastAPI and Uvicorn, with Pydantic for the data contracts
- NumPy and SciPy for particle tracking, detection and geometry
- Matplotlib for scene and envelope rendering, Pillow for images
- ReportLab for the PDF dossier

**Detection**
- Classical baseline detector with Lee adaptive speckle filtering
- U-Net trained in PyTorch with a Tversky loss (PyTorch is installed separately and is not needed to run the app)

**Frontend**
- React 19 and Vite
- MapLibre GL for the Replay Map, driver.js for the guided tour
- Self-hosted fonts (@fontsource), so the dashboard works offline

**Quality**
- pytest, oxlint, and a GitHub Actions test workflow

**Optional**
- rasterio for the GeoTIFF adapter; it pulls in GDAL (over 100 MB), so it is left out of the runtime requirements and imported only when used

---

### Installation

```bash
# Python environment and dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock -r requirements-dev.lock

# Frontend dependencies
cd frontend && npm install && cd ..
```

> **macOS 26 note.** `python3 -m venv` fails at `ensurepip` on macOS 26: pip cannot parse the OS version and raises `ValueError`. This is a pip/macOS incompatibility, not a project defect. Use `uv` instead:
>
> ```bash
> uv venv --python 3.12 .venv
> uv pip install --python .venv/bin/python -r requirements.lock -r requirements-dev.lock
> ```
>
> If `./run.sh` reports permission denied, run `chmod +x run.sh`.

To train or evaluate the U-Net, also install PyTorch (`pip install torch`). To read real GeoTIFF scenes, install rasterio (`pip install rasterio`).

---

### Usage

**Run the dashboard**

```bash
./run.sh
```

This activates the environment, builds the dashboard if it has not been built, and serves the API and UI at http://localhost:8000. After changing frontend code, rebuild with `(cd frontend && npm run build)`.

**Run the pipeline and checks**

```bash
source .venv/bin/activate

python3 scripts/run_pipeline.py --regenerate    # regenerate all cases and run every stage
python3 scripts/run_validation.py               # score the benchmark; writes docs/validation_report.*
python3 -m pytest tests/ -q                     # test suite
python3 scripts/verify_document_claims.py       # check every documented claim against the repository
python3 scripts/smoke_test.py                   # acceptance check against a running server
```

**U-Net detector**

```bash
python3 scripts/train_unet.py        # train the U-Net
python3 scripts/eval_unet.py         # evaluate it on the validation and test splits
python3 scripts/fit_calibration.py   # calibrate the ensemble win fraction on a held-out set
```

**Docker**

```bash
docker build -t slicktrace:cpu .
docker compose --profile cpu up -d      # serves on http://localhost:8000
docker compose --profile cpu down       # stop and remove the container
```

The image bakes in the demo cases and seeds the data volume on first start. To confirm it works offline, cut the container's network and rerun the smoke test:

```bash
docker network disconnect slick-trace_default slick-trace-slicktrace-1
docker exec slick-trace-slicktrace-1 python3 scripts/smoke_test.py
docker network connect slick-trace_default slick-trace-slicktrace-1
```

---

### Configuration

- `VITE_ARCGIS_API_KEY` (optional, in `frontend/.env.local`): an Esri key for the satellite basemap on the Replay Map. It is built into the dashboard, so restrict it to your domain in the ArcGIS dashboard. Without it, the map uses an offline coastline and the app makes no outbound calls.
- Case families and seeds live in `CASE_PLAN` in `slicktrace_core/synth_generator.py`: nine cases across `decoy` (3), `moving_discharge` (2), `absent_source` (2), `crowded` and `along_track_ribbon`.
- Ground truth lives in each case's `truth.json` and is never loaded by the API or the UI.

---

### Key Features

**Attribution**
- Forward replay of every candidate under six forcing variants, scored against the observed slick
- 7 of 7 source-present cases correct, against 0 of 7 for nearest-vessel proximity (exact McNemar p = 0.0156)
- Abstains when the best fit is below the gate: correct in 1 of 2 source-absent cases; in the other a passer-by clears the gate and is named, recorded as a known limitation (A10)

**Detection and characterisation**
- Slick outline, area, perimeter, principal axes and orientation, measured in metres
- Trained U-Net: test IoU 0.968, recall 0.998, no false positives on look-alike or clean scenes

**Traffic filtering**
- Backtracking under reversed forcing; each vessel is a candidate, excluded or unassessed
- Missing evidence is marked unassessed, never treated as clearance

**Robustness and exposure**
- Rank fragility: 80 perturbed runs per case, with the smallest change that flips the leader
- Forward exposure at +6, +12 and +24 h, with shoreline and sensitive-area contact
- Coverage-aware matching of radar contacts with no AIS (71% of hidden-AIS vessels recovered in tests)

**Ask Slick Trace**
- Thirteen recognised intents by regex and keyword matching, with no language model
- Every answer cited; similarity search declines until an incident corpus exists, and anything else is refused rather than guessed

**Integrity**
- Ground truth never reaches the API or UI; a `_strip_truth` middleware removes any stray field
- A leak audit on every validation checks that bookkeeping gives no hint of the answer
- Investigation report in JSON and Markdown, and a four-page PDF dossier with SHA-256 checksums

---

### Verification Status

| Check | Command | Status |
|-------|---------|--------|
| Startup&nbsp;check | `python3 scripts/startup_check.py` | pass |
| Determinism |   regenerate, diff analysis artifacts | byte-identical, 9 cases, verified in CI on Ubuntu x86-64 |
| Test&nbsp;suite | `python3 -m pytest tests/ -q` | 359 passed, 8 skipped |
| Document&nbsp;claims | `python3&nbsp;scripts/verify_document_claims.py` | 38 passed, 0 failed |
| Validation | `python3 scripts/run_validation.py` | 7/7 attribution (naive 0/7, exact McNemar p = 0.0156), 1/2 abstentions, 3 of 35 leak-audit rules flagged (about 2.8 expected by chance), 47/47 NLP |
| Acceptance | `python3 scripts/smoke_test.py` | 5/5 |
| API | 31 API routes and 404 paths | pass, no 500s |
| Frontend | `npm run lint && npm run build` | 0 errors, 1 warning |
| Browser | headless Chromium, desktop and mobile | 0 console errors; no external requests unless the Esri key is set |
| Docker | `docker compose --profile cpu up` | image built and run, health check passing |

> **What byte-identical covers.** Every analysis artifact (attribution, fragility, hindcast, coverage, forecast, next-observation, detection) is byte-identical after regeneration on a different OS and architecture, checked in CI. Generated media are not: PNG encoding depends on the zlib build and `.npz` archives store timestamps, so those files differ between platforms while their contents do not. `manifest.json` carries SHA-256 checksums of those files and differs for the same reason. The claim is about the results, not their containers.

---

### Known Limitations

- Classical baseline detector recall is 0.860 on validation and 0.819 on test, against a 0.85 target: met on validation, missed on test. The U-Net exceeds it on both.
- In one of the two source-absent cases, a passer-by clears the fit gate and is named (A10).
- Slick geometry uses a local azimuthal-equidistant projection rather than a full reprojection into the declared UTM zone (EPSG:32643); over a one-degree scene the difference is far below the detector's boundary uncertainty (A15).
- No DuckDB/Parquet layer, and no unstructured evidence index or similarity search.
- The next-observation advisory is computed and exported in the report and API, but is not shown in the dashboard.
- The GeoTIFF and MarineCadastre adapters are implemented but not yet tested on real data.
- The `--reveal-truth` flag is development-only and must never be exposed in production.

---

### Real Data Integration

The system runs on synthetic data by design: the generator owns the ground truth, which is what makes the decoy, absent-source and crowded-traffic families testable at all. No real dataset can tell you which vessel actually caused a given slick, so the measured 7/7 against 0/7 could not be produced on real imagery.

The path to real data is an adapter, not a rewrite: every pipeline stage reads `slicktrace_core.schema`, not a source format. Named candidates, with the work each implies:

| Layer | Candidate | Effort and caveat |
|---|---|---|
| SAR&nbsp;imagery | Zenodo Sentinel-1 oil-spill dataset, Parts I–III | ~96 GB. Part II negatives are essential: its look-alike masks are zero-valued oil masks, not outlines of the look-alike |
| Ship&nbsp;contacts | `allenai/vessel-detection-sentinels` | Production models from Skylight; would replace the stand-in contact detector behind the coverage metrics |
| AIS&nbsp;decoding | `pyais` | Message-level only |
| AIS tracks | MovingPandas, or AISdb for larger extracts | MovingPandas is in-memory; AISdb adds a database but scales |
| Transport | OpenDrift / OpenOil | **GPL v2 — would require relicensing this repository from MIT.** See `docs/licence_and_data_rights.md` |
| Oil&nbsp;properties | NOAA ADIOS (`adios_db`) | Unencumbered. Would replace blind variation of density and windage with measured values |
| Shoreline | GSHHG | LGPL library over public-domain data |
| Protected&nbsp;areas | WDPA via `pywdpa` | Mandatory attribution string in README, report export and interface |
| Forcing | Copernicus ERA5 and Marine reanalysis | Accounts and attribution required |

Two things would then need re-establishing rather than assuming: detection metrics against real look-alikes, and the fact that real cases have no source label, so attribution accuracy becomes unmeasurable without independently confirmed incidents.

---

### Documentation

| Document | Contents |
|----------|----------|
| `docs/validation_report.md` | Measured results: attribution, abstention, detection, NLP, coverage, next-observation, runtime, ablations, origin error per case |
| `docs/calibration_report.md` | Ensemble win fraction against synthetic truth: Brier, ECE, reliability bins, held-out |
| `docs/assumptions_register.md` | 24 modelling assumptions with code locators and failure modes |
| `docs/licence_and_data_rights.md` | Code and data licensing, and real-world deployment requirements |
| `docs/sustainability_and_ownership.md` | Running costs, refresh cadence, handover position, roadmap |
| `docs/runtime.json` | Per-stage timings with hardware specifications |
| `docs/evidence/` | Smoke test results, Docker build logs and verification evidence |

---

### License

MIT License; see `LICENSE`. Code and data rights are separated: source licences, redistribution status and required attribution strings for every dataset are recorded in `docs/licence_and_data_rights.md`.

---

### Maintainer and handover

**Shaurya Chopra** — shauryachopra@zohomail.in — [github.com/shauryach0pra](https://github.com/shauryach0pra)

Continuity does not rest on a second reader being available: nine cases regenerate byte-identically from fixed seeds, 359 automated tests run on every regeneration, and a scripted acceptance check verifies the frozen case against declared tolerances. A no-obligation handover (code, manifests, assumptions register, licence appendix and validation report) is offered to the evaluating body; see `docs/sustainability_and_ownership.md`.

---

<div align="center">

Built by [Shaurya Chopra](https://shauryachopra.dev/)

</div>
