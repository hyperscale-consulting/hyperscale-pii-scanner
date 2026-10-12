# pyright: reportPrivateUsage=false
import pytest

from hyperscale.pii_scanner import _engine


@pytest.fixture(scope="session", autouse=True)
def warm_engine() -> None:
    """Load the model once for the session so individual tests stay fast."""
    _engine.analyze("warm up")
