from pydantic_settings import BaseSettings 
from functools import lru_cache

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    primary_model: str = "gpt-4-0613"
    fallback_model: str = "gpt-3.5-turbo-0613"

    LANGCHAIN_TRACING_V2: bool = True
    LANGSMITH_API_KEY: str
    LANGSMITH_PROJECT: str
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    RATE_LIMIT: str = "20/minute"
    CACHE_TLL_SECONDS: int = 300
    MAX_RETRIES: int = 3

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"
    
@lru_cache
def get_settings() -> Settings:
    """Cached setings - only load once, reuse everywhere"""
    return Settings()