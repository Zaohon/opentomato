SCHEMA = {
    "type": "function",
    "function": {
        "name": "memory_store",
        "description": (
            "Save a stable user fact, preference, goal, constraint, device detail, or other long-term memory. "
            "This tool writes the new memory into long-term memory storage and also triggers an automatic profile "
            "refresh attempt for the user's canonical profile. Use it for information that should still matter in "
            "future conversations. You should call this tool when the user provides identity information "
            "(for example, 'My name is X'), household facts, long-term preferences, device background, or "
            "explicitly asks you to remember something. Do not use it for temporary status, one-off commands, "
            "or short-lived context."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "text": {
                    "type": "string",
                    "description": (
                        "The stable user information to persist, written as a concise factual memory statement, "
                        "such as a name, household background, long-term preference, ongoing goal, important "
                        "device fact, or durable operating constraint."
                    ),
                }
            },
            "required": ["text"],
        },
    },
}
