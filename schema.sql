-- Insurance policies table
-- covered_types uses a native PostgreSQL TEXT array so individual
-- coverage categories (auto, health, home, life, …) can be queried
-- with the @> containment operator from the claims-triage side.

CREATE TABLE IF NOT EXISTS policies (
    policy_number   TEXT PRIMARY KEY,
    holder_name     TEXT        NOT NULL,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    coverage_limit  NUMERIC(15, 2) NOT NULL,
    deductible      NUMERIC(15, 2) NOT NULL,
    covered_types   TEXT[]      NOT NULL,
    start_date      DATE        NOT NULL,
    end_date        DATE        NOT NULL
);
