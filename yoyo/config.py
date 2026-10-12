from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://yoyo:yoyo_local@localhost:55432/yoyo"
    artifact_dir: Path = ROOT / "artifacts"
    langsmith_api_key: str = ""
    langsmith_project: str = "yoyo-local"
    langsmith_tracing: bool = True
    openai_api_key: str = ""
    model: str = ""
    exa_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")


settings = Settings()
