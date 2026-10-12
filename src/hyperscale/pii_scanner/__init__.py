"""Deterministic, offline scan for residual personal identifiers in UK English text."""

from importlib.metadata import version as _dist_version

__version__ = _dist_version("hyperscale-pii-scanner")

__all__ = ["__version__"]
