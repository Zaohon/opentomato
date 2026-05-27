SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_station_forecast_24h",
        "description": (
            "Fetch next-24-hour station forecast including predicted PV power and load power."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "station_id": {
                    "type": "integer",
                    "description": "Station ID used by forecast API. Default is 1.",
                    "minimum": 1,
                }
            },
        },
    },
}

