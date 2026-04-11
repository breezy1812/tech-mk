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
    discord_bot_token: str = ""
    discord_public_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
