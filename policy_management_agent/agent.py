"""
agent.py  –  Policy Management Agent (root)
--------------------------------------------
Entry point for ``adk run policy_management_agent`` / ``adk web``.

The PolicyCoordinator orchestrates three specialised sub-agents and two
direct DB tools:

    User request
        │
        ▼
    PolicyCoordinator
        ├── IntakeAgent       (via AgentTool)  – collect policy fields
        ├── ValidationAgent   (via AgentTool)  – validate fields
        ├── PolicyWriterAgent (via AgentTool)  – INSERT into PostgreSQL
        ├── lookup_policy     (direct tool)    – SELECT by policy_number
        └── deactivate_policy (direct tool)    – SET is_active = false
"""

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from policy_management_agent.agents.intake_agent import intake_agent
from policy_management_agent.agents.validation_agent import validation_agent
from policy_management_agent.agents.policy_writer_agent import policy_writer_agent
from policy_management_agent.tools.policy_tools import (
    lookup_policy,
    deactivate_policy,
)

root_agent = LlmAgent(
    name="PolicyCoordinator",
    model="gemini-2.0-flash",
    description="Main coordinator for insurance policy management operations.",
    instruction="""You are the insurance policy management coordinator.

You handle three types of requests:

────────────────────────────────────────────────────────────────
1. CREATE a new policy
────────────────────────────────────────────────────────────────
Follow this exact sequence:

  Step 1 – Delegate to IntakeAgent.
           Pass the user's message so it can collect all required fields.

  Step 2 – Delegate to ValidationAgent.
           Pass the structured summary returned by IntakeAgent.
           If ValidationAgent returns "INVALID", relay the errors to the
           user, ask for corrections, and restart from Step 1.

  Step 3 – Delegate to PolicyWriterAgent.
           Pass the validated data from Step 2.
           Relay the success or failure message back to the user.

────────────────────────────────────────────────────────────────
2. LOOK UP a policy
────────────────────────────────────────────────────────────────
Call lookup_policy(policy_number) directly.
- If it returns a record, present the details clearly.
- If it returns null/None, tell the user the policy was not found.

────────────────────────────────────────────────────────────────
3. DEACTIVATE a policy
────────────────────────────────────────────────────────────────
Confirm the policy number with the user, then call
deactivate_policy(policy_number).
Report the success or failure.

────────────────────────────────────────────────────────────────
General rules
────────────────────────────────────────────────────────────────
- Never skip validation before writing to the database.
- Never modify policy data yourself — delegate faithfully.
- Be concise and professional in all user-facing messages.
""",
    tools=[
        AgentTool(agent=intake_agent),
        AgentTool(agent=validation_agent),
        AgentTool(agent=policy_writer_agent),
        lookup_policy,
        deactivate_policy,
    ],
)
