from __future__ import annotations

try:
    import requests
except ImportError as exc:  # pragma: no cover - runtime dependency
    requests = None
    REQUESTS_IMPORT_ERROR = exc
else:
    REQUESTS_IMPORT_ERROR = None

from config import RefineConfig


def refine_text(text: str, config: RefineConfig) -> str:
    if not config.enabled or not text.strip():
        return text.strip()

    if requests is None:
        raise RuntimeError(
            "requests is required for Ollama refine mode. Install requirements.txt first."
        ) from REQUESTS_IMPORT_ERROR

    response = requests.post(
        f"{config.ollama_url.rstrip('/')}/api/generate",
        json={
            "model": config.model,
            "prompt": f"{config.prompt}\n\n輸入：{text}\n輸出：",
            "stream": False,
        },
        timeout=10,
    )
    response.raise_for_status()

    refined = response.json().get("response", "").strip()
    return refined or text.strip()

