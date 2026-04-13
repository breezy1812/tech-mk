from typing import Any, Dict, List

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


class OllamaEmbeddingClient:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.rag_embedding_model
        self.timeout = settings.rag_embedding_timeout_seconds

    def embed(self, text: str) -> List[float]:
        last_error: requests.RequestException | None = None
        candidates = [
            ("/api/embed", {"model": self.model, "input": text}),
            ("/api/embeddings", {"model": self.model, "prompt": text}),
        ]

        for path, payload in candidates:
            try:
                response = requests.post(
                    f"{self.base_url}{path}",
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
            except requests.HTTPError as exc:
                last_error = exc
                if exc.response is not None and exc.response.status_code == 404:
                    continue
                raise OllamaUnavailableError(f"Failed to call Ollama embeddings at {self.base_url}") from exc
            except requests.RequestException as exc:
                raise OllamaUnavailableError(f"Failed to reach Ollama embeddings at {self.base_url}") from exc

            embedding = self._extract_embedding(response.json())
            if embedding is not None:
                return embedding
            raise OllamaUnavailableError("Ollama embeddings returned an invalid payload")

        raise OllamaUnavailableError(f"Failed to call Ollama embeddings at {self.base_url}") from last_error

    def _extract_embedding(self, data: Dict[str, Any]) -> List[float] | None:
        embedding = data.get("embedding")
        if isinstance(embedding, list):
            return [float(value) for value in embedding]

        embeddings = data.get("embeddings")
        if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
            return [float(value) for value in embeddings[0]]

        return None