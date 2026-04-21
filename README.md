# Policy Management Agent

A Google ADK multi-agent system for managing insurance policies backed by a local PostgreSQL database (Docker). Customers can browse a product catalog, choose a plan, and create a policy in a single conversation. Designed to integrate with the claims-triage system via a shared `lookup_policy` contract.

---

## Architecture

```
User
  │
  ▼
PolicyAssistant  (root agent — conversational front-door)
  │   ├── get_available_plans()    ← show catalog / pricing to customer
  │   ├── submit_policy()          ← triggers the 3-stage pipeline below
  │   ├── lookup_policy()          ← SELECT by policy_number
  │   └── deactivate_policy()      ← SET is_active = false
  │
  └── Pipeline (via submit_policy)
        ├── IntakeAgent        ← collects plan_id + holder details
        ├── ValidationAgent    ← validates all fields, confirms plan exists
        └── PolicyWriterAgent  ← resolves plan details, writes to PostgreSQL
```

Each pipeline stage passes its output through ADK session state (`output_key`) so the next agent picks it up automatically.

---

## Agents

| Agent | Stage | Responsibility |
|---|---|---|
| **PolicyAssistant** | Front-door | Shows available plans, routes requests, calls pipeline via `submit_policy`, handles lookups and deactivations. |
| **IntakeAgent** | 1 | Collects `policy_number`, `holder_name`, `plan_id`, `start_date`, `end_date`. Outputs JSON to session state. |
| **ValidationAgent** | 2 | Validates all five fields; confirms `plan_id` is in the known catalog. Returns `VALID` or `INVALID` with per-field errors. |
| **PolicyWriterAgent** | 3 | Calls `get_available_plans()` to resolve plan details, then calls `create_policy()` to INSERT into PostgreSQL. |

### Policy creation flow

```
Customer picks a plan
        │
        ▼
PolicyAssistant → submit_policy()
                        │
              ┌─────────▼──────────┐
              │    IntakeAgent     │  output_key="policy_intake"
              └─────────┬──────────┘
                        │
              ┌─────────▼──────────┐
              │  ValidationAgent   │  output_key="policy_validation"
              └─────────┬──────────┘
                    VALID │ INVALID → error back to customer
              ┌─────────▼──────────┐
              │ PolicyWriterAgent  │  output_key="policy_write_result"
              └─────────┬──────────┘
                        │
               Policy created in DB
```

---

## Product catalog

18 pre-defined plans across 6 coverage types, 3 tiers each. Stored in the `insurance_plans` table and returned by `get_available_plans()`.

| Coverage type | Plan ID | Monthly premium | Coverage limit | Deductible |
|---|---|---|---|---|
| Auto | AUTO-BASIC | $89 | $15,000 | $1,000 |
| Auto | AUTO-STD | $149 | $50,000 | $500 |
| Auto | AUTO-PREM | $249 | $100,000 | $250 |
| Health | HEALTH-BASIC | $199 | $50,000 | $2,000 |
| Health | HEALTH-STD | $349 | $150,000 | $1,000 |
| Health | HEALTH-PREM | $549 | $500,000 | $250 |
| Home | HOME-BASIC | $79 | $100,000 | $2,500 |
| Home | HOME-STD | $149 | $300,000 | $1,000 |
| Home | HOME-PREM | $249 | $750,000 | $500 |
| Life | LIFE-BASIC | $29 | $100,000 | $0 |
| Life | LIFE-STD | $79 | $500,000 | $0 |
| Life | LIFE-PREM | $149 | $1,000,000 | $0 |
| Property | PROP-BASIC | $59 | $50,000 | $1,500 |
| Property | PROP-STD | $119 | $200,000 | $750 |
| Property | PROP-PREM | $199 | $500,000 | $250 |
| Liability | LIAB-BASIC | $49 | $100,000 | $1,000 |
| Liability | LIAB-STD | $99 | $300,000 | $500 |
| Liability | LIAB-PREM | $179 | $1,000,000 | $0 |

> **Coverage limit** = maximum the insurer pays per claim.  
> **Deductible** = what the customer covers themselves per claim.

---

## Tools

All tools live in `policy_management_agent/tools/policy_tools.py` and use an `asyncpg` connection pool.

### `get_available_plans(coverage_type=None)`

Returns the full catalog, optionally filtered by coverage type.

```python
await get_available_plans()                    # all 18 plans
await get_available_plans("auto")              # 3 auto plans only
# → {"status": "success", "plans": [...], "count": 3}
```

### `create_policy(...)`

Inserts a new policy row. The `plan_id`, `monthly_premium`, `coverage_limit`, and `deductible` are resolved by `PolicyWriterAgent` from the catalog before calling this.

```python
await create_policy(
    policy_number="POL-2026-001",
    holder_name="Jane Smith",
    plan_id="AUTO-STD",
    monthly_premium=149.0,
    coverage_limit=50_000.0,
    deductible=500.0,
    covered_types=["auto"],
    start_date="2026-05-01",
    end_date="2027-05-01",
)
# → {"status": "created", "policy_number": "POL-2026-001"}
# → {"status": "error",   "error": "..."}
```

### `lookup_policy(policy_number)`

Returns a single policy record or `None`.

```python
await lookup_policy("POL-2026-001")
# → {
#     "status":              "success",
#     "policy_number":       "POL-2026-001",
#     "is_active":           True,
#     "coverage_limit":      50000.0,
#     "deductible":          500.0,
#     "covered_claim_types": ["auto"],
#   }
# → None  (policy not found)
```

> **Claims-triage compatibility** — The `lookup_policy` return shape is consumed directly by the claims-triage agent's `policy_tools.py`. Both agents share the same PostgreSQL database; the claims agent only needs `DATABASE_URL` pointing to `insurance_user@localhost:5432/insurance`.

### `deactivate_policy(policy_number)`

Sets `is_active = false`.

```python
await deactivate_policy("POL-2026-001")
# → {"success": True,  "policy_number": "POL-2026-001"}
# → {"success": False, "error": "Policy 'X' not found."}
```

---

## Database schema

### `insurance_plans`

```sql
CREATE TABLE insurance_plans (
    plan_id         TEXT PRIMARY KEY,
    coverage_type   TEXT           NOT NULL,
    plan_name       TEXT           NOT NULL,
    monthly_premium NUMERIC(10, 2) NOT NULL,
    coverage_limit  NUMERIC(15, 2) NOT NULL,
    deductible      NUMERIC(15, 2) NOT NULL,
    description     TEXT
);
```

Pre-seeded with 18 plans on first container start.

### `policies`

```sql
CREATE TABLE policies (
    policy_number   TEXT PRIMARY KEY,
    holder_name     TEXT           NOT NULL,
    is_active       BOOLEAN        NOT NULL DEFAULT TRUE,
    plan_id         TEXT           REFERENCES insurance_plans(plan_id),
    monthly_premium NUMERIC(10, 2) NOT NULL,
    coverage_limit  NUMERIC(15, 2) NOT NULL,
    deductible      NUMERIC(15, 2) NOT NULL,
    covered_types   TEXT[]         NOT NULL,
    start_date      DATE           NOT NULL,
    end_date        DATE           NOT NULL
);
```

Managed by PostgreSQL 16 running in Docker. The schema is applied automatically on first container start via `docker-entrypoint-initdb.d`.

> **Existing database** — If the container volume already existed before `insurance_plans` was added, run the migration manually:
> ```bash
> python -c "
> import asyncio, asyncpg, os
> from dotenv import load_dotenv; load_dotenv('.env')
> url = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://')
> async def run():
>     conn = await asyncpg.connect(url)
>     await conn.execute(open('schema.sql').read())
>     await conn.execute('''
>         ALTER TABLE policies
>             ADD COLUMN IF NOT EXISTS plan_id TEXT REFERENCES insurance_plans(plan_id),
>             ADD COLUMN IF NOT EXISTS monthly_premium NUMERIC(10,2);
>         UPDATE policies SET monthly_premium = 0 WHERE monthly_premium IS NULL;
>         ALTER TABLE policies ALTER COLUMN monthly_premium SET NOT NULL;
>     ''')
>     await conn.close()
> asyncio.run(run())
> "
> ```

---

## Project structure

```
Policy_management_agent/
├── .env                              ← credentials (do not commit)
├── .env.example                      ← template
├── docker-compose.yml
├── schema.sql
├── main.py                           ← CLI entry point
├── requirements.txt
└── policy_management_agent/
    ├── __init__.py
    ├── agent.py                      ← PolicyManagementAgent class + root_agent
    ├── configs/
    │   ├── agent_configs.py          ← all agent prompts and model assignments
    │   ├── model_config.py           ← single LiteLlm model instance
    │   └── logging_config.py         ← logger + before_agent_callback
    ├── schemas/
    │   └── models.py                 ← Pydantic models (InsurancePlan, PolicyIntake, …)
    ├── sub_agents/
    │   ├── intake_agent.py
    │   ├── validation_agent.py
    │   ├── policy_writer_agent.py
    │   └── conversational_agent.py   ← root_agent for adk web
    └── tools/
        ├── policy_tools.py           ← DB tools (catalog, create, lookup, deactivate)
        └── pipeline_runner_tool.py   ← submit_policy() wrapper
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

**Browse plans**
```
You:   What auto insurance plans do you offer?
Agent: Here are our Auto Insurance plans:

       Plan ID    | Plan Name     | Monthly | Coverage Limit | Deductible
       -----------|---------------|---------|----------------|----------
       AUTO-BASIC | Basic Auto    | $89     | $15,000        | $1,000
       AUTO-STD   | Standard Auto | $149    | $50,000        | $500
       AUTO-PREM  | Premium Auto  | $249    | $100,000       | $250

       Coverage limit = max the insurer pays per claim.
       Deductible = what you cover yourself per claim.
```

**Create a policy**
```
You:   I'd like the Standard Auto plan for Jane Smith, starting May 1 2026 for one year.
Agent: Got it! I'll create the following policy:
         Plan: AUTO-STD (Standard Auto)
         Holder: Jane Smith
         Dates: 2026-05-01 → 2027-05-01
         Monthly premium: $149 | Coverage: $50,000 | Deductible: $500
       Policy POL-2026-001 has been created successfully.
```

**Look up a policy**
```
You:   Look up policy POL-2026-001
Agent: Policy POL-2026-001 — Jane Smith
       Status: Active | Plan: AUTO-STD | Monthly: $149
       Coverage: $50,000 | Deductible: $500 | 2026-05-01 → 2027-05-01
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
