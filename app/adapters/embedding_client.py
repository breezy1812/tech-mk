from typing import List

from app.adapters.ollama_client import OllamaEmbeddingClient


class EmbeddingClient:
    def __init__(self) -> None:
        self._client = OllamaEmbeddingClient()
        self.model_name = self._client.model
        self.timeout = self._client.timeout

    def embed(self, text: str) -> List[float]:
        return self._client.embed(text)
