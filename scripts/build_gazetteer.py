"""Build data/uk_places.txt from the GeoNames GB extract.

Usage: uv run --group gazetteer python scripts/build_gazetteer.py [--input GB.zip]

Rules (see the design spec):
- populated places (feature class P) with population >= 1,000
- ADM2 areas (counties, unitary authorities) and ADM3 areas within Greater
  London (admin2 code GLA), with administrative prefixes and suffixes stripped
- single-word names whose lower-cased form has a wordfreq Zipf frequency >= 4.5
  are dropped unless listed in scripts/gazetteer_extra.txt
- scripts/gazetteer_stoplist.txt removes names; scripts/gazetteer_extra.txt adds them

GeoNames data is CC BY 4.0: https://www.geonames.org/
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import sys
import urllib.request
import zipfile
from collections.abc import Callable
from collections.abc import Iterable
from pathlib import Path

GEONAMES_URL = "https://download.geonames.org/export/dump/GB.zip"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "src" / "hyperscale" / "pii_scanner" / "data" / "uk_places.txt"
STOPLIST = REPO_ROOT / "scripts" / "gazetteer_stoplist.txt"
EXTRAS = REPO_ROOT / "scripts" / "gazetteer_extra.txt"
MIN_POPULATION = 1000
MAX_ZIPF = 4.5
LONDON_ADMIN2 = "GLA"

PREFIXES = (
    "London Borough of ",
    "Royal Borough of ",
    "Metropolitan Borough of ",
    "City and Borough of ",
    "City and County of ",
    "Borough of ",
    "City of ",
    "County of ",
    "District of ",
    "Sir ",
)
SUFFIXES = (" County Borough", " District", " Borough")
NAME_OK = re.compile(r"^[A-Z][A-Za-z'’\- ]*[A-Za-z]$")


def strip_admin(name: str) -> str:
    for prefix in PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    for suffix in SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.strip()


def read_list(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def select_names(
    rows: Iterable[list[str]],
    zipf: Callable[[str], float | None],
    *,
    stoplist: set[str],
    extras: set[str],
    min_population: int = MIN_POPULATION,
) -> tuple[set[str], list[str]]:
    """Return (names, dropped_by_frequency).

    ``zipf`` maps a lower-cased word to its Zipf score (or None if unknown).
    """
    candidates: set[str] = set()
    for row in rows:
        name, fclass, fcode = row[1], row[6], row[7]
        population = int(row[14] or 0)
        admin2 = row[11]
        if fclass == "P" and population >= min_population:
            candidates.add(name)
        elif fclass == "A" and fcode == "ADM2":
            candidates.add(strip_admin(name))
        elif fclass == "A" and fcode == "ADM3" and admin2 == LONDON_ADMIN2:
            candidates.add(strip_admin(name))
    dropped: list[str] = []
    names: set[str] = set()
    for name in candidates:
        if not NAME_OK.match(name) or len(name) < 3 or name in stoplist:
            continue
        if " " not in name and "-" not in name:
            score = zipf(name.lower())
            if score is not None and score >= MAX_ZIPF:
                dropped.append(name)
                if name not in extras:
                    continue
        names.add(name)
    names |= {e for e in extras if e not in stoplist}
    return names, sorted(dropped)


def load_rows(source: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(source)) as zf:
        text = zf.read("GB.txt").decode("utf-8")
    return list(csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE))


def write_output(names: set[str], extract_date: str) -> None:
    header = [
        "# UK place names for hyperscale-pii-scanner.",
        f"# Source: GeoNames GB extract ({GEONAMES_URL}), licensed CC BY 4.0,",
        "# data from GeoNames (https://www.geonames.org/).",
        f"# Extract date: {extract_date}. Rules: populated places with population"
        f" >= {MIN_POPULATION},",
        "# ADM2 areas, London ADM3 boroughs; single-word names with wordfreq Zipf >= "
        f"{MAX_ZIPF} dropped unless in scripts/gazetteer_extra.txt;",
        "# scripts/gazetteer_stoplist.txt applied. Regenerate with `make gazetteer`.",
        f"# Entries: {len(names)}",
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(header + sorted(names)) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    from wordfreq import zipf_frequency

    if "--input" in argv:
        source = Path(argv[argv.index("--input") + 1]).read_bytes()
    else:
        print(f"downloading {GEONAMES_URL}", file=sys.stderr)
        with urllib.request.urlopen(GEONAMES_URL, timeout=120) as response:  # noqa: S310
            source = response.read()
    rows = load_rows(source)
    names, dropped = select_names(
        rows,
        lambda word: zipf_frequency(word, "en"),
        stoplist=read_list(STOPLIST),
        extras=read_list(EXTRAS),
    )
    write_output(names, dt.date.today().isoformat())
    print(f"wrote {len(names)} names to {OUTPUT}", file=sys.stderr)
    print("dropped by frequency (add to gazetteer_extra.txt to keep):", file=sys.stderr)
    print("  " + ", ".join(dropped), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
