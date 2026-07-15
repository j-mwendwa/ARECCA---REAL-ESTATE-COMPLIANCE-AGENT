from datetime import date
from src.validation.math_validator import validate_rent_escalation
from src.extraction.schemas import LeaseTerms, RentSchedule


def test_fixed_percentage_valid():
    terms = LeaseTerms(
        base_rent_monthly=5000.0,
        lease_term_months=36,
        escalation_type="fixed_percentage",
        escalation_rate=3.0,
        escalation_frequency_months=12,
        rent_schedule=[
            RentSchedule(year=1, annual_rent=60000.0, monthly_rent=5000.0, escalation_percent=0.0),
            RentSchedule(year=2, annual_rent=61800.0, monthly_rent=5150.0, escalation_percent=3.0),
            RentSchedule(year=3, annual_rent=63654.0, monthly_rent=5304.5, escalation_percent=3.0),
        ],
    )
    result = validate_rent_escalation(terms)
    assert result.is_valid


def test_fixed_percentage_mismatch():
    terms = LeaseTerms(
        base_rent_monthly=5000.0,
        lease_term_months=24,
        escalation_type="fixed_percentage",
        escalation_rate=3.0,
        escalation_frequency_months=12,
        rent_schedule=[
            RentSchedule(year=1, annual_rent=60000.0, monthly_rent=5000.0, escalation_percent=0.0),
            RentSchedule(year=2, annual_rent=63000.0, monthly_rent=5250.0, escalation_percent=3.0),
        ],
    )
    result = validate_rent_escalation(terms)
    assert not result.is_valid
    assert len(result.discrepancies) == 1


def test_fixed_amount_valid():
    terms = LeaseTerms(
        base_rent_monthly=4000.0,
        lease_term_months=24,
        escalation_type="fixed_amount",
        escalation_rate=2400.0,
        escalation_frequency_months=12,
        rent_schedule=[
            RentSchedule(year=1, annual_rent=48000.0, monthly_rent=4000.0, escalation_percent=0.0),
            RentSchedule(year=2, annual_rent=50400.0, monthly_rent=4200.0, escalation_percent=2400.0),
        ],
    )
    result = validate_rent_escalation(terms)
    assert result.is_valid


def test_no_escalation():
    terms = LeaseTerms(
        base_rent_monthly=3000.0,
        lease_term_months=12,
        escalation_type="none",
        escalation_rate=0.0,
    )
    result = validate_rent_escalation(terms)
    assert result.is_valid
    assert len(result.discrepancies) == 0


def test_no_rent_schedule_stated():
    terms = LeaseTerms(
        base_rent_monthly=5000.0,
        lease_term_months=36,
        escalation_type="fixed_percentage",
        escalation_rate=3.0,
        escalation_frequency_months=12,
        rent_schedule=None,
    )
    result = validate_rent_escalation(terms)
    assert result.is_valid
    assert len(result.projected_schedule) == 3


def test_escalation_with_cap():
    terms = LeaseTerms(
        base_rent_monthly=5000.0,
        lease_term_months=24,
        escalation_type="fixed_percentage",
        escalation_rate=5.0,
        escalation_cap=3.0,
        escalation_frequency_months=12,
    )
    result = validate_rent_escalation(terms)
    assert result.is_valid
    assert result.projected_schedule[1]["annual_rent"] == 61800.0
