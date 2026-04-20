"""
PolicyWriterAgent
-----------------
Persists a validated policy record to PostgreSQL using the create_policy tool.
"""

from google.adk.agents import LlmAgent

from policy_management_agent.tools.policy_tools import create_policy

policy_writer_agent = LlmAgent(
    name="PolicyWriterAgent",
    model="gemini-2.0-flash",
    description=(
        "Receives validated policy data and writes it to PostgreSQL using the "
        "create_policy tool. Reports the success or failure of the operation."
    ),
    instruction="""You are an insurance policy database writer.
Your only job is to persist a validated policy record to the database.

Steps
-----
1. Parse the validated policy data passed to you by the coordinator.
2. Call the create_policy tool with exactly these parameters:
     - policy_number  (str)
     - holder_name    (str)
     - coverage_limit (float)
     - deductible     (float)
     - covered_types  (list of str)
     - start_date     (str, YYYY-MM-DD)
     - end_date       (str, YYYY-MM-DD)
3. Report the result clearly:
   - On success : "Policy <policy_number> has been created successfully."
   - On failure : "Failed to create policy: <error message from tool>"

Do NOT modify the data — write it exactly as received.
Do NOT attempt to validate, look up, or deactivate policies.
""",
    tools=[create_policy],
)
