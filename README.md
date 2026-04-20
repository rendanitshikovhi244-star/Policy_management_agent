# Policy Management Agent

A Google ADK multi-agent system for managing insurance policies backed by a local PostgreSQL database (Docker). Designed to integrate with the claims-triage system via a shared `lookup_policy` contract.

---

## Architecture

```
User request
    │
    ▼
PolicyCoordinator  (root agent)
    ├── IntakeAgent        ← collects policy fields conversationally
    ├── ValidationAgent    ← validates dates, limits, coverage types
    ├── PolicyWriterAgent  ← writes validated policy to PostgreSQL
    ├── lookup_policy()    ← SELECT by policy_number (direct tool)
    └── deactivate_policy() ← SET is_active = false (direct tool)
```

Sub-agents are wired into the coordinator via `AgentTool` so the coordinator can delegate to them like calling a function.

---

## Agents

| Agent | Responsibility |
|---|---|
| **IntakeAgent** | Conversationally collects all seven required policy fields. Generates a `policy_number` if the user does not provide one. |
| **ValidationAgent** | Checks business rules (date ordering, positive limits, deductible < coverage, allowed coverage types, no duplicates). Returns `VALID` or `INVALID` with a per-field error list. |
| **PolicyWriterAgent** | Receives validated data from the coordinator and calls `create_policy()` to INSERT into PostgreSQL. Reports success or failure. |

### Policy creation flow

```
IntakeAgent → ValidationAgent → PolicyWriterAgent
                    ↑                 |
                    └─ INVALID: re-collect from user
```

---

## Tools

All three tools live in `policy_management_agent/tools/policy_tools.py` and use an `asyncpg` connection pool.

### `create_policy(...)`

Inserts a new policy row.

```python
await create_policy(
    policy_number="POL-2024-001",
    holder_name="Jane Smith",
    coverage_limit=50_000.0,
    deductible=500.0,
    covered_types=["auto", "health"],
    start_date="2024-01-01",
    end_date="2025-01-01",
)
# → {"success": True, "policy_number": "POL-2024-001"}
# → {"success": False, "error": "..."} on failure
```

### `lookup_policy(policy_number)`

Returns a single policy record or `None`.

```python
await lookup_policy("POL-2024-001")
# → {
#     "status":              "success",
#     "policy_number":       "POL-2024-001",
#     "is_active":           True,
#     "coverage_limit":      50000.0,
#     "deductible":          500.0,
#     "covered_claim_types": ["auto", "health"],
#   }
# → None  (policy not found)
```

> **Claims-triage compatibility** — The return shape is identical to the in-memory stub in the claims-triage system (`_POLICY_DB.get(policy_number)`). Swapping the stub for a live DB call requires changing one line in the claims agent's `policy_tools.py` — no other changes needed.

### `deactivate_policy(policy_number)`

Sets `is_active = false` on an existing policy.

```python
await deactivate_policy("POL-2024-001")
# → {"success": True,  "policy_number": "POL-2024-001"}
# → {"success": False, "error": "Policy 'X' not found."}
```

---

## Database schema

```sql
CREATE TABLE policies (
    policy_number   TEXT PRIMARY KEY,
    holder_name     TEXT           NOT NULL,
    is_active       BOOLEAN        NOT NULL DEFAULT TRUE,
    coverage_limit  NUMERIC(15, 2) NOT NULL,
    deductible      NUMERIC(15, 2) NOT NULL,
    covered_types   TEXT[]         NOT NULL,
    start_date      DATE           NOT NULL,
    end_date        DATE           NOT NULL
);
```

Managed by PostgreSQL 16 running in Docker. The schema is applied automatically on first container start via `docker-entrypoint-initdb.d`.

---

## Project structure

```
Policy_management_agent/
├── .env                              ← credentials (do not commit)
├── .env.example                      ← template
├── docker-compose.yml
├── schema.sql
├── requirements.txt
└── policy_management_agent/
    ├── agent.py                      ← root_agent (PolicyCoordinator)
    ├── agents/
    │   ├── intake_agent.py
    │   ├── validation_agent.py
    │   └── policy_writer_agent.py
    └── tools/
        └── policy_tools.py
```

---

## Quick start

### Prerequisites

- Python 3.11+
- Docker Desktop (or Docker Engine)
- A [HuggingFace](https://huggingface.co/settings/tokens) API key

### 1. Start Postgres

```bash
docker compose up -d
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set your HUGGINGFACE_API_KEY
```

`.env` values:

| Variable | Default | Description |
|---|---|---|
| `HUGGINGFACE_API_KEY` | *(required)* | HuggingFace API key |
| `HF_MODEL` | `huggingface/MiniMaxAI/MiniMax-M2.7` | Model used by all agents |
| `DATABASE_URL` | `postgresql+asyncpg://insurance_user:insurance_pass@localhost:5432/insurance` | asyncpg connection string |

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the agent

```bash
# Interactive CLI
adk run policy_management_agent

# Browser UI at http://localhost:8000
adk web
```

---

## Example conversations

**Create a policy**
```
You:   I need to create a new auto and health policy for John Doe.
Agent: Sure! What coverage limit would you like?
You:   $100,000 with a $1,000 deductible, starting today for one year.
Agent: Here is the policy I will create: ...
       Policy POL-2026-001 has been created successfully.
```

**Look up a policy**
```
You:   Look up policy POL-2026-001
Agent: Policy POL-2026-001 — John Doe
       Status: Active | Limit: $100,000 | Deductible: $1,000
       Coverage: auto, health | 2026-04-20 → 2027-04-20
```

**Deactivate a policy**
```
You:   Please deactivate POL-2026-001
Agent: Policy POL-2026-001 has been deactivated.
```

---

## Validation rules

| Field | Rule |
|---|---|
| `coverage_limit` | Must be > 0 |
| `deductible` | Must be > 0 and < `coverage_limit` |
| `covered_types` | Non-empty; each value in `auto`, `health`, `home`, `life`, `property`, `liability`; no duplicates |
| `start_date` / `end_date` | Valid `YYYY-MM-DD`; `end_date` must be after `start_date` |

---

## Integration with claims-triage

The claims-triage agent stubs `lookup_policy` with an in-memory dict:

```python
# claims_triage/policy_tools.py  (stub)
_POLICY_DB: dict[str, dict] = { ... }

def lookup_policy(policy_number: str) -> dict | None:
    return _POLICY_DB.get(policy_number)
```

To point it at the real database, replace only the function body:

```python
# claims_triage/policy_tools.py  (live DB)
from policy_management_agent.tools.policy_tools import lookup_policy
```

Parameters (`policy_number: str`) and return shape (`dict | None` with the six keys above) are unchanged.
