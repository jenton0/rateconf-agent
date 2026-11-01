"""Tests for the deterministic checks; they run without an API key."""
from rateconf import Charge, RateConfirmation, Stop, to_row, validate
from pathlib import Path


def make(stops, charges, total):
    return RateConfirmation(
        broker_name="Demo Broker", load_number="L-1", equipment="Dry Van", commodity=None,
        weight_lbs=None, stops=stops, charges=charges, total_usd=total,
        payment_terms=None, special_instructions=[],
    )


PU = Stop(kind="pickup", company="A", address="1 St", city="Joliet", state="IL", appointment="2026-10-30T08:00")
DEL = Stop(kind="delivery", company="B", address="2 St", city="Atlanta", state="GA", appointment="2026-11-01T06:00")


def test_clean_load_has_no_issues():
    rc = make([PU, DEL], [Charge(description="Line haul", amount_usd=2150), Charge(description="FSC", amount_usd=310)], 2460)
    assert validate(rc) == []
    assert to_row(rc, Path("x.pdf"), [])["status"] == "OK"


def test_total_mismatch_is_flagged():
    rc = make([PU, DEL], [Charge(description="Line haul", amount_usd=1800), Charge(description="Tarp", amount_usd=100)], 2000)
    assert any("add up to 1900.00" in i for i in validate(rc))


def test_delivery_before_pickup_is_flagged():
    early = DEL.model_copy(update={"appointment": "2026-10-29T06:00"})
    issues = validate(make([PU, early], [Charge(description="x", amount_usd=10)], 10))
    assert any("is before" in i for i in issues)


def test_missing_delivery_and_appointment():
    no_time = PU.model_copy(update={"appointment": None})
    issues = validate(make([no_time], [Charge(description="x", amount_usd=10)], 10))
    assert "no delivery stop" in issues
    assert any("missing appointment" in i for i in issues)


def test_bad_date_format():
    bad = DEL.model_copy(update={"appointment": "Nov 1 morning"})
    assert any("unreadable" in i for i in validate(make([PU, bad], [Charge(description="x", amount_usd=10)], 10)))
