from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_VERSION: str = "1.0.0"
    DATABASE_URL: str = "postgresql+asyncpg://nexorum:nexorum@localhost/nexorum"
    REDIS_URL: str = "redis://localhost:6379/0"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    SECRET_KEY: str = "dev-secret"
    DEFAULT_AI_MODEL: str = "gpt-4o"
    MAX_CONTEXT_TOKENS: int = 128000
    STRATEGY_GENERATION_TEMP: float = 0.2

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
