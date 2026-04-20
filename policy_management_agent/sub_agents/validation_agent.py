"""
validation_agent.py
-------------------
ValidationAgent — second stage in the policy creation pipeline.
Model, description, and instruction are sourced from agent_configs.py.
"""
from __future__ import annotations

from google.adk.agents import LlmAgent

from ..configs import AGENT_CONFIGS, agent_start_callback

_cfg = AGENT_CONFIGS["ValidationAgent"]

validation_agent = LlmAgent(
    name="ValidationAgent",
    model=_cfg.model,
    description=_cfg.description,
    instruction=_cfg.instruction,
    output_key="policy_validation",
    before_agent_callback=agent_start_callback,
)
