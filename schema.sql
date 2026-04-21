-- ---------------------------------------------------------------------------
-- Insurance product catalog
-- Defines the plans customers can choose from, including pricing tiers.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS insurance_plans (
    plan_id         TEXT PRIMARY KEY,
    coverage_type   TEXT           NOT NULL,   -- auto | health | home | life | property | liability
    plan_name       TEXT           NOT NULL,
    monthly_premium NUMERIC(10, 2) NOT NULL,   -- what the customer pays per month
    coverage_limit  NUMERIC(15, 2) NOT NULL,   -- maximum the insurer pays per claim
    deductible      NUMERIC(15, 2) NOT NULL,   -- what the customer covers themselves per claim
    description     TEXT
);

-- Seed data — 3 tiers per coverage type (Basic / Standard / Premium)
INSERT INTO insurance_plans (plan_id, coverage_type, plan_name, monthly_premium, coverage_limit, deductible, description) VALUES
  -- Auto
  ('AUTO-BASIC',    'auto',      'Basic Auto',            89.00,    15000.00,  1000.00, 'Essential auto coverage for everyday drivers'),
  ('AUTO-STD',      'auto',      'Standard Auto',        149.00,    50000.00,   500.00, 'Comprehensive auto coverage with lower out-of-pocket costs'),
  ('AUTO-PREM',     'auto',      'Premium Auto',         249.00,   100000.00,   250.00, 'Maximum auto protection with minimal out-of-pocket'),
  -- Health
  ('HEALTH-BASIC',  'health',    'Basic Health',         199.00,    50000.00,  2000.00, 'Essential health coverage for individuals'),
  ('HEALTH-STD',    'health',    'Standard Health',      349.00,   150000.00,  1000.00, 'Balanced health coverage with moderate deductible'),
  ('HEALTH-PREM',   'health',    'Premium Health',       549.00,   500000.00,   250.00, 'Comprehensive health coverage with minimal deductible'),
  -- Home
  ('HOME-BASIC',    'home',      'Basic Home',            79.00,   100000.00,  2500.00, 'Essential home protection'),
  ('HOME-STD',      'home',      'Standard Home',        149.00,   300000.00,  1000.00, 'Comprehensive home coverage'),
  ('HOME-PREM',     'home',      'Premium Home',         249.00,   750000.00,   500.00, 'Maximum home protection'),
  -- Life
  ('LIFE-BASIC',    'life',      'Basic Life',            29.00,   100000.00,     0.00, 'Essential life coverage'),
  ('LIFE-STD',      'life',      'Standard Life',         79.00,   500000.00,     0.00, 'Substantial life coverage for families'),
  ('LIFE-PREM',     'life',      'Premium Life',         149.00,  1000000.00,     0.00, 'Maximum life coverage'),
  -- Property
  ('PROP-BASIC',    'property',  'Basic Property',        59.00,    50000.00,  1500.00, 'Essential property coverage'),
  ('PROP-STD',      'property',  'Standard Property',    119.00,   200000.00,   750.00, 'Comprehensive property coverage'),
  ('PROP-PREM',     'property',  'Premium Property',     199.00,   500000.00,   250.00, 'Maximum property protection'),
  -- Liability
  ('LIAB-BASIC',    'liability', 'Basic Liability',       49.00,   100000.00,  1000.00, 'Essential liability coverage'),
  ('LIAB-STD',      'liability', 'Standard Liability',    99.00,   300000.00,   500.00, 'Comprehensive liability coverage'),
  ('LIAB-PREM',     'liability', 'Premium Liability',    179.00,  1000000.00,     0.00, 'Maximum liability protection')
ON CONFLICT (plan_id) DO NOTHING;


-- ---------------------------------------------------------------------------
-- Insurance policies table
-- covered_types uses a native PostgreSQL TEXT array so individual
-- coverage categories (auto, health, home, life, …) can be queried
-- with the @> containment operator from the claims-triage side.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS policies (
    policy_number   TEXT PRIMARY KEY,
    holder_name     TEXT           NOT NULL,
    is_active       BOOLEAN        NOT NULL DEFAULT TRUE,
    plan_id         TEXT           REFERENCES insurance_plans(plan_id),
    monthly_premium NUMERIC(10, 2) NOT NULL,   -- copied from plan at creation time
    coverage_limit  NUMERIC(15, 2) NOT NULL,   -- what the insurer pays out per claim
    deductible      NUMERIC(15, 2) NOT NULL,   -- what the customer covers per claim
    covered_types   TEXT[]         NOT NULL,
    start_date      DATE           NOT NULL,
    end_date        DATE           NOT NULL
);
