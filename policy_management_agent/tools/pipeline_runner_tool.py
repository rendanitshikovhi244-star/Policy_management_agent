"""
pipeline_runner_tool.py
-----------------------
Tool used by PolicyAssistant (the conversational agent) to trigger the
internal policy creation pipeline.

The policy_management_agent (PolicyManagementAgent) is imported lazily
inside the function to avoid a circular import:
  agent.py  ←  conversational_agent  ←  this file  ←→ [lazy] agent.py
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

logger = logging.getLogger("policy_agent.pipeline")


# ---------------------------------------------------------------------------
# Tool: submit_policy
# ---------------------------------------------------------------------------


async def submit_policy(user_message: str) -> str:
    """
    Run the full policy creation pipeline (Intake → Validation → Write)
    for a user request and return a human-readable result string.

    Args:
        user_message: The user's policy creation request in free-text or as a
            JSON string containing partial or complete policy fields.

    Returns:
        A plain-text summary of the outcome — either the created policy number
        or a list of validation errors for the user to correct.
    """
    # Lazy import to avoid circular dependency
    from ..agent import policy_management_agent  # noqa: PLC0415

    session_id = f"policy_{uuid.uuid4().hex[:12]}"
    state = await policy_management_agent.process_policy(
        policy_input=user_message,
        session_id=session_id,
    )

    return _format_result(state)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_result(state: dict) -> str:
    """Convert pipeline session state to a human-readable summary string."""
    write_result = state.get("policy_write_result")
    validation = state.get("policy_validation")

    if write_result:
        import json as _json

        try:
            data = (
                _json.loads(write_result)
                if isinstance(write_result, str)
                else write_result
            )
            if data.get("status") == "created":
                return (
                    f"Policy {data['policy_number']} has been created successfully."
                )
            return f"Failed to create policy: {data.get('error', 'unknown error')}"
        except Exception:
            return str(write_result)

    if validation:
        import json as _json

        try:
            data = (
                _json.loads(validation)
                if isinstance(validation, str)
                else validation
            )
            if data.get("verdict") == "INVALID":
                errors = data.get("errors", [])
                lines = ["Validation failed — please correct the following:"]
                for err in errors:
                    lines.append(f"  • {err['field']}: {err['message']}")
                return "\n".join(lines)
        except Exception:
            pass

    return (
        "The policy pipeline did not produce a result. "
        "Please check your input and try again."
    )
