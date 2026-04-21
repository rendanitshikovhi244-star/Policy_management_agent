"""
api/app.py
----------
FastAPI REST interface for the Policy Management Agent.

Endpoints
---------
GET  /plans                     — list all plans (optionally filter by coverage_type)
GET  /plans/{plan_id}           — get a single plan
POST /policies                  — create a policy via the full 3-stage pipeline
GET  /policies/{policy_number}  — look up a policy
DELETE /policies/{policy_number} — deactivate a policy

Run with:
    uvicorn api.app:app --reload --port 8080
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parent.parent / ".env")

# Import after env is loaded so DATABASE_URL / HF vars are present
from policy_management_agent import configure  # noqa: E402

configure()

from policy_management_agent.agent import policy_management_agent  # noqa: E402
from policy_management_agent.tools.policy_tools import (  # noqa: E402
    deactivate_policy,
    get_available_plans,
    lookup_policy,
)


# ---------------------------------------------------------------------------
# Lifespan — nothing to tear down yet, but keeps the pattern clean
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Policy Management API",
    description="REST interface for the insurance policy management agent.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreatePolicyRequest(BaseModel):
    message: str = Field(
        description=(
            "Natural-language request describing the policy to create. "
            "Include the plan ID, holder name, start date and end date. "
            "Example: 'Create an AUTO-STD policy for Jane Smith from 2026-05-01 to 2027-05-01'"
        )
    )


class CreatePolicyResponse(BaseModel):
    status: str
    policy_number: str | None = None
    error: str | None = None
    session_state: dict[str, Any] = Field(default_factory=dict)


class PolicyResponse(BaseModel):
    status: str
    policy_number: str
    is_active: bool
    coverage_limit: float
    deductible: float
    covered_claim_types: list[str]


class DeactivateResponse(BaseModel):
    success: bool
    policy_number: str | None = None
    error: str | None = None


class PlanResponse(BaseModel):
    plan_id: str
    coverage_type: str
    plan_name: str
    monthly_premium: float
    coverage_limit: float
    deductible: float
    description: str


class PlansResponse(BaseModel):
    status: str
    plans: list[PlanResponse]
    count: int


# ---------------------------------------------------------------------------
# Routes — catalog
# ---------------------------------------------------------------------------


@app.get(
    "/plans",
    response_model=PlansResponse,
    summary="List available insurance plans",
    tags=["Catalog"],
)
async def list_plans(
    coverage_type: str | None = Query(
        default=None,
        description="Filter by coverage type: auto | health | home | life | property | liability",
    ),
):
    """Return all available plans, optionally filtered by *coverage_type*."""
    result = await get_available_plans(coverage_type)
    if result.get("status") != "success":
        raise HTTPException(status_code=500, detail="Failed to fetch plans")
    return result


@app.get(
    "/plans/{plan_id}",
    response_model=PlanResponse,
    summary="Get a single plan by ID",
    tags=["Catalog"],
)
async def get_plan(plan_id: str):
    """Return details for a specific plan (e.g. ``AUTO-STD``)."""
    result = await get_available_plans()
    plans = {p["plan_id"]: p for p in result.get("plans", [])}
    plan = plans.get(plan_id.upper())
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    return plan


# ---------------------------------------------------------------------------
# Routes — policies
# ---------------------------------------------------------------------------


@app.post(
    "/policies",
    response_model=CreatePolicyResponse,
    status_code=201,
    summary="Create a new policy via the agent pipeline",
    tags=["Policies"],
)
async def create_policy_endpoint(body: CreatePolicyRequest):
    """
    Run the full 3-stage pipeline (IntakeAgent → ValidationAgent →
    PolicyWriterAgent) for the given natural-language *message*.

    Returns the write result and the full final session state for
    inspection / debugging.
    """
    state = await policy_management_agent.process_policy(body.message)

    write_result = state.get("policy_write_result", {})
    if isinstance(write_result, str):
        import json
        try:
            write_result = json.loads(write_result)
        except Exception:
            write_result = {}

    validation_result = state.get("policy_validation", {})
    if isinstance(validation_result, str):
        import json
        try:
            validation_result = json.loads(validation_result)
        except Exception:
            validation_result = {}

    # Pipeline wrote successfully
    if write_result.get("status") == "created":
        return CreatePolicyResponse(
            status="created",
            policy_number=write_result.get("policy_number"),
            session_state=state,
        )

    # Validation failed
    if validation_result.get("verdict") == "INVALID":
        errors = validation_result.get("errors", [])
        return CreatePolicyResponse(
            status="invalid",
            error=str(errors),
            session_state=state,
        )

    # Write error
    if write_result.get("status") == "error":
        return CreatePolicyResponse(
            status="error",
            error=write_result.get("error"),
            session_state=state,
        )

    # Unknown / pipeline incomplete
    return CreatePolicyResponse(status="unknown", session_state=state)


@app.get(
    "/policies/{policy_number}",
    response_model=PolicyResponse,
    summary="Look up a policy by policy number",
    tags=["Policies"],
)
async def get_policy(policy_number: str):
    """Return the full record for *policy_number*, or 404 if not found."""
    result = await lookup_policy(policy_number)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Policy '{policy_number}' not found"
        )
    return result


@app.delete(
    "/policies/{policy_number}",
    response_model=DeactivateResponse,
    summary="Deactivate a policy",
    tags=["Policies"],
)
async def deactivate_policy_endpoint(policy_number: str):
    """Set ``is_active = false`` on the given policy."""
    result = await deactivate_policy(policy_number)
    if not result.get("success"):
        raise HTTPException(
            status_code=404, detail=result.get("error", "Policy not found")
        )
    return result
