SCHEMA = {
    "type": "function",
    "function": {
        "name": "handoff_tool",
        "description": "Route current user request to the best downstream agent.",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "target_agent": {
                    "type": "string",
                    "description": "Target agent to receive handoff.",
                    "enum": ["control_agent", "analyst_agent", "support_agent"],
                },
                "reason": {
                    "type": "string",
                    "description": "Short rationale for audit logs.",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score in [0,1].",
                    "minimum": 0,
                    "maximum": 1,
                },
            },
            "required": ["target_agent", "reason"],
        },
    },
}

