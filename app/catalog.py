SERVICE_CATALOG = [
    {
        "service_key": "search.web",
        "pricing_mode": "fixed",
        "fixed_cost_micro_usdc": 100_000,
    },
    {
        "service_key": "ocr.parse_image",
        "pricing_mode": "fixed",
        "fixed_cost_micro_usdc": 200_000,
    },
    {
        "service_key": "llm.chat",
        "pricing_mode": "reserve_then_settle",
        "input_cost_per_1k_micro_usdc": 50_000,
        "output_cost_per_1k_micro_usdc": 100_000,
        "reserve_buffer_bps": 12000,
    },
]


def get_service(service_key: str) -> dict[str, int | str] | None:
    for service in SERVICE_CATALOG:
        if service["service_key"] == service_key:
            return service
    return None
