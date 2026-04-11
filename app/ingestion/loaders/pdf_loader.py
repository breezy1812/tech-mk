from pathlib import Path

from app.domain.schemas.rag import SourceDocument


class PDFLoader:
    supported_suffixes = {".pdf"}

    def load(self, path: Path, docs_root: Path) -> SourceDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required to load PDF documents") from exc

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        content = "\n\n".join(page.strip() for page in pages if page.strip())
        return SourceDocument(
            file_name=path.name,
            relative_path=path.relative_to(docs_root).as_posix(),
            source_type="pdf",
            content=content,
        )
