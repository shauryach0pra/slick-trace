# Host and architecture matrix

Recorded 12 September 2026. Hosts that could not be tested are declared
untested rather than omitted, and no "runs on any OS" claim is made anywhere
in this submission.

| Host | Architecture | Result | Evidence |
|---|---|---|---|
| macOS 26.2 (Apple silicon) | arm64 | **Pass** | Native and container, see below |
| Linux x86-64 | amd64 | Untested | No machine available |
| Windows x86-64 (Docker Desktop / WSL 2) | amd64 | Untested | No machine available |
| macOS Intel | amd64 | Untested | No machine available |

## What passed on the tested host

Native — Python 3.12.14, Node v25.9.0:

- `python3 -m pytest tests/ -q` → 119 passed
- `npm run build` → frontend built clean
- `./run.sh` → API and UI served on :8000
- `python3 scripts/smoke_test.py` → 6/6, full identity check

Container — Docker 29.4.0, image `slicktrace:cpu`:

- `docker build` → completed from a clean context, 12 runtime steps
- startup check → six cases found, frontend present, CPU profile reported
- smoke test online → 6/6
- smoke test with the container's network disconnected → 6/6

Logs in `docker_build.txt`, `smoke_online.txt`, `smoke_offline.txt`.

## Two portability findings from the tested host

Both were found by setting the project up on a machine that had never run it.

1. **`run.sh` arrived without its executable bit.** Git had not recorded mode
   755, so a fresh clone failed with permission denied. Fixed with
   `git update-index --chmod=+x`; new clones are runnable.
2. **pip cannot create a venv on macOS 26.** Python reads the OS version as
   empty strings, and pip's macOS certificate code raises `ValueError`
   converting that to an integer, so `ensurepip` fails on both Python 3.12 and
   3.14. This is a pip/macOS incompatibility, not a defect in this project.
   Workaround: `uv venv --python 3.12 .venv` then
   `uv pip install --python .venv/bin/python -r requirements.lock`.

## Prerequisites, stated honestly

Docker isolates dependencies; it does not remove host requirements. A reviewer
without Docker Desktop and a supported Linux-container backend is blocked by
the container rather than helped by it. The native path (`run.sh`, Python 3.12,
Node 20+) is supported and documented for exactly that case.
