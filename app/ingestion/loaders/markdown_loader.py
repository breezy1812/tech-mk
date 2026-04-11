from pathlib import Path

from app.domain.schemas.rag import SourceDocument


class MarkdownLoader:
    supported_suffixes = {".md"}

    def load(self, path: Path, docs_root: Path) -> SourceDocument:
        return SourceDocument(
            file_name=path.name,
            relative_path=path.relative_to(docs_root).as_posix(),
            source_type="markdown",
            content=path.read_text(encoding="utf-8"),
        )
