from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SourceDocument(BaseModel):
    file_name: str
    relative_path: str
    source_type: str
    content: str


class ChunkSource(BaseModel):
    file: str
    chunk: int
    relative_path: str


class ChunkRecord(BaseModel):
    chunk_id: str
    content: str
    file_name: str
    relative_path: str
    source_type: str
    chunk_index: int
    content_hash: str
    metadata: Dict[str, str] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    file: str
    chunk: int
    relative_path: str
    content: str
    score: Optional[float] = None


class IndexingFileReport(BaseModel):
    file: str
    relative_path: str
    chunk_count: int
    status: str
    error: Optional[str] = None


class IndexManifestFile(BaseModel):
    file: str
    relative_path: str
    source_type: str
    file_hash: str
    last_modified_at: datetime
    chunk_ids: List[str]
    chunk_count: int


class IndexManifest(BaseModel):
    collection_name: str
    docs_root: str
    updated_at: datetime
    files: List[IndexManifestFile]


class IndexingReport(BaseModel):
    mode: str = "reindex"
    collection_name: str
    embedding_model: str
    docs_root: str
    files_processed: int
    chunks_indexed: int
    files_indexed: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    files: List[IndexingFileReport]
    failed_files: List[str]
    indexed_at: datetime


class RAGStatusResponse(BaseModel):
    enabled: bool
    collection_name: str
    embedding_model: str
    docs_root: str
    chunk_size: int
    chunk_overlap: int
    indexed_files: int
    indexed_chunks: int
    last_indexed_at: Optional[datetime] = None
    last_report: Optional[IndexingReport] = None


class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: Optional[int] = Field(default=None, ge=1, le=10)
    debug: bool = False


class RAGQueryResponse(BaseModel):
    answer: str
    sources: List[ChunkSource]
    retrieved_chunks: Optional[List[RetrievedChunk]] = None
