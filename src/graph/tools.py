"""
High-efficiency math validation tool for rent escalation calculations.
Uses NumPy vectorization for batch schedule validation.
"""
import numpy as np
from typing import Any, Optional
from langchain_core.tools import tool

from src.config import cfg

_validation_cfg = cfg.get("validation", {})
_DECIMALS = _validation_cfg.get("rounding_decimals", 2)
_TOLERANCE = float(_validation_cfg.get("tolerance", 0.01))


@tool
def validate_rent_schedule(
    base_rent_monthly: float,
    lease_term_months: int,
    escalation_type: str,
    escalation_rate: float,
    escalation_cap: Optional[float] = None,
    stated_schedule: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """Validate a lease's rent escalation schedule using deterministic math.

    Computes the projected rent for each year of the lease term using the
    given escalation formula and compares it against any stated schedule.

    Args:
        base_rent_monthly: Initial monthly base rent in dollars.
        lease_term_months: Total lease term in months.
        escalation_type: 'fixed_percentage', 'fixed_amount', 'cpi_based', or 'none'.
        escalation_rate: Escalation rate (e.g. 3.0 for 3%, or $2400 for fixed_amount).
        escalation_cap: Optional maximum escalation percentage cap.
        stated_schedule: Optional list of dicts with 'year', 'annual_rent', 'monthly_rent'.

    Returns:
        Dict with 'is_valid', 'discrepancies', 'projected_schedule'.
    """
    num_years = max(lease_term_months // 12, 1)
    base_annual = base_rent_monthly * 12
    rate = float(escalation_rate)
    cap = float(escalation_cap) if escalation_cap else None

    years = np.arange(1, num_years + 1, dtype=np.float64)

    if escalation_type in ("fixed_percentage", "cpi_based") and rate > 0:
        annual_rate = rate / 100.0
        if cap:
            annual_rate = min(annual_rate, cap / 100.0)
        projected_annual = base_annual * (1 + annual_rate) ** (years - 1)
    elif escalation_type == "fixed_amount" and rate > 0:
        projected_annual = base_annual + (rate * (years - 1))
    else:
        projected_annual = np.full(num_years, base_annual, dtype=np.float64)

    projected_annual = np.round(projected_annual, _DECIMALS)
    projected_monthly = np.round(projected_annual / 12, _DECIMALS)

    schedule = []
    for i in range(num_years):
        schedule.append({
            "year": int(years[i]),
            "annual_rent": float(projected_annual[i]),
            "monthly_rent": float(projected_monthly[i]),
            "escalation_percent": rate,
        })

    discrepancies = []
    if stated_schedule:
        stated_annual = np.array([s["annual_rent"] for s in stated_schedule], dtype=np.float64)
        diff = np.abs(stated_annual[:num_years] - projected_annual[:len(stated_schedule)])
        mismatch_indices = np.where(diff > _TOLERANCE)[0]
        for idx in mismatch_indices:
            discrepancies.append({
                "year": int(stated_schedule[idx]["year"]),
                "stated_annual_rent": float(stated_annual[idx]),
                "projected_annual_rent": float(projected_annual[idx]),
                "difference": float(diff[idx]),
            })

    return {
        "is_valid": len(discrepancies) == 0,
        "discrepancies": discrepancies,
        "projected_schedule": schedule,
    }
