<div align="center">

### Slick Trace

</div>

<div align="center">

[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=fff)](#) [![FastAPI](https://img.shields.io/badge/FastAPI-009485.svg?logo=fastapi&logoColor=white)](#) [![React](https://img.shields.io/badge/React-%2320232a.svg?logo=react&logoColor=%2361DAFB)](#) [![NumPy](https://img.shields.io/badge/NumPy-4DABCF?logo=numpy&logoColor=fff)](#) [![Matplotlib](https://custom-icon-badges.demolab.com/badge/Matplotlib-71D291?logo=matplotlib&logoColor=fff)](#) [![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=fff)](#)

</div>

---

### Overview

Slick Trace is an oil-spill source attribution system that detects slicks, reconstructs plausible releases from candidate vessel tracks, and reports how well each one explains the observation. The system uses a strictly ordered pipeline with synthetic case generation, historical mapping, forward-replay attribution, fragility analysis, coverage-aware matching, forecasting, and next-observation advisement. Ground truth is never exposed to the API or UI, ensuring attribution methods demonstrate genuine detection capability rather than recognizing known identifiers.

---

### Project Structure

```
slicktrace/
├── backend/              # FastAPI application serving attribution results
├── frontend/             # React + Vite dashboard with live time-slider controls
├── slicktrace_core/          # Core attribution pipeline modules
│   ├── schema.py         # Data contracts and validation schemas
│   ├── synth_generator.py # Synthetic case generation
│   ├── hindcast.py       # Historical vessel-slick mapping
│   ├── attribution.py    # Forward-replay ranking and comparison
│   ├── fragility.py      # Rank-fragility sensitivity analysis
│   ├── coverage.py       # Hidden-AIS recovery experiments
│   ├── forecast.py       # 6/12/24h exposure envelope prediction
│   ├── next_observation.py # Optimal future observation advisor
│   ├── report.py         # Investigation report export (JSON + Markdown)
│   ├── nlp_query.py      # "Ask Slick Trace" intent-based query system
│   └── detection/        # Oil slick detection (baseline + U-Net)
├── data/                 # Incident data (synthetic cases, volumes)
├── data_seed/            # Baked-in demo cases for Docker images
├── scripts/              # Pipeline execution, validation, and smoke tests
├── tests/                # Comprehensive test suite (119 tests)
├── docs/                 # Validation reports, assumptions, sustainability
└── docker-compose.yml    # Multi-stage Docker deployment
```

---

### Tech Stack

**Backend:**
- Python 3.12 with FastAPI and Uvicorn for REST API
- NumPy and SciPy for numerical computations and particle tracking
- Matplotlib for visualization and envelope generation
- Pydantic for data validation and schema enforcement
- Pytest for comprehensive testing (119 tests covering invariants, API, and NLP)

**Frontend:**
- React 19 with Vite for modern build tooling
- Recharts for data visualization
- Self-hosted fonts (@fontsource) for offline capability
- Keyboard-accessible time slider controls with ARIA support

**Detection:**
- Classical computer vision baseline detector (OpenCV-based)
- PyTorch U-Net architecture (implemented, requires separate training environment)

**Infrastructure:**
- Multi-stage Docker build (Node.js for frontend, Python for runtime)
- Named volumes for persistent incident data
- Health checks and startup validation
- CPU-only reference deployment (GPU optional for U-Net training)

---

### Installation

**Local Development:**

```bash
# Create virtual environment and install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.lock -r requirements-dev.lock

# Install frontend dependencies
cd frontend
npm install
cd ..
```


> **macOS 26 note.** `python3 -m venv` fails at `ensurepip` on macOS 26 — pip
> cannot parse the OS version and raises `ValueError`. This is a pip/macOS
> incompatibility, not a project defect. Use `uv` instead:
>
> ```bash
> uv venv --python 3.12 .venv
> uv pip install --python .venv/bin/python -r requirements.lock -r requirements-dev.lock
> ```
>
> If `./run.sh` reports permission denied, run `chmod +x run.sh`.

**Docker Deployment:**

```bash
# Build and run with Docker Compose
docker compose --profile cpu up

# Access the application at http://localhost:8000
```

---

### Usage

**Pipeline Execution:**

```bash
# Activate the environment first — every command below needs it
source .venv/bin/activate

# Regenerate all synthetic cases and run full pipeline
python3 scripts/run_pipeline.py --regenerate

# Run validation and generate reports
python3 scripts/run_validation.py

# Run test suite
python3 -m pytest tests/ -q
```

**Running the Application:**

```bash
# Local development (builds frontend, serves API + UI on :8000)
./run.sh

# Smoke test against running instance
python3 scripts/smoke_test.py
```

**Docker Usage:**

```bash
# Check Compose is available first — it is a per-user CLI plugin, so an
# account with Docker installed may still not have it
docker compose version

# Build the image, then start the CPU-only deployment
docker build -t slicktrace:cpu .
docker compose --profile cpu up -d

# Offline verification: cut the container's network, confirm it still passes
docker network disconnect slick-trace_default slick-trace-slicktrace-1
docker exec slick-trace-slicktrace-1 python3 scripts/smoke_test.py
docker network connect slick-trace_default slick-trace-slicktrace-1
```

---

### Configuration

**Environment Variables:**
- `PYTHONUNBUFFERED=1` - Disable Python output buffering
- `PYTHONDONTWRITEBYTECODE=1` - Prevent .pyc file generation

**Data Configuration:**
- Synthetic cases are generated from seeds in `slicktrace_core/synth_generator.py` (keeping existing module name for compatibility)
- Ground truth lives in per-case `truth.json` files (never loaded by API)
- Vessel identifiers use neutral fictional MMSIs (419xxxxxx)
- Docker uses named volumes at `/app/data` for persistent incident storage

**Pipeline Configuration:**
- Case families: `decoy`, `moving_discharge`, `absent_source`, `crowded`
- Six independently seeded cases defined in `CASE_PLAN`
- Attribution uses 6-member ensemble for wind/current/diffusivity perturbations
- IoU gate prevents false positives on low-confidence matches

---

### Verification Status

| Check | Command | Status |
|-------|---------|--------|
| Syntax + imports | `py_compile`, import graph | pass |
| Startup check | `python3 scripts/startup_check.py` | pass |
| Determinism | regenerate, diff all artifacts | bit-identical, 6 cases |
| Test suite | `python3 -m pytest tests/ -q` | 119 passed |
| Dependency pins | every `==` vs installed | all match |
| Validation | `python3 scripts/run_validation.py` | 4/4 attribution, 2/2 abstentions, 40/40 NLP |
| Acceptance | `python3 scripts/smoke_test.py` | 6/6 |
| API | 16 endpoints + 404 paths | pass, no 500s |
| Frontend | `npm run lint && npm run build` | 0 errors, 2 warnings |
| Browser | headless Chromium, desktop + mobile | 0 console errors, 0 external requests |
| Docker | — | reviewed, not executed (no daemon) |

---

### Key Features

**Attribution Accuracy:**
- Forward replay achieves 4/4 Top-1 on source-present cases vs 0/4 for naive proximity
- Correctly abstains on 2/2 source-absent cases
- Uses shared ensemble perturbations for fair candidate comparison
- Dispersion grows with elapsed drift time in both generator and simulator

**Historical Mapping:**
- Backtracks observed slicks under reversed forcing with growing uncertainty
- Three outcomes per vessel: candidate / excluded / unassessed
- No forced binary decisions — missing evidence is explicitly marked

**Fragility Analysis:**
- Smallest tested perturbation that flips top rank
- Sensitivity counterfactual with both runs available for inspection
- Grid-based perturbation exploration

**NLP Query System:**
- Eleven intents via regex/keyword parsing (no LLM calls)
- Fully inspectable and testable behavior
- Returns interpreted filters and citations with templated responses
- Refuses rather than guesses on out-of-domain questions

**Security & Privacy:**
- Ground truth never exposed to API or UI
- `_strip_truth` middleware removes any stray ground-truth fields
- Neutral vessel identifiers prevent answer leakage
- No outbound network calls in served application
- Self-hosted fonts for offline capability

---

### Documentation

| Document | Contents |
|----------|----------|
| `docs/validation_report.md` | Measured results: attribution, abstention, detection, NLP, coverage, next-observation, runtime, ablations |
| `docs/assumptions_register.md` | 15 modelling assumptions with code locators and failure modes |
| `docs/licence_and_data_rights.md` | Code vs data licensing terms and real-world deployment requirements |
| `docs/sustainability_and_ownership.md` | Running costs, refresh cadence, handover position, roadmap |
| `docs/runtime.json` | Per-stage timings with hardware specifications |

---

### Known Limitations

- No DuckDB/Parquet layer; no unstructured evidence index or similarity search
- No geometry in metric projection (recorded but unused)
- U-Net implemented but unevaluated (requires GPU environment for training)
- Classical baseline detector misses recall target (0.68 val / 0.70 test vs 0.85 target)
- Coverage, forecast, and next-observation results computed but not yet on dashboard
- `--reveal-truth` flag is development-only and must never be exposed in production

---

### Real Data Integration

This system runs on synthetic data by design: the generator owns the ground
truth, which is what makes the decoy, absent-source and crowded-traffic families
testable at all. No real dataset can tell you which vessel actually caused a
given slick, so the measured 4/4 against 0/4 could not be produced on real
imagery.

The path to real data is an adapter, not a rewrite — every pipeline stage reads
`slicktrace_core.schema`, not a source format. Named candidates, with the work
each implies:

| Layer | Candidate | Effort and caveat |
|---|---|---|
| SAR imagery | Zenodo Sentinel-1 oil-spill dataset, Parts I–III | ~96 GB. Part II negatives are essential: its look-alike masks are zero-valued oil masks, not outlines of the look-alike |
| Ship contacts | `allenai/vessel-detection-sentinels` | Production models from Skylight; would replace the stand-in contact detector behind the coverage metrics |
| AIS decoding | `pyais` | Message-level only |
| AIS tracks | MovingPandas, or AISdb for larger extracts | MovingPandas is in-memory; AISdb adds a database but scales |
| Transport | OpenDrift / OpenOil | **GPL v2 — would require relicensing this repository from MIT.** See `docs/licence_and_data_rights.md` |
| Oil properties | NOAA ADIOS (`adios_db`) | Unencumbered. Would replace blind variation of density and windage with measured values |
| Shoreline | GSHHG | LGPL library over public-domain data |
| Protected areas | WDPA via `pywdpa` | Mandatory attribution string in README, report export and interface |
| Forcing | Copernicus ERA5 and Marine reanalysis | Accounts and attribution required |

Two things would then need re-establishing rather than assuming: detection
metrics against real look-alikes, and the fact that real cases have no source
label, so attribution accuracy becomes unmeasurable without independently
confirmed incidents.

---

### License

MIT License — see `LICENSE` file for details. Note scope notes separating code from data rights.
Source licences, redistribution status and required attribution strings for every
dataset are recorded in `docs/licence_and_data_rights.md`.

---

### Maintainer and handover

**Shaurya Chopra** — shauryachopra@zohomail.in — [github.com/shauryach0pra](https://github.com/shauryach0pra)

Team Untangle (ID 124608), SIH 2026 problem statement 26143 (NTRO).

Built and maintained by one person. Continuity does not rest on a second reader
being available: six cases regenerate bit-identically from fixed seeds, 119
automated tests run on every regeneration, and a scripted acceptance check
verifies the frozen case against declared tolerances. A no-obligation handover —
code, manifests, assumptions register, licence appendix and validation report —
is offered to the evaluating body; see `docs/sustainability_and_ownership.md`.
Source licences, redistribution status and required attribution strings for every
dataset are recorded in `docs/licence_and_data_rights.md`.

---

### Maintainer and handover

**Shaurya Chopra** — shauryachopra@zohomail.in — [github.com/shauryach0pra](https://github.com/shauryach0pra)

Team Untangle (ID 124608), SIH 2026 problem statement 26143 (NTRO).

Built and maintained by one person. Continuity does not rest on a second reader
being available: six cases regenerate bit-identically from fixed seeds, 119
automated tests run on every regeneration, and a scripted acceptance check
verifies the frozen case against declared tolerances. A no-obligation handover —
code, manifests, assumptions register, licence appendix and validation report —
is offered to the evaluating body; see `docs/sustainability_and_ownership.md`.

---

<div align="center">

Built by [Shaurya Chopra](https://shauryachopra.dev/)

</div>
