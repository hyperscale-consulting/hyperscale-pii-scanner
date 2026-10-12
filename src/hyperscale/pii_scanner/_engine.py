"""One Presidio engine per process, built lazily, used under a lock."""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from dataclasses import field
from importlib.metadata import version as dist_version
from pathlib import Path

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer import RecognizerResult
from presidio_analyzer.nlp_engine import NerModelConfiguration
from presidio_analyzer.nlp_engine import SpacyNlpEngine

from ._recognisers import build_registry
from ._types import ScannerVersion

DEFAULT_MODEL_NAME = "en_core_web_md"
DEFAULT_MODEL_VERSION = "3.8.0"
DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent
    / "_model"
    / f"{DEFAULT_MODEL_NAME}-{DEFAULT_MODEL_VERSION}"
)
SCORE_THRESHOLD = 0.3
# spaCy labels that must never reach Presidio.
# DATE and TIME are replaced by UkDateRecognizer.
LABELS_TO_IGNORE = [
    "CARDINAL",
    "DATE",
    "EVENT",
    "FAC",
    "LANGUAGE",
    "LAW",
    "MONEY",
    "NORP",
    "ORDINAL",
    "PERCENT",
    "PRODUCT",
    "QUANTITY",
    "TIME",
    "WORK_OF_ART",
]


@dataclass
class _State:
    model: str | os.PathLike[str] = DEFAULT_MODEL_PATH
    engine: AnalyzerEngine | None = None
    build_lock: threading.Lock = field(default_factory=threading.Lock)
    scan_lock: threading.Lock = field(default_factory=threading.Lock)


_state = _State()


def configure(model: str | os.PathLike[str]) -> None:
    """Select the spaCy model: a package name or a path to a model directory.

    Must be called before the first scan in the process.
    """
    with _state.build_lock:
        if _state.engine is not None:
            raise RuntimeError(
                "configure() must be called before the engine is already loaded"
            )
        _state.model = model


def is_loaded() -> bool:
    return _state.engine is not None


def reset_for_tests() -> None:
    """Drop the engine and configuration. Test use only."""
    with _state.build_lock:
        _state.engine = None
        _state.model = DEFAULT_MODEL_PATH


def _build_engine() -> AnalyzerEngine:
    model = _state.model
    model_ref = os.fspath(model)
    if isinstance(model, os.PathLike) or os.sep in model_ref:
        if not Path(model_ref).is_dir():
            raise FileNotFoundError(f"spaCy model directory not found: {model_ref}")
    nlp_engine = SpacyNlpEngine(
        models=[{"lang_code": "en", "model_name": model_ref}],
        ner_model_configuration=NerModelConfiguration(
            labels_to_ignore=LABELS_TO_IGNORE
        ),
    )
    nlp_engine.load()
    return AnalyzerEngine(
        registry=build_registry(),
        nlp_engine=nlp_engine,
        supported_languages=["en"],
        default_score_threshold=SCORE_THRESHOLD,
    )


def _get_engine() -> AnalyzerEngine:
    engine = _state.engine
    if engine is not None:
        return engine
    with _state.build_lock:
        if _state.engine is None:
            _state.engine = _build_engine()
        return _state.engine


def analyze(text: str) -> list[RecognizerResult]:
    """Run Presidio over ``text``. Serialised: spaCy pipelines are not thread-safe."""
    engine = _get_engine()
    with _state.scan_lock:
        results: list[RecognizerResult] = engine.analyze(text, language="en")
    return results


def _model_identity() -> tuple[str, str]:
    model = _state.model
    model_ref = os.fspath(model)
    meta_path = Path(model_ref) / "meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return f"{meta['lang']}_{meta['name']}", str(meta["version"])
    return model_ref, dist_version(model_ref)


def scanner_version() -> ScannerVersion:
    """Component versions for audit logs. Does not load the model."""
    model_name, model_version = _model_identity()
    return ScannerVersion(
        library=dist_version("hyperscale-pii-scanner"),
        presidio_analyzer=dist_version("presidio-analyzer"),
        spacy=dist_version("spacy"),
        model_name=model_name,
        model_version=model_version,
    )
