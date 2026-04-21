"""
policy_writer_agent.py
----------------------
PolicyWriterAgent — third stage in the policy creation pipeline.
Model, description, and instruction are sourced from agent_configs.py.
"""
from __future__ import annotations

from google.adk.agents import LlmAgent

from ..configs import AGENT_CONFIGS, agent_start_callback
from ..tools.policy_tools import create_policy, get_available_plans

_cfg = AGENT_CONFIGS["PolicyWriterAgent"]

policy_writer_agent = LlmAgent(
    name="PolicyWriterAgent",
    model=_cfg.model,
    description=_cfg.description,
    instruction=_cfg.instruction,
    tools=[get_available_plans, create_policy],
    output_key="policy_write_result",
    before_agent_callback=agent_start_callback,
)
