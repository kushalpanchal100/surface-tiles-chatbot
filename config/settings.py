import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Google Gemini Settings
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.5-flash-lite", validation_alias="GEMINI_MODEL")
    gemini_embedding_model: str = Field(default="gemini-embedding-001", validation_alias="GEMINI_EMBEDDING_MODEL")

    # Data & Storage Directories
    base_dir: Path = BASE_DIR
    data_raw_dir: Path = BASE_DIR / "data" / "raw"
    data_processed_dir: Path = BASE_DIR / "data" / "processed"
    chroma_persist_dir: Path = BASE_DIR / "data" / "embeddings" / "chroma"
    logs_dir: Path = BASE_DIR / "logs"
    log_retention_days: int = Field(default=2, validation_alias="LOG_RETENTION_DAYS")

    # Scraper Settings
    base_url: str = "https://surfacestiles.co.uk"
    request_timeout: int = 15
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 (SurfacesTilesBot/1.0)"

    # RAG Settings
    top_k: int = 10
    score_threshold: float = 0.2
    max_chat_history: int = Field(default=10, validation_alias="MAX_CHAT_HISTORY")

    # Server Settings
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8060, validation_alias="PORT")
    debug: bool = Field(default=False, validation_alias="DEBUG")


settings = Settings()

# Ensure directories exist
settings.data_raw_dir.mkdir(parents=True, exist_ok=True)
settings.data_processed_dir.mkdir(parents=True, exist_ok=True)
settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
settings.logs_dir.mkdir(parents=True, exist_ok=True)
