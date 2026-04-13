import multiprocessing
import logging
import os
import signal
import shutil
import subprocess
from time import monotonic
from pathlib import Path

from app.config import settings
from app.domain.schemas.rag import SourceDocument
from app.ingestion.loaders.docx_loader import DocxLoader
from app.ingestion.loaders.markdown_loader import MarkdownLoader
from app.ingestion.loaders.pdf_loader import PDFLoader
from app.ingestion.text_sanitizer import sanitize_text
from app.ingestion.loaders.text_loader import TextLoader


logger = logging.getLogger(__name__)


def _load_document_in_subprocess(loader, path_str: str, docs_root_str: str, connection) -> None:
    path = Path(path_str)
    docs_root = Path(docs_root_str)
    try:
        document = loader.load(path, docs_root)
        connection.send(("ok", document.model_dump()))
    except Exception as exc:
        connection.send(("error", str(exc)))
    finally:
        connection.close()


class DocumentLoaderRegistry:
    _sandboxed_suffixes = {".pdf", ".docx"}
    _sandbox_poll_interval_seconds = 0.2
    _sandbox_stop_timeout_seconds = 1.0

    def __init__(self, shutdown_checker=None) -> None:
        self._loaders = [MarkdownLoader(), TextLoader(), PDFLoader(), DocxLoader()]
        self._shutdown_checker = shutdown_checker or (lambda: False)
        self._sandbox_timeout_seconds = settings.rag_loader_timeout_seconds

    def supports(self, path: Path) -> bool:
        return self._get_loader(path) is not None

    def load(self, path: Path, docs_root: Path):
        loader = self._get_loader(path)
        if loader is None:
            raise ValueError(f"Unsupported file type: {path.suffix}")
        if path.suffix.lower() in self._sandboxed_suffixes:
            return self._load_in_subprocess(loader, path, docs_root)
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

    def _load_in_subprocess(self, loader, path: Path, docs_root: Path) -> SourceDocument:
        context = multiprocessing.get_context()
        parent_connection, child_connection = context.Pipe(duplex=False)
        process = context.Process(
            target=_load_document_in_subprocess,
            args=(loader, str(path), str(docs_root), child_connection),
        )
        try:
            process.start()
            child_connection.close()
            deadline = monotonic() + self._sandbox_timeout_seconds

            while process.is_alive():
                if self._shutdown_checker():
                    self._stop_process(process)
                    raise RuntimeError(f"Document loader interrupted for {path.name}")

                remaining = deadline - monotonic()
                if remaining <= 0:
                    self._stop_process(process)
                    if path.suffix.lower() == ".pdf":
                        return self._load_pdf_with_pdftotext(path, docs_root)
                    raise RuntimeError(f"Document loader timed out for {path.name}")

                process.join(timeout=min(self._sandbox_poll_interval_seconds, remaining))

            if process.exitcode != 0 and path.suffix.lower() == ".pdf":
                return self._load_pdf_with_pdftotext(path, docs_root)

            if process.exitcode != 0:
                raise RuntimeError(f"Document loader crashed for {path.name} with exit code {process.exitcode}")

            if not parent_connection.poll():
                raise RuntimeError(f"Document loader returned no result for {path.name}")

            status, payload = parent_connection.recv()
            if status == "error":
                raise RuntimeError(str(payload))
            return SourceDocument.model_validate(payload)
        finally:
            parent_connection.close()
            if process.is_alive():
                self._stop_process(process)
            if hasattr(process, "close"):
                process.close()

    def _stop_process(self, process) -> None:
        if not process.is_alive():
            return

        process.terminate()
        process.join(timeout=self._sandbox_stop_timeout_seconds)
        if not process.is_alive():
            return

        pid = getattr(process, "pid", None)
        if pid is not None:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                return

        process.join(timeout=self._sandbox_stop_timeout_seconds)

    def _load_pdf_with_pdftotext(self, path: Path, docs_root: Path) -> SourceDocument:
        pdftotext = shutil.which("pdftotext")
        if not pdftotext:
            raise RuntimeError(f"Document loader crashed for {path.name} and pdftotext is not available")

        logger.warning("Falling back to pdftotext for %s", path.name)
        try:
            result = subprocess.run(
                [pdftotext, "-layout", str(path), "-"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._sandbox_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Document loader timed out for {path.name}") from exc

        if result.returncode != 0:
            message = result.stderr.strip() or f"pdftotext exited with code {result.returncode}"
            raise RuntimeError(f"Document loader crashed for {path.name}; pdftotext failed: {message}")

        return SourceDocument(
            file_name=path.name,
            relative_path=path.relative_to(docs_root).as_posix(),
            source_type="pdf",
            content=sanitize_text(result.stdout).strip(),
        )
