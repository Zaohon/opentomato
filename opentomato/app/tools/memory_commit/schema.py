SCHEMA = {
    "type": "function",
    "function": {
        "name": "memory_commit",
        "description": (
            "Force commit current memory session to OpenViking. "
            "Use when explicit memory capture happened and immediate extraction is required."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Short reason for forcing commit.",
                }
            },
            "required": ["reason"],
        },
    },
}
