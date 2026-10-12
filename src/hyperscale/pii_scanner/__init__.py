"""Deterministic, offline scan for residual personal identifiers in UK English text."""

from importlib.metadata import version as _dist_version

from ._engine import configure
from ._engine import scanner_version
from ._types import Hit
from ._types import HitKind
from ._types import ScannerVersion

__version__ = _dist_version("hyperscale-pii-scanner")

__all__ = [
    "Hit",
    "HitKind",
    "ScannerVersion",
    "__version__",
    "configure",
    "scanner_version",
]
