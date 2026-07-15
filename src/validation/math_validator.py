from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from src.config import cfg
from src.extraction.schemas import LeaseTerms


_validation_cfg = cfg.get("validation", {})
_DECIMALS = _validation_cfg.get("rounding_decimals", 2)
_TOLERANCE = Decimal(str(_validation_cfg.get("tolerance", 0.01)))


@dataclass
class ValidationResult:
    is_valid: bool = False
    discrepancies: list[dict[str, Any]] = field(default_factory=list)
    projected_schedule: list[dict[str, Any]] = field(default_factory=list)


def _round(val: float) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0." + "0" * _DECIMALS), rounding=ROUND_HALF_UP)


def validate_rent_escalation(lease_terms: LeaseTerms) -> ValidationResult:
    result = ValidationResult(projected_schedule=[])

    if not lease_terms.base_rent_monthly and not lease_terms.base_rent_annual:
        result.is_valid = True
        return result

    base_monthly = _round(lease_terms.base_rent_monthly or (lease_terms.base_rent_annual or 0) / 12)
    base_annual = base_monthly * 12
    escalation_rate = lease_terms.escalation_rate
    escalation_type = (lease_terms.escalation_type or "").lower()
    term_months = lease_terms.lease_term_months or 12

    if not escalation_rate or escalation_rate == 0 or escalation_type == "none":
        result.is_valid = True
        if term_months:
            for year in range(1, (term_months // 12) + 1):
                result.projected_schedule.append({
                    "year": year,
                    "annual_rent": float(base_annual),
                    "monthly_rent": float(base_monthly),
                    "escalation_percent": 0.0,
                })
        return result

    if escalation_type == "fixed_amount":
        annual_increase = Decimal(str(escalation_rate))
        for year in range(1, (term_months // 12) + 1):
            projected_annual = base_annual + (annual_increase * (year - 1))
            projected_monthly = projected_annual / 12
            result.projected_schedule.append({
                "year": year,
                "annual_rent": float(projected_annual),
                "monthly_rent": float(projected_monthly),
                "escalation_percent": float(annual_increase),
            })
    elif escalation_type in ("fixed_percentage", "cpi_based"):
        rate = Decimal(str(escalation_rate)) / 100
        cap = Decimal(str(lease_terms.escalation_cap)) / 100 if lease_terms.escalation_cap else None
        for year in range(1, (term_months // 12) + 1):
            if year == 1:
                projected_annual = base_annual
            else:
                increase = rate
                if cap:
                    increase = min(rate, cap)
                projected_annual = projected_annual * (Decimal("1") + increase)
            projected_monthly = projected_annual / 12
            result.projected_schedule.append({
                "year": year,
                "annual_rent": float(projected_annual),
                "monthly_rent": float(projected_monthly),
                "escalation_percent": escalation_rate,
            })
    else:
        result.is_valid = True
        return result

    if lease_terms.rent_schedule:
        for i, stated in enumerate(lease_terms.rent_schedule):
            if i < len(result.projected_schedule):
                projected = result.projected_schedule[i]
                stated_annual = _round(stated.annual_rent)
                projected_annual = _round(projected["annual_rent"])
                diff = abs(stated_annual - projected_annual)
                if diff > _TOLERANCE:
                    result.discrepancies.append({
                        "year": stated.year,
                        "stated_annual_rent": float(stated_annual),
                        "projected_annual_rent": float(projected_annual),
                        "difference": float(diff),
                        "type": "rent_mismatch",
                    })

    result.is_valid = len(result.discrepancies) == 0
    return result
