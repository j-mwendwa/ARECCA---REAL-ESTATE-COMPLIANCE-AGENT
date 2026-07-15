from dataclasses import dataclass, field
from typing import Callable

from src.extraction.schemas import LeaseTerms


@dataclass
class ComplianceRule:
    rule_id: str
    name: str
    description: str
    risk_level: str
    check_fn: Callable[[LeaseTerms], str | None]


RULES: list[ComplianceRule] = []


def _check_late_fee_cap(terms: LeaseTerms) -> str | None:
    if terms.late_fee_amount is not None:
        if terms.late_fee_is_percentage and terms.late_fee_amount > 5:
            return (
                f"Late fee of {terms.late_fee_amount}% exceeds typical 5% cap. "
                "May be illegal under state law."
            )
        if not terms.late_fee_is_percentage and terms.base_rent_monthly:
            fee_pct = (terms.late_fee_amount / terms.base_rent_monthly) * 100
            if fee_pct > 5:
                return (
                    f"Late fee of ${terms.late_fee_amount:.2f} ({fee_pct:.1f}% of rent) "
                    "exceeds typical 5% cap."
                )
    return None


def _check_grace_period(terms: LeaseTerms) -> str | None:
    if terms.grace_period_days is None or terms.grace_period_days < 3:
        return (
            f"Grace period of {terms.grace_period_days or 0} days is too short. "
            "Minimum 3-day grace period recommended."
        )
    return None


def _check_security_deposit_cap(terms: LeaseTerms) -> str | None:
    if terms.security_deposit is not None and terms.base_rent_monthly:
        deposit_months = terms.security_deposit / terms.base_rent_monthly
        if deposit_months > 2:
            return (
                f"Security deposit of ${terms.security_deposit:.2f} "
                f"({deposit_months:.1f}x monthly rent) exceeds 2-month cap."
            )
    return None


def _check_rent_escalation_disclosure(terms: LeaseTerms) -> str | None:
    if terms.escalation_type and terms.escalation_type != "none":
        if not terms.escalation_rate:
            return "Rent escalation is referenced but no escalation rate is specified."
        if terms.escalation_frequency_months is None:
            return "Rent escalation is specified but frequency is not disclosed."
    return None


def _check_no_retaliatory_clause() -> str | None:
    return None


def _check_habitability_waiver() -> str | None:
    return None


RULES = [
    ComplianceRule("LATE_FEE_CAP", "Late Fee Cap Check",
                   "Verifies late fees do not exceed legal limits", "high", _check_late_fee_cap),
    ComplianceRule("GRACE_PERIOD", "Grace Period Check",
                   "Verifies minimum grace period exists", "medium", _check_grace_period),
    ComplianceRule("DEPOSIT_CAP", "Security Deposit Cap",
                   "Verifies deposit does not exceed legal limits", "high", _check_security_deposit_cap),
    ComplianceRule("ESCALATION_DISCLOSURE", "Rent Escalation Disclosure",
                   "Verifies escalation terms are fully disclosed", "medium", _check_rent_escalation_disclosure),
]
