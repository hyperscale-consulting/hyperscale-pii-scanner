"""Download the pinned spaCy model wheel and unpack it into the package.

Usage: python3 scripts/vendor_model.py [--force]

Stdlib only so it runs before `uv sync` and inside CI without a venv.
"""

from __future__ import annotations

import hashlib
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

MODEL_NAME = "en_core_web_md"
MODEL_VERSION = "3.8.0"
WHEEL_URL = (
    "https://github.com/explosion/spacy-models/releases/download/"
    f"{MODEL_NAME}-{MODEL_VERSION}/{MODEL_NAME}-{MODEL_VERSION}-py3-none-any.whl"
)
WHEEL_SHA256 = "5e6329fe3fecedb1d1a02c3ea2172ee0fede6cea6e4aefb6a02d832dba78a310"

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_ROOT = REPO_ROOT / "src" / "hyperscale" / "pii_scanner" / "_model"
TARGET = MODEL_ROOT / f"{MODEL_NAME}-{MODEL_VERSION}"
# Inside the wheel the model data lives at <pkg>/<pkg>-<version>/
WHEEL_PREFIX = f"{MODEL_NAME}/{MODEL_NAME}-{MODEL_VERSION}/"


def verify(data: bytes, expected_sha256: str) -> None:
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise SystemExit(f"sha256 mismatch: expected {expected_sha256}, got {digest}")


def unpack(wheel_bytes: bytes, target: Path, prefix: str = WHEEL_PREFIX) -> int:
    """Extract the model directory from the wheel. Returns the file count."""
    count = 0
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as zf:
        for info in zf.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            relative = Path(info.filename[len(prefix) :])
            if relative.is_absolute() or ".." in relative.parts:
                raise SystemExit(f"refusing unsafe path in wheel: {info.filename}")
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    if count == 0:
        raise SystemExit(f"no files under {prefix} in wheel")
    return count


def main(argv: list[str]) -> int:
    force = "--force" in argv
    if (TARGET / "meta.json").exists() and not force:
        print(f"model already present at {TARGET}")
        return 0
    print(f"downloading {WHEEL_URL}")
    with urllib.request.urlopen(WHEEL_URL, timeout=120) as response:  # noqa: S310
        data = response.read()
    verify(data, WHEEL_SHA256)
    if TARGET.exists():
        shutil.rmtree(TARGET)
    count = unpack(data, TARGET)
    print(f"unpacked {count} files to {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
