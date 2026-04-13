import hashlib
from typing import Iterable, List

from app.domain.schemas.rag import ChunkRecord, SourceDocument
from app.ingestion.text_sanitizer import sanitize_text


class TextChunker:
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, document: SourceDocument) -> List[ChunkRecord]:
        normalized_content = sanitize_text(document.content)

        if document.source_type == "markdown":
            segments = self._split_markdown(normalized_content)
        else:
            segments = self._split_plain_text(normalized_content)

        chunks = self._assemble_chunks(segments)
        records: List[ChunkRecord] = []
        for index, content in enumerate(chunks):
            safe_content = sanitize_text(content)
            records.append(
                ChunkRecord(
                    chunk_id=f"{document.relative_path}:{index}",
                    content=safe_content,
                    file_name=document.file_name,
                    relative_path=document.relative_path,
                    source_type=document.source_type,
                    chunk_index=index,
                    content_hash=hashlib.sha256(safe_content.encode("utf-8")).hexdigest(),
                    metadata={
                        "file_name": document.file_name,
                        "relative_path": document.relative_path,
                        "source_type": document.source_type,
                    },
                )
            )
        return records

    def _split_markdown(self, text: str) -> List[str]:
        blocks: List[str] = []
        current: List[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") and current:
                blocks.append("\n".join(current).strip())
                current = [line]
                continue
            current.append(line)
            if not stripped and current:
                block = "\n".join(current).strip()
                if block:
                    blocks.append(block)
                current = []

        trailing = "\n".join(current).strip()
        if trailing:
            blocks.append(trailing)
        return [block for block in blocks if block]

    def _split_plain_text(self, text: str) -> List[str]:
        blocks = [block.strip() for block in text.split("\n\n")]
        return [block for block in blocks if block]

    def _assemble_chunks(self, segments: Iterable[str]) -> List[str]:
        chunks: List[str] = []
        current = ""

        for segment in segments:
            normalized = segment.strip()
            if not normalized:
                continue
            if len(normalized) > self.chunk_size:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.extend(self._slice_long_segment(normalized))
                continue

            tentative = normalized if not current else f"{current}\n\n{normalized}"
            if len(tentative) <= self.chunk_size:
                current = tentative
                continue

            if current:
                chunks.append(current.strip())
            overlap = current[-self.chunk_overlap :].strip() if current and self.chunk_overlap else ""
            current = normalized if not overlap else f"{overlap}\n\n{normalized}"

            if len(current) > self.chunk_size:
                chunks.extend(self._slice_long_segment(current))
                current = ""

        if current.strip():
            chunks.append(current.strip())
        return chunks

    def _slice_long_segment(self, text: str) -> List[str]:
        values: List[str] = []
        start = 0
        step = self.chunk_size - self.chunk_overlap
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            values.append(text[start:end].strip())
            if end >= len(text):
                break
            start += step
        return [value for value in values if value]
