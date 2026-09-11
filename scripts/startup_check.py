"""
Startup checker (masterplan p.6): runs before the app starts serving,
reports host architecture, data/asset presence, and dependency status.
Exits non-zero with a clear message on anything critical missing, rather
than starting a broken server silently.
"""

from __future__ import annotations

import importlib
import os
import platform
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_PACKAGES = ["fastapi", "uvicorn", "numpy", "scipy", "PIL", "pydantic"]
REQUIRED_PATHS = {
    "at least one incident case": os.path.join(REPO_ROOT, "data", "cases"),
    "built frontend": os.path.join(REPO_ROOT, "frontend", "dist", "index.html"),
}


def check() -> bool:
    ok = True
    print("=" * 60)
    print("Slick Trace startup check")
    print("=" * 60)
    print(f"host arch:      {platform.machine()}")
    print(f"host system:    {platform.system()} {platform.release()}")
    print(f"python:         {platform.python_version()}")
    print(f"compute profile: CPU (reference release — no GPU/torch required to serve;"
          f" torch is only needed for optional offline U-Net training, see scripts/train_unet.py)")
    print("-" * 60)

    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
            print(f"[ok]   dependency importable: {pkg}")
        except ImportError as e:
            print(f"[FAIL] dependency missing: {pkg} ({e})")
            ok = False

    print("-" * 60)
    for label, path in REQUIRED_PATHS.items():
        if label == "at least one incident case":
            cases = [d for d in os.listdir(path)] if os.path.isdir(path) else []
            if cases:
                print(f"[ok]   {label}: found {cases}")
            else:
                print(f"[FAIL] {label}: none found under {path}")
                print(f"       fallback: run `python3 -m varuna_core.synth_generator` "
                      f"to create a synthetic demo case")
                ok = False
        else:
            if os.path.exists(path):
                print(f"[ok]   {label}: {path}")
            else:
                print(f"[FAIL] {label}: not found at {path}")
                print(f"       fallback: run `npm install && npm run build` in frontend/, "
                      f"or start the API alone and use it without the UI")
                ok = False

    print("=" * 60)
    if ok:
        print("All checks passed — starting server.")
    else:
        print("One or more checks FAILED — see fallback notes above. "
              "Do not treat a subsequent successful startup as validated on this host.")
    print("=" * 60)
    return ok


if __name__ == "__main__":
    success = check()
    sys.exit(0 if success else 1)
