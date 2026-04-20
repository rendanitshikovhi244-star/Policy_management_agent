"""
main.py
-------
CLI entrypoint for the Policy Management Multi-Agent System.

Usage:
    # Create a policy from a JSON file
    python main.py sample_policies/policy_auto_001.json

    # Create a policy from a JSON string
    python main.py '{"holder_name": "Jane Smith", "coverage_limit": 50000, ...}'

    # Create a policy from free-text
    python main.py "I need an auto policy for John Doe, $100k coverage, $1k deductible."

The pipeline runs synchronously and prints a structured result to stdout.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Ensure Unicode output works correctly on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from policy_management_agent.configs.logging_config import configure as _configure_logging
_configure_logging()

from policy_management_agent.agent import policy_management_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_policy_input(arg: str) -> str:
    """
    Accept a file path, a JSON string, or a plain-text description.
    Returns the raw string sent as the user message to the pipeline.
    """
    path = Path(arg)
    if path.exists() and path.suffix == ".json":
        return path.read_text(encoding="utf-8")
    return arg


def _pretty_print_result(state: dict) -> None:
    """Print a concise summary of the pipeline result."""
    write_result = state.get("policy_write_result")
    validation = state.get("policy_validation")
    intake = state.get("policy_intake")

    print("\n" + "=" * 60)
    print("POLICY MANAGEMENT RESULT")
    print("=" * 60)

    if write_result:
        try:
            data = json.loads(write_result) if isinstance(write_result, str) else write_result
            if data.get("status") == "created":
                print(f"Status        : CREATED")
                print(f"Policy Number : {data.get('policy_number', 'N/A')}")
            else:
                print(f"Status        : ERROR")
                print(f"Error         : {data.get('error', 'N/A')}")
        except Exception:
            print(f"Write result  : {write_result}")

    elif validation:
        try:
            data = json.loads(validation) if isinstance(validation, str) else validation
            verdict = data.get("verdict", "UNKNOWN")
            print(f"Status        : VALIDATION {verdict}")
            if verdict == "INVALID":
                print("Errors:")
                for err in data.get("errors", []):
                    print(f"  • {err['field']}: {err['message']}")
        except Exception:
            print(f"Validation    : {validation}")

    elif intake:
        print("Status        : INTAKE ONLY (validation did not run)")
        print(f"Intake        : {intake}")

    else:
        print("[WARNING] No output found in session state.")
        print("Session state keys:", list(state.keys()))

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Main pipeline runner
# ---------------------------------------------------------------------------


async def run_pipeline(policy_input: str) -> dict:
    """Execute the full policy creation pipeline for a single input."""
    session_id = f"policy_{abs(hash(policy_input)) % 10 ** 9}"

    print(f"\nRunning Policy Management Pipeline...")
    print(f"Session ID: {session_id}\n")

    return await policy_management_agent.process_policy(
        policy_input=policy_input,
        session_id=session_id,
        user_id="policy_processor",
    )


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "  python main.py <path/to/policy.json>\n"
            "  python main.py '<json string>'\n"
            "  python main.py 'Free-text policy description...'\n"
        )
        sys.exit(1)

    raw_input = _load_policy_input(sys.argv[1])
    final_state = asyncio.run(run_pipeline(raw_input))
    _pretty_print_result(final_state)


if __name__ == "__main__":
    main()
