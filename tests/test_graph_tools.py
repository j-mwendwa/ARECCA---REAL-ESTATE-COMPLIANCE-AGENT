from src.graph.tools import validate_rent_schedule


def test_fixed_percentage():
    result = validate_rent_schedule.invoke({
        "base_rent_monthly": 5000.0,
        "lease_term_months": 36,
        "escalation_type": "fixed_percentage",
        "escalation_rate": 3.0,
    })
    assert result["is_valid"]
    assert len(result["projected_schedule"]) == 3
    assert result["projected_schedule"][0]["annual_rent"] == 60000.0
    assert result["projected_schedule"][1]["annual_rent"] == 61800.0


def test_fixed_percentage_with_cap():
    result = validate_rent_schedule.invoke({
        "base_rent_monthly": 5000.0,
        "lease_term_months": 24,
        "escalation_type": "fixed_percentage",
        "escalation_rate": 5.0,
        "escalation_cap": 3.0,
    })
    assert result["is_valid"]
    assert result["projected_schedule"][1]["annual_rent"] == 61800.0


def test_fixed_amount():
    result = validate_rent_schedule.invoke({
        "base_rent_monthly": 4000.0,
        "lease_term_months": 24,
        "escalation_type": "fixed_amount",
        "escalation_rate": 2400.0,
    })
    assert result["is_valid"]
    assert result["projected_schedule"][0]["annual_rent"] == 48000.0
    assert result["projected_schedule"][1]["annual_rent"] == 50400.0


def test_detects_discrepancy():
    result = validate_rent_schedule.invoke({
        "base_rent_monthly": 5000.0,
        "lease_term_months": 24,
        "escalation_type": "fixed_percentage",
        "escalation_rate": 3.0,
        "stated_schedule": [
            {"year": 1, "annual_rent": 60000.0, "monthly_rent": 5000.0},
            {"year": 2, "annual_rent": 63000.0, "monthly_rent": 5250.0},
        ],
    })
    assert not result["is_valid"]
    assert len(result["discrepancies"]) == 1


def test_no_escalation():
    result = validate_rent_schedule.invoke({
        "base_rent_monthly": 3000.0,
        "lease_term_months": 12,
        "escalation_type": "none",
        "escalation_rate": 0.0,
    })
    assert result["is_valid"]
    assert result["projected_schedule"][0]["annual_rent"] == 36000.0
