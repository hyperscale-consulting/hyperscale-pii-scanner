# pyright: reportPrivateUsage=false
import socket

import pytest

from hyperscale.pii_scanner import HitKind
from hyperscale.pii_scanner import scan
from hyperscale.pii_scanner._recognisers import build_recognisers
from hyperscale.pii_scanner._recognisers.email import OfflineEmailRecognizer
from tests.helpers import matches


def _kinds(text: str) -> set[tuple[HitKind, str]]:
    return {(h.kind, h.text) for h in scan(text)}


def test_registry_has_no_us_or_unlisted_recognisers():
    names = {type(r).__name__ for r in build_recognisers()}
    assert not any(n.startswith("Us") for n in names)
    assert "CreditCardRecognizer" not in names
    assert "DateRecognizer" not in names
    assert "IpRecognizer" not in names


@pytest.mark.parametrize(
    "nhs",
    ["943 476 5919", "9434765919", "943-476-5919", "398 259 7919", "401 023 2137"],
)
def test_nhs_valid_numbers(nhs: str):
    assert (HitKind.NHS_NUMBER, nhs) in _kinds(f"NHS number {nhs} on file.")


@pytest.mark.parametrize("not_nhs", ["943 476 5918", "485 777 3456", "123 456 7890"])
def test_nhs_check_digit_failures_are_not_reported(not_nhs: str):
    kinds = _kinds(f"NHS number {not_nhs} on file.")
    assert not any(k == HitKind.NHS_NUMBER for k, _ in kinds)


def test_nhs_number_is_not_also_reported_as_phone():
    hits = scan("Her number is 943 476 5919.")
    assert [(h.kind, h.text) for h in hits] == [(HitKind.NHS_NUMBER, "943 476 5919")]


@pytest.mark.parametrize("nino", ["AB123456C", "AB 12 34 56 C", "JG 20 31 97 A"])
def test_nino_valid(nino: str):
    assert (HitKind.NATIONAL_INSURANCE_NUMBER, nino) in _kinds(f"NI number {nino}.")


@pytest.mark.parametrize(
    "not_nino",
    [
        "BG123456C",
        "GB123456C",
        "NK123456C",
        "KN123456C",
        "NT123456C",
        "TN123456C",
        "ZZ123456C",
        "DA123456C",
        "AO123456C",
        "AB123456E",
    ],
)
def test_nino_invalid_prefix_or_suffix(not_nino: str):
    kinds = _kinds(f"NI number {not_nino}.")
    assert not any(k == HitKind.NATIONAL_INSURANCE_NUMBER for k, _ in kinds)


@pytest.mark.parametrize(
    "phone",
    [
        "07911 123456",
        "+44 7911 123456",
        "0113 496 0000",
        "(0113) 4960000",
        "020 7946 0958",
        "+44 (0)20 7946 0958",
    ],
)
def test_uk_phone_positive(phone: str):
    assert (HitKind.PHONE, phone) in _kinds(f"Call {phone} now.")


@pytest.mark.parametrize("not_phone", ["123456789", "12345", "1 800 555 0199"])
def test_uk_phone_negative(not_phone: str):
    assert not any(k == HitKind.PHONE for k, _ in _kinds(f"Ref {not_phone} here."))


def test_email_and_url():
    kinds = _kinds(
        "Write to jane.smith@example.org or see https://www.example.org/report/1."
    )
    assert (HitKind.EMAIL, "jane.smith@example.org") in kinds
    assert any(k == HitKind.URL and "example.org" in t for k, t in kinds)


def test_email_validation_is_offline(monkeypatch: pytest.MonkeyPatch):
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    assert matches(OfflineEmailRecognizer(), "jane@example.org", "EMAIL_ADDRESS") == [
        ("jane@example.org", 1.0)
    ]
    assert (
        matches(OfflineEmailRecognizer(), "jane@example.notatld", "EMAIL_ADDRESS") == []
    )
