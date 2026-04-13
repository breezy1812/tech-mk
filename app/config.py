from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "phase1-tech-km"
    app_env: str = "dev"
    app_port: int = 8000
    app_base_url: str = "http://127.0.0.1:8000"
    log_level: str = "INFO"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma3:4b"
    ollama_timeout_seconds: int = 120
    ollama_system_prompt: str = (
        "你是一個部署在私有伺服器上的技術資料管理助手。"
        "請優先用自然、像聊天一樣的口吻回答，預設使用短段落。"
        "除非使用者明確要求，否則不要用 Markdown 標題、過多條列、表格、或像文件模板的格式。"
        "回答應直接切入重點，避免前言、避免把答案寫成教學文件。"
        "若問題很簡單，先用 2 到 4 句直接回答；只有在真的需要拆點時才使用短條列。"
        "請用清楚、保守、可落地的方式回答。"
    )

    telegram_bot_token: str = ""
    telegram_polling_enabled: bool = True
    telegram_polling_timeout_seconds: int = 30
    telegram_polling_limit: int = 100
    telegram_polling_retry_delay_seconds: int = 5
    telegram_admin_user_ids: str = ""
    discord_bot_token: str = ""
    discord_public_key: str = ""

    rag_enabled: bool = True
    rag_docs_root: str = "data/docs"
    rag_vector_store_path: str = "data/vector_store"
    rag_collection_name: str = "tech_docs"
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_max_chunks_per_file: int = 2000
    rag_top_k: int = 3
    rag_embedding_model: str = "nomic-embed-text"
    rag_embedding_timeout_seconds: int = 60
    rag_embedding_batch_size: int = 32
    rag_loader_timeout_seconds: int = 120
    rag_allow_reindex: bool = False
    rag_query_debug_default: bool = False
    rag_chroma_anonymized_telemetry: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def telegram_admin_user_id_set(self) -> set[str]:
        values = [value.strip() for value in self.telegram_admin_user_ids.split(",")]
        return {value for value in values if value}


settings = Settings()
