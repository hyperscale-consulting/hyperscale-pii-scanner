import re

from hyperscale import pii_scanner


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", pii_scanner.__version__)
