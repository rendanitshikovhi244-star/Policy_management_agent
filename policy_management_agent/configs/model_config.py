"""
model_config.py
---------------
Single model instance shared by all agents, sourced from HF_MODEL in .env.

To swap the model, change HF_MODEL in the root .env file.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.models.lite_llm import LiteLlm

# .env lives at the repo root
load_dotenv(Path(__file__).parent.parent.parent / ".env")

MODEL = LiteLlm(model=os.environ["HF_MODEL"])

# Kept for backward-compat — all point to the same instance
DEFAULT_MODEL = MODEL
MODEL_FAST = MODEL
MODEL_MID  = MODEL
MODEL_MAIN = MODEL
