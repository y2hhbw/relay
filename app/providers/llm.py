from typing import Any


def run_chat(prompt: str, model: str, max_output_tokens: int) -> dict[str, Any]:
    del model
    del max_output_tokens
    return {
        "content": f"Echo: {prompt}",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 200,
        },
    }
