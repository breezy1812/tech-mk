from pathlib import Path

from app.ingestion.loaders.docx_loader import DocxLoader
from app.ingestion.loaders.markdown_loader import MarkdownLoader
from app.ingestion.loaders.pdf_loader import PDFLoader
from app.ingestion.loaders.text_loader import TextLoader


class DocumentLoaderRegistry:
    def __init__(self) -> None:
        self._loaders = [MarkdownLoader(), TextLoader(), PDFLoader(), DocxLoader()]

    def supports(self, path: Path) -> bool:
        return self._get_loader(path) is not None

    def load(self, path: Path, docs_root: Path):
        loader = self._get_loader(path)
        if loader is None:
            raise ValueError(f"Unsupported file type: {path.suffix}")
        return loader.load(path, docs_root)

    def supported_suffixes(self) -> set[str]:
        suffixes: set[str] = set()
        for loader in self._loaders:
            suffixes.update(loader.supported_suffixes)
        return suffixes

    def _get_loader(self, path: Path):
        for loader in self._loaders:
            if path.suffix.lower() in loader.supported_suffixes:
                return loader
        return None
