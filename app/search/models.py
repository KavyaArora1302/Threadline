"""Catalog of AI models Threadline can answer with, across providers."""

MODELS = [
    {
        "id": "gemini-3-flash-preview",
        "label": "Gemini 3 Flash",
        "provider": "gemini",
        "supports_image": True,
    },
    {
        "id": "qwen/qwen3.6-27b",
        "label": "Qwen3.6 27B (Groq)",
        "provider": "groq",
        "supports_image": True,
    },
]

DEFAULT_MODEL_ID = "gemini-3-flash-preview"


def get_model(model_id: str) -> dict:
    for m in MODELS:
        if m["id"] == model_id:
            return m
    raise ValueError(f"Unknown model id '{model_id}'")
