from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


class PolicyIntake(BaseModel):
    """Structured policy data produced by IntakeAgent."""

    policy_number: str = Field(description="Unique policy identifier, e.g. POL-2026-001")
    holder_name: str = Field(description="Full legal name of the policy holder")
    coverage_limit: float = Field(description="Maximum payout in USD", gt=0)
    deductible: float = Field(description="Deductible amount in USD", gt=0)
    covered_types: List[
        Literal["auto", "health", "home", "life", "property", "liability"]
    ] = Field(description="Coverage categories")
    start_date: str = Field(description="Policy start date in YYYY-MM-DD format")
    end_date: str = Field(description="Policy end date in YYYY-MM-DD format")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class ValidationError(BaseModel):
    field: str
    message: str


class ValidationResult(BaseModel):
    """Verdict produced by ValidationAgent."""

    verdict: Literal["VALID", "INVALID"]
    # Present when verdict == "VALID"
    policy_number: Optional[str] = None
    holder_name: Optional[str] = None
    coverage_limit: Optional[float] = None
    deductible: Optional[float] = None
    covered_types: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    # Present when verdict == "INVALID"
    errors: Optional[List[ValidationError]] = None


# ---------------------------------------------------------------------------
# Write result
# ---------------------------------------------------------------------------


class PolicyWriteResult(BaseModel):
    """Outcome produced by PolicyWriterAgent."""

    status: Literal["created", "error"]
    policy_number: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# DB record (mirrors the lookup_policy return shape)
# ---------------------------------------------------------------------------


class PolicyRecord(BaseModel):
    """Full policy record returned by lookup_policy."""

    status: Literal["success"]
    policy_number: str
    is_active: bool
    coverage_limit: float
    deductible: float
    covered_claim_types: List[str]
