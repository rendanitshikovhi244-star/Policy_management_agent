"""
conversational_agent.py
-----------------------
PolicyAssistant — the front-door conversational agent.
Model, description, and instruction are sourced from agent_configs.py.

It is the root_agent exposed to adk web and adk run.
The batch CLI (main.py) bypasses this agent and calls the pipeline directly.
"""
from __future__ import annotations

from google.adk.agents import LlmAgent

from ..configs import AGENT_CONFIGS, agent_start_callback
from ..tools.pipeline_runner_tool import submit_policy
from ..tools.policy_tools import deactivate_policy, lookup_policy

_cfg = AGENT_CONFIGS["PolicyAssistant"]

conversational_agent = LlmAgent(
    name="PolicyAssistant",
    model=_cfg.model,
    description=_cfg.description,
    instruction=_cfg.instruction,
    tools=[
        submit_policy,
        lookup_policy,
        deactivate_policy,
    ],
    before_agent_callback=agent_start_callback,
)
