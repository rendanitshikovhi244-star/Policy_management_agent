"""
agent.py
--------
PolicyManagementAgent — orchestrates the full policy creation pipeline
without relying on ADK's SequentialAgent wrapper.

Each stage is driven by a dedicated Runner for the sub-agent, sharing the
same session state so outputs written via output_key are visible downstream.

Pipeline order:
  1. IntakeAgent        — collect policy fields from user input
  2. ValidationAgent    — validate all fields, return VALID/INVALID verdict
  3. PolicyWriterAgent  — INSERT into PostgreSQL (only if VALID)

root_agent is still exposed for adk web / adk run entry point.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .sub_agents import (
    intake_agent,
    policy_writer_agent,
    validation_agent,
)
from .sub_agents.conversational_agent import conversational_agent

logger = logging.getLogger("policy_agent.pipeline")


class PolicyManagementAgent:
    """
    Orchestrates the insurance policy creation pipeline through direct async
    calls to each sub-agent.

    Each sub-agent shares the same session_service and session_id, so outputs
    written via output_key are visible to every downstream agent.
    """

    APP_NAME = "policy_management"

    def __init__(self) -> None:
        self.session_service = InMemorySessionService()

        # Pipeline sub-agents
        self.intake_agent = intake_agent
        self.validation_agent = validation_agent
        self.policy_writer_agent = policy_writer_agent

        # Front-door conversational agent (adk web / adk run entry point)
        self._root_agent = conversational_agent

    # -----------------------------------------------------------------------
    # Internal runner helper
    # -----------------------------------------------------------------------

    async def _run_agent(
        self,
        agent: LlmAgent,
        session_id: str,
        user_id: str,
        message: str,
    ) -> str | None:
        """
        Create a Runner for *agent* and drive it with *message*.
        Returns the text of the final response event, or None.
        """
        runner = Runner(
            agent=agent,
            app_name=self.APP_NAME,
            session_service=self.session_service,
        )
        content = types.Content(role="user", parts=[types.Part(text=message)])
        final_text: str | None = None

        logger.info("[Pipeline] %-26s → running", agent.name)
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        logger.info(
                            "[Pipeline] %-26s → TOOL CALL  : %s(%s)",
                            event.author,
                            part.function_call.name,
                            str(part.function_call.args)[:120].replace("\n", " "),
                        )
                    elif hasattr(part, "function_response") and part.function_response:
                        logger.info(
                            "[Pipeline] %-26s ← TOOL RESULT: %s → %s",
                            event.author,
                            part.function_response.name,
                            str(part.function_response.response)[:120].replace("\n", " "),
                        )
                    elif hasattr(part, "text") and part.text and part.text.strip():
                        logger.info(
                            "[Pipeline] %-26s   OUTPUT     : %s",
                            event.author,
                            part.text[:200].replace("\n", " "),
                        )
            if event.is_final_response() and event.content:
                final_text = event.content.parts[0].text.strip()

        logger.info("[Pipeline] %-26s   complete", agent.name)
        return final_text

    # -----------------------------------------------------------------------
    # Pipeline entry point
    # -----------------------------------------------------------------------

    async def process_policy(
        self,
        policy_input: str,
        *,
        session_id: str | None = None,
        user_id: str = "system",
    ) -> dict[str, Any]:
        """
        Run the full policy creation pipeline and return the final session
        state dict.

        Stages:
          1. IntakeAgent      — collect and structure policy fields
          2. ValidationAgent  — validate all fields (VALID / INVALID)
          3. PolicyWriterAgent — INSERT into PostgreSQL (only when VALID)
        """
        session_id = session_id or f"policy_{uuid.uuid4().hex[:12]}"
        await self.session_service.create_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

        logger.info("[Policy] Starting pipeline  session=%s", session_id)

        # Stage 1 — Intake
        await self._run_agent(self.intake_agent, session_id, user_id, policy_input)

        # Stage 2 — Validation
        await self._run_agent(
            self.validation_agent,
            session_id,
            user_id,
            "Validate the collected policy data.",
        )

        # Stage 3 — Write (only if validation passed)
        session = await self.session_service.get_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        validation_output = (session.state or {}).get("policy_validation", "")
        try:
            verdict = (
                json.loads(validation_output)
                if isinstance(validation_output, str)
                else validation_output
            ).get("verdict", "INVALID")
        except Exception:
            verdict = "INVALID"

        if verdict == "VALID":
            await self._run_agent(
                self.policy_writer_agent,
                session_id,
                user_id,
                "Write the validated policy to the database.",
            )
        else:
            logger.info("[Policy] Validation INVALID — skipping write stage")

        logger.info("[Policy] Pipeline complete  session=%s", session_id)

        session = await self.session_service.get_session(
            app_name=self.APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        return dict(session.state) if session else {}


# ---------------------------------------------------------------------------
# Module-level instances
# ---------------------------------------------------------------------------

# Shared instance used by pipeline_runner_tool and main.py CLI
policy_management_agent = PolicyManagementAgent()

# root_agent is the adk web / adk run entry point — the conversational front-door
root_agent = policy_management_agent._root_agent

