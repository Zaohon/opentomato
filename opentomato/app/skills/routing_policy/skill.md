# Skill: routing_policy

- Route by intent first, not by keyword overlap.
- Prefer `support_agent` when the request is conversational or ambiguous.
- Only route to `control_agent` when user clearly asks for an operational action.
- Route to `analyst_agent` for telemetry, trends, forecasts, or pricing analysis.
