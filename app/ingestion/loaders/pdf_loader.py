from pathlib import Path

from app.domain.schemas.rag import SourceDocument
from app.ingestion.text_sanitizer import sanitize_text


class PDFLoader:
    supported_suffixes = {".pdf"}

    def load(self, path: Path, docs_root: Path) -> SourceDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required to load PDF documents") from exc

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            text = sanitize_text(text).strip()
            if text:
                pages.append(text)

        content = "\n\n".join(pages)
        return SourceDocument(
            file_name=path.name,
            relative_path=path.relative_to(docs_root).as_posix(),
            source_type="pdf",
            content=content,
        )
