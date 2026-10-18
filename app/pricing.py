"""Estimated pilot model pricing used for reporting and the budget guard."""


def estimated_openai_cost(metadata: dict) -> float | None:
    if metadata.get("model") != "gpt-6-luna":
        return None
    input_tokens = metadata.get("input_tokens")
    output_tokens = metadata.get("output_tokens")
    if input_tokens is None or output_tokens is None:
        return None
    return (input_tokens * 0.10 + output_tokens * 0.50) / 1_000_000
