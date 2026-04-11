from typing import Any, Dict

import requests

from app.config import settings


class OllamaUnavailableError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout_seconds
        self.system_prompt = settings.ollama_system_prompt

    def chat(self, user_text: str) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_text},
            ],
        }
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OllamaUnavailableError(f"Failed to reach Ollama at {self.base_url}") from exc

        data = response.json()
        return {
            "reply": data.get("message", {}).get("content", ""),
            "model": data.get("model", self.model),
            "raw": data,
        }
