from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def to_asyncpg_url(url: str) -> str:
    """Convert a PostgreSQL URL to the SQLAlchemy asyncpg form."""
    if not url:
        raise ValueError("A PostgreSQL URL is required")

    parsed = urlsplit(url)
    if parsed.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}:
        raise ValueError(f"Unsupported database URL scheme: {parsed.scheme}")

    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in {"sslmode", "ssl"}
    ]
    query.append(("ssl", "require"))
    return urlunsplit(
        (
            "postgresql+asyncpg",
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    log_content: bool = False
    frontend_origin: str = "http://localhost:3000"
    debug_enabled: bool = False
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/docqa"
    database_url_unpooled: str = ""
    database_url_test: str = ""
    upload_dir: str = "./uploads"
    max_upload_mb: int = Field(default=25, gt=0)
    min_cosine: float = Field(default=0.30, ge=-1, le=1)
    max_question_length: int = Field(default=2000, gt=0)
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
