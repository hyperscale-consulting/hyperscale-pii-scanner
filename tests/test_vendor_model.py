import hashlib
import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "vendor_model.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("vendor_model", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_wheel(prefix: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{prefix}meta.json", '{"name": "core_web_md"}')
        zf.writestr(f"{prefix}ner/model", "binary")
        zf.writestr("en_core_web_md/__init__.py", "")
    return buf.getvalue()


def test_verify_rejects_wrong_digest():
    vm = _load_script()
    with pytest.raises(SystemExit, match="sha256 mismatch"):
        vm.verify(b"abc", "0" * 64)
    vm.verify(b"abc", hashlib.sha256(b"abc").hexdigest())


def test_unpack_extracts_only_the_model_directory(tmp_path: Path):
    vm = _load_script()
    count = vm.unpack(_fake_wheel(vm.WHEEL_PREFIX), tmp_path / "model")
    assert count == 2
    assert (tmp_path / "model" / "meta.json").read_text() == '{"name": "core_web_md"}'
    assert (tmp_path / "model" / "ner" / "model").exists()
    assert not (tmp_path / "model" / "__init__.py").exists()


def test_unpack_rejects_path_traversal(tmp_path: Path):
    vm = _load_script()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{vm.WHEEL_PREFIX}../../evil", "x")
    with pytest.raises(SystemExit, match="unsafe path"):
        vm.unpack(buf.getvalue(), tmp_path / "model")
