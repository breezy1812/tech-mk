from pathlib import Path

from app.domain.schemas.rag import SourceDocument


class TextLoader:
    supported_suffixes = {".txt"}

    def load(self, path: Path, docs_root: Path) -> SourceDocument:
        return SourceDocument(
            file_name=path.name,
            relative_path=path.relative_to(docs_root).as_posix(),
            source_type="text",
            content=path.read_text(encoding="utf-8"),
        )
