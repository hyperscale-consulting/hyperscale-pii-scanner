import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_gazetteer.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_gazetteer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    name: str, fclass: str, fcode: str, population: int, admin2: str = ""
) -> list[str]:
    row = [""] * 19
    row[1] = name
    row[2] = name
    row[6] = fclass
    row[7] = fcode
    row[11] = admin2
    row[14] = str(population)
    return row


def test_strip_admin_prefixes_and_suffixes():
    bg = _load()
    assert bg.strip_admin("London Borough of Hackney") == "Hackney"
    assert (
        bg.strip_admin("Royal Borough of Kingston upon Thames")
        == "Kingston upon Thames"
    )
    assert bg.strip_admin("City of York") == "York"
    assert bg.strip_admin("Wyre Forest District") == "Wyre Forest"
    assert bg.strip_admin("Caerphilly County Borough") == "Caerphilly"
    assert bg.strip_admin("Sir Powys") == "Powys"
    assert bg.strip_admin("Kent") == "Kent"


def test_select_names_applies_population_frequency_stoplist_and_extras():
    bg = _load()
    rows = [
        _row("Harrogate", "P", "PPL", 89060),
        _row("Tinyhamlet", "P", "PPL", 120),
        _row("Street", "P", "PPL", 12911),
        _row("London", "P", "PPLC", 8961989),
        _row("London Borough of Hackney", "A", "ADM3", 273526, admin2="GLA"),
        _row("Wyre Forest District", "A", "ADM3", 100000, admin2="XX"),
        _row("Kent", "A", "ADM2", 1500000),
        _row("Bath", "P", "PPLA2", 101557),
    ]
    zipf = {
        "street": 5.28,
        "london": 5.27,
        "harrogate": 2.92,
        "kent": 4.17,
        "bath": 4.44,
        "hackney": 3.0,
    }
    names, dropped = bg.select_names(
        rows, zipf.get, stoplist={"Bath"}, extras={"London"}, min_population=1000
    )
    assert names == {"Harrogate", "London", "Hackney", "Kent"}
    assert "Street" in dropped and "London" in dropped
