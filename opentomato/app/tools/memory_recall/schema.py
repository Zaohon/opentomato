SCHEMA = {
    "type": "function",
    "function": {
        "name": "memory_recall",
        "description": (
            "Recall long-term memory for identity, past conversations, preferences, household facts, "
            "device background, and other historical user information. Use this tool before answering "
            "questions such as 'Who am I?', 'Do you remember me?', 'What did I say before?', "
            "'What did we talk about yesterday?', or any question that depends on prior conversations "
            "or stored user facts. If current profile/context is insufficient, call this tool first "
            "instead of guessing or saying you cannot access past conversations. "
            "IMPORTANT: The query text should follow the user's language. "
            "For Chinese users, prefer Chinese query terms such as '我是谁 姓名 身份'."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A focused search query describing the historical fact or past conversation to recall, "
                        "such as a name, household detail, preference, device fact, or prior conversation topic. "
                        "Use the same language as the user's latest message."
                    ),
                }
            },
            "required": ["query"],
        },
    },
}
