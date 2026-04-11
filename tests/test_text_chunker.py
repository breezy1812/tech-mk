from app.domain.schemas.rag import SourceDocument
from app.ingestion.chunkers.text_chunker import TextChunker


def test_markdown_chunker_keeps_metadata_and_indices() -> None:
    chunker = TextChunker(chunk_size=80, chunk_overlap=12)
    document = SourceDocument(
        file_name="guide.md",
        relative_path="docs/guide.md",
        source_type="markdown",
        content=(
            "# Intro\n"
            "Phase 2A starts with predictable indexing and reporting.\n\n"
            "## Details\n"
            "Chunking should keep metadata stable and split markdown on headings.\n\n"
            "## More\n"
            "A later chunk should still contain the correct file mapping."
        ),
    )

    chunks = chunker.chunk_document(document)

    assert len(chunks) >= 2
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.file_name == "guide.md" for chunk in chunks)
    assert all(chunk.relative_path == "docs/guide.md" for chunk in chunks)
    assert all(chunk.metadata["source_type"] == "markdown" for chunk in chunks)


def test_plain_text_chunker_uses_overlap_for_long_segments() -> None:
    chunker = TextChunker(chunk_size=30, chunk_overlap=10)
    document = SourceDocument(
        file_name="notes.txt",
        relative_path="notes.txt",
        source_type="text",
        content="abcdefghij" * 8,
    )

    chunks = chunker.chunk_document(document)

    assert len(chunks) > 1
    assert chunks[0].content[-10:] == chunks[1].content[:10]
