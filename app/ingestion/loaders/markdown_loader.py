from pathlib import Path

from app.domain.schemas.rag import SourceDocument
from app.ingestion.loaders.text_decoding import read_text_file


class MarkdownLoader:
    supported_suffixes = {".md"}

    def load(self, path: Path, docs_root: Path) -> SourceDocument:
        return SourceDocument(
            file_name=path.name,
            relative_path=path.relative_to(docs_root).as_posix(),
            source_type="markdown",
            content=read_text_file(path),
        )
