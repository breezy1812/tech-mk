from app.adapters.ollama_client import OllamaUnavailableError
from app.domain.schemas.rag import ChunkSource, RAGQueryResponse, RetrievedChunk
from app.services.rag_prompt_builder import RAGPromptBuilder
from app.services.rag_service import RAGBackendError, RAGService


class FakeRetrievalService:
    def __init__(self, results=None, error: Exception | None = None) -> None:
        self.results = results or []
        self.error = error
        self.calls = []

    def retrieve(self, question: str, top_k: int | None = None):
        self.calls.append((question, top_k))
        if self.error:
            raise self.error
        return self.results


class FakeOllamaClient:
    def __init__(self, reply: str = "answer", error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls = []

    def chat(self, user_text: str):
        self.calls.append(user_text)
        if self.error:
            raise self.error
        return {"reply": self.reply, "model": "test-model"}


def test_rag_service_returns_answer_and_sources() -> None:
    retrieval = FakeRetrievalService(
        [
            RetrievedChunk(file="guide.md", chunk=0, relative_path="guide.md", content="RAG uses retrieval", score=0.9),
            RetrievedChunk(file="guide.md", chunk=1, relative_path="guide.md", content="More context", score=0.8),
        ]
    )
    client = FakeOllamaClient(reply="RAG combines retrieval and generation.")
    service = RAGService(retrieval_service=retrieval, prompt_builder=RAGPromptBuilder(), client=client)

    result = service.query(question="What is RAG?", top_k=2, debug=False)

    assert result.answer == "RAG combines retrieval and generation."
    assert result.sources == [ChunkSource(file="guide.md", chunk=0, relative_path="guide.md"), ChunkSource(file="guide.md", chunk=1, relative_path="guide.md")]
    assert result.retrieved_chunks is None
    assert len(client.calls) == 1


def test_rag_service_does_not_call_llm_when_no_chunks_found() -> None:
    retrieval = FakeRetrievalService([])
    client = FakeOllamaClient()
    service = RAGService(retrieval_service=retrieval, client=client)

    result = service.query(question="Unknown?", top_k=3, debug=True)

    assert result.sources == []
    assert result.answer == "目前知識庫中沒有足夠資訊可以回答這個問題。"
    assert result.retrieved_chunks == []
    assert client.calls == []


def test_rag_service_raises_backend_error_for_retrieval_failure() -> None:
    service = RAGService(retrieval_service=FakeRetrievalService(error=RuntimeError("broken")), client=FakeOllamaClient())

    try:
        service.query(question="broken", top_k=1)
    except RAGBackendError as exc:
        assert "retrieve" in str(exc).lower()
    else:
        raise AssertionError("Expected RAGBackendError")


def test_rag_service_raises_backend_error_for_llm_failure() -> None:
    retrieval = FakeRetrievalService([RetrievedChunk(file="guide.md", chunk=0, relative_path="guide.md", content="content", score=0.9)])
    service = RAGService(
        retrieval_service=retrieval,
        client=FakeOllamaClient(error=OllamaUnavailableError("down")),
    )

    try:
        service.query(question="broken", top_k=1)
    except RAGBackendError as exc:
        assert "ollama" in str(exc).lower()
    else:
        raise AssertionError("Expected RAGBackendError")
