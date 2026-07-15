from dataclasses import dataclass, field

from src.extraction.schemas import LeaseTerms
from src.compliance.rules import RULES


@dataclass
class ComplianceFlag:
    rule_id: str
    rule_name: str
    risk_level: str
    description: str
    clause_text: str | None = None


@dataclass
class ComplianceReport:
    document_id: str
    overall_risk_level: str
    flags: list[ComplianceFlag] = field(default_factory=list)
    summary: str = ""


RISK_WEIGHTS = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def run_compliance_check(document_id: str, lease_terms: LeaseTerms) -> ComplianceReport:
    flags: list[ComplianceFlag] = []

    for rule in RULES:
        violation = rule.check_fn(lease_terms)
        if violation:
            flags.append(ComplianceFlag(
                rule_id=rule.rule_id,
                rule_name=rule.name,
                risk_level=rule.risk_level,
                description=violation,
            ))

    if flags:
        max_risk = max(flags, key=lambda f: RISK_WEIGHTS.get(f.risk_level, 0)).risk_level
        overall = max_risk
    else:
        overall = "low"

    high_count = sum(1 for f in flags if f.risk_level in ("high", "critical"))
    flag_count = len(flags)

    if flag_count == 0:
        summary = "All compliance checks passed."
    else:
        summary = (
            f"Found {flag_count} compliance issue(s), "
            f"{high_count} of which are high/critical risk. "
            f"Overall risk level: {overall.upper()}."
        )

    return ComplianceReport(
        document_id=document_id,
        overall_risk_level=overall,
        flags=flags,
        summary=summary,
    )
