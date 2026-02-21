from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CarePath AI"
    environment: str = "dev"
    db_path: str = "app/data/carepath.db"
    uploads_dir: str = "app/data/uploads"
    knowledge_base_dir: str = "app/data/kb"
    default_llm_provider: str = "fallback"
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.1-8b-instant"
    max_upload_size_mb: int = Field(default=10, ge=1, le=25)
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_data_dirs(self) -> None:
        Path(self.uploads_dir).mkdir(parents=True, exist_ok=True)
        Path(self.knowledge_base_dir).mkdir(parents=True, exist_ok=True)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_data_dirs()
    return settings
