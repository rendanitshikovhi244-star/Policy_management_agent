"""
policy_tools.py
---------------
Async PostgreSQL tools for insurance policy management.

Return contract for lookup_policy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The return shape is intentionally identical to the stub used in the
claims-triage system:

    {
        "policy_number":  str,
        "holder_name":    str,
        "is_active":      bool,
        "coverage_limit": float,
        "deductible":     float,
        "covered_types":  list[str],
        "start_date":     str,   # "YYYY-MM-DD"
        "end_date":       str,   # "YYYY-MM-DD"
    }

or ``None`` when the policy is not found.

The claims agent's policy_tools.py stub looks like::

    _POLICY_DB: dict[str, dict] = { ... }

    def lookup_policy(policy_number: str) -> dict | None:
        return _POLICY_DB.get(policy_number)

Replacing that one function body with a call to the async version here
(pointing at the real DB) is the only change required — parameters and
return shape are identical.
"""

from __future__ import annotations

import os
from typing import Any

import asyncpg
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Connection pool — lazily initialised, shared across all tool calls
# ---------------------------------------------------------------------------

_pool: asyncpg.Pool | None = None


def _dsn() -> str:
    """Return an asyncpg-compatible DSN by stripping the SQLAlchemy dialect prefix."""
    raw = os.environ["DATABASE_URL"]
    # SQLAlchemy uses postgresql+asyncpg://; asyncpg expects postgresql://
    return raw.replace("postgresql+asyncpg://", "postgresql://")


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(_dsn(), min_size=1, max_size=5)
    return _pool


# ---------------------------------------------------------------------------
# Tool: create_policy
# ---------------------------------------------------------------------------


async def create_policy(
    policy_number: str,
    holder_name: str,
    coverage_limit: float,
    deductible: float,
    covered_types: list[str],
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Insert a new insurance policy into the database.

    Args:
        policy_number: Unique policy identifier, e.g. ``POL-2024-001``.
        holder_name: Full name of the policy holder.
        coverage_limit: Maximum coverage amount in dollars (must be > 0).
        deductible: Deductible amount in dollars (must be > 0).
        covered_types: Non-empty list of coverage categories, e.g.
            ``["auto", "health"]``.
        start_date: Policy start date in ``YYYY-MM-DD`` format.
        end_date: Policy end date in ``YYYY-MM-DD`` format (must be after
            *start_date*).

    Returns:
        ``{"success": True, "policy_number": policy_number}`` on success, or
        ``{"success": False, "error": "<message>"}`` on failure.
    """
    from datetime import date

    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        return {"success": False, "error": f"Invalid date format: {exc}"}

    pool = await _get_pool()
    try:
        await pool.execute(
            """
            INSERT INTO policies (
                policy_number, holder_name, is_active,
                coverage_limit, deductible, covered_types,
                start_date, end_date
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            policy_number,
            holder_name,
            True,
            coverage_limit,
            deductible,
            covered_types,
            start,
            end,
        )
        return {"success": True, "policy_number": policy_number}
    except asyncpg.UniqueViolationError:
        return {
            "success": False,
            "error": f"Policy '{policy_number}' already exists.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: lookup_policy
# ---------------------------------------------------------------------------


async def lookup_policy(policy_number: str) -> dict[str, Any] | None:
    """Retrieve a policy record by its policy number.

    Return shape matches the claims-triage stub so the claims agent can
    replace its in-memory ``_POLICY_DB.get(policy_number)`` call with this
    function without any other code changes.

    Args:
        policy_number: The unique policy identifier to look up.

    Returns:
        A dict with keys ``policy_number``, ``holder_name``, ``is_active``,
        ``coverage_limit``, ``deductible``, ``covered_types``,
        ``start_date``, ``end_date`` — or ``None`` if not found.
    """
    pool = await _get_pool()
    row = await pool.fetchrow(
        "SELECT * FROM policies WHERE policy_number = $1",
        policy_number,
    )
    if row is None:
        return None
    return {
        "policy_number": row["policy_number"],
        "holder_name": row["holder_name"],
        "is_active": row["is_active"],
        "coverage_limit": float(row["coverage_limit"]),
        "deductible": float(row["deductible"]),
        "covered_types": list(row["covered_types"]),
        "start_date": row["start_date"].isoformat(),
        "end_date": row["end_date"].isoformat(),
    }


# ---------------------------------------------------------------------------
# Tool: deactivate_policy
# ---------------------------------------------------------------------------


async def deactivate_policy(policy_number: str) -> dict[str, Any]:
    """Set ``is_active = false`` for an existing policy.

    Args:
        policy_number: The unique policy identifier to deactivate.

    Returns:
        ``{"success": True, "policy_number": policy_number}`` when the policy
        was found and updated, or ``{"success": False, "error": "<message>"}``
        when the policy does not exist or the update failed.
    """
    pool = await _get_pool()
    try:
        result: str = await pool.execute(
            "UPDATE policies SET is_active = false WHERE policy_number = $1",
            policy_number,
        )
        # asyncpg returns a status string like "UPDATE 1"
        rows_affected = int(result.split()[-1])
        if rows_affected == 0:
            return {
                "success": False,
                "error": f"Policy '{policy_number}' not found.",
            }
        return {"success": True, "policy_number": policy_number}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "error": str(exc)}
