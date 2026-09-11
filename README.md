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
varuna/
├── backend/              # FastAPI application serving attribution results
├── frontend/             # React + Vite dashboard with live time-slider controls
├── varuna_core/          # Core attribution pipeline modules
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
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

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
# Start CPU-only deployment
docker compose --profile cpu up

# Offline verification (disconnect network, still works)
docker compose --profile cpu up -d
docker network disconnect $(docker compose ps -q varuna | xargs docker inspect -f '{{range $$net,$$v := .NetworkSettings.Networks}}{{$$net}}{{end}}') varuna-cpu-1 --force
curl http://localhost:8000/api/health
```

---

### Configuration

**Environment Variables:**
- `PYTHONUNBUFFERED=1` - Disable Python output buffering
- `PYTHONDONTWRITEBYTECODE=1` - Prevent .pyc file generation

**Data Configuration:**
- Synthetic cases are generated from seeds in `varuna_core/synth_generator.py` (keeping existing module name for compatibility)
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
| `docs/assumptions_register.md` | 13 modelling assumptions with code locators and failure modes |
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

This system currently uses synthetic data for demonstration. To deploy with real-world data:

1. Download Zenodo Sentinel-1 oil-spill dataset (Parts I/II/III) and DMA or NOAA AIS extracts
2. Write an adapter mapping them into `varuna_core.schema.SceneObservation` / `VesselTrack` with `Provenance.status = OBSERVED` (keeping existing module structure)
3. No other changes required — every pipeline stage reads the schema, not the source format

---

### License

MIT License — see `LICENSE` file for details. Note scope notes separating code from data rights.

---

<div align="center">

Built by [Shaurya Chopra](https://shauryachopra.dev/)

</div>
