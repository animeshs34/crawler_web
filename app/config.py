from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Web Crawler API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    request_timeout: int = 30
    max_content_length: int = 10_000_000
    user_agent: str = "WebCrawler/1.0 (SEO Metadata Extractor)"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
