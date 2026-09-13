# Fresh-start rehearsal

Recorded 13 September 2026.

## How it was done, stated honestly

A separate macOS user account on the same machine, with no repo, no virtual
environment, no `node_modules`, no Docker images and a different shell profile.
The README was followed literally; nothing was fixed from memory, and every
stop was recorded as a finding before being worked around.

This is a substitute for a genuinely independent user, not a replacement. The
operator had prior knowledge of the project. A second account removes the
environment but not the knowledge, and that limitation is stated rather than
papered over.

## What passed from a clean clone

- `git clone` → `run.sh` arrived executable, no permission error
- `uv venv` + `uv pip install` → 38 packages from both lock files
- `npm install` → 67 packages, 0 vulnerabilities
- `run_pipeline.py --regenerate` → 6 cases, 4 families, 13.1s
- `run_validation.py` → 4/4 Top-1 vs 0/4 naive, 2/2 abstentions, 40/40 NLP
- `pytest tests/ -q` → 119 passed
- `run.sh` → frontend built, dashboard loaded in the browser
- `smoke_test.py` → 6/6, identical figures to the development machine
  (IoU 0.688 / 0.087, top 419336692, naive 419824090)

Every headline number in this submission reproduced from a clean checkout.

## Findings, and what was changed

**1. The Usage section assumed an activated environment without saying so.**
Following it literally gave `ModuleNotFoundError: No module named 'numpy'` at
the first command, because `python3` resolved to the system interpreter. A
reviewer could reasonably have read that as a broken project. `source
.venv/bin/activate` is now the first line of that block.

**2. `docker compose` was unavailable despite Docker being installed.**
Docker Desktop is installed system-wide, but the Compose CLI plugin lives in
the per-user `~/.docker/cli-plugins`, so the account had `docker` without
`docker compose`. The README now checks `docker compose version` first and
says why it can be missing.

**3. The README's offline-verification command was stale.** It referenced a
container name Compose does not create and tested only `/api/health` from the
host, which cannot work once the network is removed. Replaced with the
commands actually executed in `docker_build.txt` / `smoke_offline.txt`.

Findings 1 and 3 would each have cost a reviewer following the README exactly.
Neither was visible from the development machine, where the environment was
already correct — which is the reason this rehearsal is required at all.
