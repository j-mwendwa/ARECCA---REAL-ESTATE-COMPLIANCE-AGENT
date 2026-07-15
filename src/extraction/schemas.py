from datetime import date
from pydantic import BaseModel, Field


class RentSchedule(BaseModel):
    year: int = Field(description="Lease year number (1-based)")
    annual_rent: float = Field(description="Annual rent amount in dollars")
    monthly_rent: float = Field(description="Monthly rent amount in dollars")
    escalation_percent: float | None = Field(
        default=None, description="Escalation percentage applied for this year"
    )
    notes: str | None = Field(default=None, description="Any notes about this year's rent")


class LeaseTerms(BaseModel):
    lessor: str | None = Field(default=None, description="Landlord/lessor name")
    lessee: str | None = Field(default=None, description="Tenant/lessee name")
    property_address: str | None = Field(default=None, description="Leased property address")
    lease_start_date: date | None = Field(default=None, description="Lease commencement date")
    lease_end_date: date | None = Field(default=None, description="Lease expiration date")
    lease_term_months: int | None = Field(default=None, description="Total lease term in months")

    base_rent_monthly: float | None = Field(default=None, description="Initial monthly base rent")
    base_rent_annual: float | None = Field(default=None, description="Initial annual base rent")
    security_deposit: float | None = Field(default=None, description="Security deposit amount")

    escalation_type: str | None = Field(
        default=None,
        description="Type of rent escalation: fixed_percentage, cpi_based, fixed_amount, or none",
    )
    escalation_frequency_months: int | None = Field(
        default=None, description="How often escalation occurs in months"
    )
    escalation_rate: float | None = Field(
        default=None, description="Escalation percentage rate (e.g., 3.0 for 3%)"
    )
    escalation_cap: float | None = Field(
        default=None, description="Maximum escalation percentage cap"
    )

    late_fee_amount: float | None = Field(default=None, description="Late fee amount or percentage")
    late_fee_is_percentage: bool | None = Field(
        default=None, description="Whether the late fee is a percentage of rent"
    )
    grace_period_days: int | None = Field(default=None, description="Grace period in days before late fee applies")
    late_fee_after_grace_days: int | None = Field(
        default=None, description="Additional days before further late fee applies"
    )

    rent_schedule: list[RentSchedule] | None = Field(
        default=None, description="Projected rent over the lease term based on escalation formula"
    )


class ExtractionResult(BaseModel):
    lease_terms: LeaseTerms
    raw_clauses: dict[str, str] = Field(
        description="Map of section title to raw text for each extracted clause"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0, default=0.0, description="Overall confidence in the extraction"
    )
