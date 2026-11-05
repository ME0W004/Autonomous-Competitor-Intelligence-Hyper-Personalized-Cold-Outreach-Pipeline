import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM Configuration
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.2

    # Crawler Settings
    CRAWLER_HEADLESS: bool = True
    CRAWLER_CONCURRENCY: int = 5
    CRAWLER_PAGE_TIMEOUT_MS: int = 30000
    CRAWLER_WORD_COUNT_THRESHOLD: int = 15
    MAX_SUBPAGES_PER_DOMAIN: int = 3
    CRAWLER_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    # Pipeline Settings
    DEFAULT_OUTREACH_LANGUAGE: str = "en"  # "en" or "fa"
    RATE_LIMIT_DELAY_SECONDS: float = 1.0

    # Paths
    BASE_DIR: Path = BASE_DIR
    INPUT_DIR: Path = BASE_DIR / "data" / "input"
    OUTPUT_DIR: Path = BASE_DIR / "data" / "output"
    LOGS_DIR: Path = BASE_DIR / "data" / "logs"
    CONFIG_DIR: Path = BASE_DIR / "config"
    PORTFOLIO_FILE: Path = BASE_DIR / "config" / "our_portfolio.json"

settings = Settings()
