#!/bin/sh
# 1. Sync the image's demo cases into the data volume if they differ.
# 2. Run the startup checker; refuse to serve if it fails, per the
#    masterplan's "startup checker reports the exact issue" requirement (p.6).
set -e

SEED_DIR=/app/data_seed
DATA_DIR=/app/data

# A named volume mounted at /app/data is populated from the image only when it
# is first created. Without this sync, `docker compose build && up` after any
# change to the cases would serve whatever the volume happened to hold — stale
# results presented as a fresh build, with nothing on screen to say so.
if [ -f "$SEED_DIR/.seed_id" ]; then
  IMAGE_SEED_ID=$(cat "$SEED_DIR/.seed_id")
  VOLUME_SEED_ID=$(cat "$DATA_DIR/.seed_id" 2>/dev/null || echo "none")
  if [ "$IMAGE_SEED_ID" != "$VOLUME_SEED_ID" ]; then
    echo "Incident data in the volume does not match this image"
    echo "  image:  $IMAGE_SEED_ID"
    echo "  volume: $VOLUME_SEED_ID"
    echo "Refreshing the baked-in demo cases from the image. Any additional"
    echo "cases you created in the volume are left untouched."
    mkdir -p "$DATA_DIR"
    cp -r "$SEED_DIR/cases" "$DATA_DIR/"
    printf '%s' "$IMAGE_SEED_ID" > "$DATA_DIR/.seed_id"
  else
    echo "Incident data in the volume matches this image ($IMAGE_SEED_ID)."
  fi
fi

if ! python3 scripts/startup_check.py; then
  echo "Startup check failed — not starting the server. See messages above." >&2
  exit 1
fi

exec uvicorn backend.app:app --host 0.0.0.0 --port 8000
