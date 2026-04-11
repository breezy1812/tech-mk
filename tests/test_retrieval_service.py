from app.domain.schemas.rag import RetrievedChunk
from app.services import retrieval_service as retrieval_service_module
from app.services.retrieval_service import RetrievalService


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1, 0.2]


class FakeVectorStore:
    def __init__(self, payload: list[RetrievedChunk]) -> None:
        self.payload = payload
        self.calls = []

    def query(self, embedding: list[float], top_k: int) -> list[RetrievedChunk]:
        self.calls.append((embedding, top_k))
        return self.payload[:top_k]


def test_retrieval_service_returns_top_k_chunks() -> None:
    embedding_client = FakeEmbeddingClient()
    vector_store = FakeVectorStore(
        [
            RetrievedChunk(file="a.md", chunk=0, relative_path="a.md", content="A", score=0.9),
            RetrievedChunk(file="b.md", chunk=1, relative_path="b.md", content="B", score=0.8),
        ]
    )
    service = RetrievalService(embedding_client=embedding_client, vector_store=vector_store)

    results = service.retrieve(question="what is rag", top_k=1)

    assert embedding_client.calls == ["what is rag"]
    assert vector_store.calls == [([0.1, 0.2], 1)]
    assert len(results) == 1
    assert results[0].file == "a.md"


def test_retrieval_service_returns_empty_list_when_no_matches() -> None:
    service = RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=FakeVectorStore([]),
    )

    results = service.retrieve(question="no docs", top_k=3)

    assert results == []


def test_retrieval_service_rebuilds_default_vector_store_each_call(monkeypatch) -> None:
    created_stores = []

    class FakeChromaVectorStore:
        def __init__(self, persist_path: str, collection_name: str) -> None:
            self.persist_path = persist_path
            self.collection_name = collection_name
            self.calls = []
            created_stores.append(self)

        def query(self, embedding: list[float], top_k: int) -> list[RetrievedChunk]:
            self.calls.append((embedding, top_k))
            return []

    monkeypatch.setattr(retrieval_service_module, "ChromaVectorStore", FakeChromaVectorStore)
    service = RetrievalService(embedding_client=FakeEmbeddingClient())

    service.retrieve(question="first", top_k=1)
    service.retrieve(question="second", top_k=2)

    assert len(created_stores) == 2
    assert created_stores[0].calls == [([0.1, 0.2], 1)]
    assert created_stores[1].calls == [([0.1, 0.2], 2)]
