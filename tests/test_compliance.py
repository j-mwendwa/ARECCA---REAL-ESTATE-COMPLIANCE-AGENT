from src.compliance.engine import run_compliance_check
from src.compliance.rules import ComplianceRule
from src.extraction.schemas import LeaseTerms
from datetime import date


def test_late_fee_excessive():
    terms = LeaseTerms(
        base_rent_monthly=5000.0,
        late_fee_amount=10.0,
        late_fee_is_percentage=True,
        grace_period_days=5,
    )
    report = run_compliance_check("test-1", terms)
    flags_by_id = {f.rule_id: f for f in report.flags}
    assert "LATE_FEE_CAP" in flags_by_id
    assert flags_by_id["LATE_FEE_CAP"].risk_level == "high"


def test_late_fee_reasonable():
    terms = LeaseTerms(
        base_rent_monthly=5000.0,
        late_fee_amount=3.0,
        late_fee_is_percentage=True,
        grace_period_days=5,
    )
    report = run_compliance_check("test-2", terms)
    flags_by_id = {f.rule_id: f for f in report.flags}
    assert "LATE_FEE_CAP" not in flags_by_id


def test_missing_grace_period():
    terms = LeaseTerms(
        base_rent_monthly=5000.0,
        grace_period_days=0,
    )
    report = run_compliance_check("test-3", terms)
    flags_by_id = {f.rule_id: f for f in report.flags}
    assert "GRACE_PERIOD" in flags_by_id


def test_security_deposit_excessive():
    terms = LeaseTerms(
        base_rent_monthly=5000.0,
        security_deposit=15000.0,
    )
    report = run_compliance_check("test-4", terms)
    flags_by_id = {f.rule_id: f for f in report.flags}
    assert "DEPOSIT_CAP" in flags_by_id


def test_all_clean():
    terms = LeaseTerms(
        base_rent_monthly=5000.0,
        late_fee_amount=3.0,
        late_fee_is_percentage=True,
        grace_period_days=5,
        security_deposit=5000.0,
        escalation_type="fixed_percentage",
        escalation_rate=3.0,
        escalation_frequency_months=12,
    )
    report = run_compliance_check("test-5", terms)
    assert len(report.flags) == 0
    assert report.overall_risk_level == "low"
