from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "production", "testing"] = "development"

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    llm_provider: Literal["ollama", "openai"] = "ollama"

    ocr_engine: Literal["tesseract", "easyocr"] = "tesseract"
    tesseract_languages: str = "eng+deu+fra"

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    max_file_size_mb: int = 10

    kaggle_username: str | None = None
    kaggle_key: str | None = None

    enable_provider_database: bool = True
    database_url: str = "sqlite:///./data/providers.db"

    @property
    def use_openai(self) -> bool:
        """Check if OpenAI is configured and should be used."""
        return bool(self.openai_api_key) and self.llm_provider == "openai"


settings = Settings()
