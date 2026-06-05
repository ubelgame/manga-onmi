from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    # Railway provides DATABASE_URL as postgres:// — we normalise it
    database_url: str = "postgresql+asyncpg://manga:manga_secret@localhost:5432/manga_omni"

    @property
    def async_database_url(self) -> str:
        """asyncpg requires postgresql+asyncpg:// scheme."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        return url

    @property
    def sync_database_url(self) -> str:
        """psycopg2 (used by Celery workers) needs plain postgresql://."""
        url = self.database_url
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        url = url.replace("postgres+asyncpg://", "postgresql://")
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # S3 / MinIO
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "manga-pages"

    # AI
    anthropic_api_key: str = ""

    # Pipeline
    context_window_pages: int = 5
    translation_model: str = "claude-opus-4-5"
    min_ocr_confidence: float = 0.7

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
