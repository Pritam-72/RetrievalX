from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    log_content: bool = False
    frontend_origin: str = "http://localhost:3000"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/docqa"
    upload_dir: str = "./uploads"
    max_upload_mb: int = Field(default=25, gt=0)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = Field(default=384, gt=0)
    reranker_model: str = "BAAI/bge-reranker-base"
    llm_provider: str = "gemini"
    llm_model: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"


@lru_cache
def get_settings() -> Settings:
    return Settings()
