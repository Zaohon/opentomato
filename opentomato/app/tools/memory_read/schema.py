SCHEMA = {
    "type": "function",
    "function": {
        "name": "memory_read",
        "description": (
            "Read a specific OpenViking memory URI by level. "
            "Use level='overview' first. Only use level='detail' when more evidence is needed."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "uri": {
                    "type": "string",
                    "description": "Target Viking URI to read.",
                },
                "level": {
                    "type": "string",
                    "enum": ["abstract", "overview", "detail"],
                    "description": "Read abstraction level. Prefer overview.",
                },
            },
            "required": ["uri", "level"],
        },
    },
}
