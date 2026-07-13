from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DEV_DATABASE_URL: str = "postgresql+asyncpg://user:password@db:5432/app"
    DATABASE_URL: str | None = None
    PROD: bool = False

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL or self.DEV_DATABASE_URL


settings = Settings()