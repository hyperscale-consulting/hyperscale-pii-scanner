import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release.py"
SAMPLE = """# Changelog

## [Unreleased]

### Added

- First thing.

## [0.1.0] - 2026-10-20

### Added

- Initial release.
"""


def _load():
    spec = importlib.util.spec_from_file_location("release", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_promote_unreleased_moves_section_under_new_version():
    rel = _load()
    updated = rel.promote_unreleased(SAMPLE, "0.2.0", "2026-11-01")
    assert (
        "## [Unreleased]\n\n## [0.2.0] - 2026-11-01\n\n### Added\n\n- First thing.\n"
        in updated
    )
    assert "## [0.1.0] - 2026-10-20" in updated


def test_promote_unreleased_refuses_empty_section():
    rel = _load()
    empty = "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-10-20\n"
    with pytest.raises(SystemExit, match="empty"):
        rel.promote_unreleased(empty, "0.2.0", "2026-11-01")


def test_section_notes_returns_body_for_version():
    rel = _load()
    assert rel.section_notes(SAMPLE, "0.1.0") == "### Added\n\n- Initial release."
    with pytest.raises(SystemExit, match="no CHANGELOG section"):
        rel.section_notes(SAMPLE, "9.9.9")
