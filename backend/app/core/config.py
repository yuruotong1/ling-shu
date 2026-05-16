from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./lingzhu.db"
    sync_database_url: str = "sqlite:///./lingzhu.db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-secret-key"
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost"
    platform_api_key: str = "sk-platform-dev"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
