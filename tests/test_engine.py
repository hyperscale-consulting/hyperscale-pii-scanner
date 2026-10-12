# pyright: reportPrivateUsage=false
import socket
import threading
from pathlib import Path

import pytest

from hyperscale.pii_scanner import _engine
from hyperscale.pii_scanner import configure
from hyperscale.pii_scanner import scanner_version


@pytest.fixture
def fresh_engine():
    _engine.reset_for_tests()
    yield
    _engine.reset_for_tests()


def test_default_model_is_the_vendored_directory():
    assert _engine.DEFAULT_MODEL_PATH.name == "en_core_web_md-3.8.0"
    assert (_engine.DEFAULT_MODEL_PATH / "meta.json").exists()


def test_scanner_version_reports_components_without_loading_engine(fresh_engine: None):
    v = scanner_version()
    assert v.presidio_analyzer == "2.2.364"
    assert v.spacy == "3.8.16"
    assert v.model_name == "en_core_web_md"
    assert v.model_version == "3.8.0"
    assert _engine.is_loaded() is False


def test_analyze_finds_a_person(fresh_engine: None):
    results = _engine.analyze("Jane Smith lives in Harrogate.")
    found = {(r.entity_type, r.start, r.end) for r in results}
    assert ("PERSON", 0, 10) in found
    assert ("LOCATION", 20, 29) in found


def test_configure_after_load_raises(fresh_engine: None):
    _engine.analyze("warm up")
    with pytest.raises(RuntimeError, match="already"):
        configure(model="en_core_web_lg")


def test_configure_with_missing_path_fails_at_first_scan(
    fresh_engine: None, tmp_path: Path
):
    configure(model=tmp_path / "nope")
    with pytest.raises(OSError):
        _engine.analyze("Jane Smith")


def test_engine_loads_and_scans_without_network(
    fresh_engine: None, monkeypatch: pytest.MonkeyPatch
):
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    results = _engine.analyze(
        "Jane Smith emailed jane@example.org; see https://example.org/report today."
    )
    assert results  # the engine worked with networking disabled


def test_engine_is_built_once_under_concurrency(fresh_engine: None):
    seen: list[int] = []

    def work() -> None:
        _engine.analyze("Jane Smith")
        seen.append(id(_engine._state.engine))

    threads = [threading.Thread(target=work) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(set(seen)) == 1


def test_unknown_model_package_fails_before_any_download(
    fresh_engine: None, monkeypatch: pytest.MonkeyPatch
):
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    configure(model="en_core_web_zz")
    with pytest.raises(RuntimeError, match="not installed"):
        _engine.analyze("Jane Smith")


def test_scanner_version_with_unknown_package_raises_runtime_error(fresh_engine: None):
    configure(model="en_core_web_zz")
    with pytest.raises(RuntimeError, match="not installed"):
        scanner_version()
