# Execution evidence — Docker

Recorded 12 September 2026 on macOS 26.2, Apple silicon (arm64),
Docker 29.4.0. Image tag `slicktrace:cpu`.

| File | What it records |
|---|---|
| `docker_build.txt` | `docker build` from a clean context — completes, 12 runtime steps |
| `smoke_online.txt` | Acceptance check against the running container, network attached — 6/6 |
| `smoke_offline.txt` | Same check with the container's network disconnected — 6/6 |

## How the offline run was done

    docker compose --profile cpu up -d
    docker network disconnect slick-trace_default slick-trace-slicktrace-1
    docker exec slick-trace-slicktrace-1 python3 scripts/smoke_test.py

Network removal was verified first: opening a socket to 1.1.1.1:53 from inside
the container fails with `OSError: [Errno 101] Network is unreachable`.

## Two things a reviewer should know

**The check runs inside the container, not from the host.** Disconnecting the
Docker network also removes the host port forward, so `localhost:8000` is
unreachable from macOS while the container is offline. Running the check inside
the container tests the thing that matters — that the application needs no
egress — without the host forward confounding it.

**The in-container run uses structural checks, not identity checks.** The truth
sidecar is not shipped in the image, so the script says so and falls back:
both IoU tolerances still apply, and the naive baseline must still disagree
with forward replay. The full identity check runs from the repo checkout and is
recorded in `smoke_online.txt`. Both runs produced identical figures
(IoU 0.688 / 0.087, top 419336692, naive 419824090).

## Two bugs this exercise found

Neither was visible from reading the files; both required an actual build.

1. `Dockerfile` copied `varuna_core/`, which no longer exists after the rename.
   The build failed outright. Fixed to `slicktrace_core/`.
2. The offline instructions in `docker-compose.yml` referenced a container name
   (`slicktrace-cpu-1`) that compose does not create, and tested only
   `/api/health` from the host, which cannot work once the network is removed.
   Rewritten to the commands above, and `scripts/smoke_test.py` is now shipped
   in the image so the offline check needs no `docker cp`.
