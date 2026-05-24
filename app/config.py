"""Application configuration using Pydantic Settings."""
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://eduai:eduai_password@localhost:5432/eduai",
        description="PostgreSQL database URL with asyncpg driver"
    )
    
    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for Celery and caching"
    )
    
    # Security
    SECRET_KEY: str = Field(
        default="your-super-secret-key-min-32-chars-change-this-in-production",
        description="Secret key for JWT token generation"
    )
    ACCESS_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="JWT access token expiration in days"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=30,
        description="JWT refresh token expiration in days"
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT algorithm"
    )
    
    # OpenAI
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key"
    )
    
    # Ollama
    USE_OLLAMA: bool = Field(
        default=False,
        description="Use Ollama instead of OpenAI"
    )
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama base URL"
    )
    OLLAMA_MODEL: str = Field(
        default="llama3",
        description="Ollama model name"
    )
    OLLAMA_EMBEDDING_MODEL: str = Field(
        default="nomic-embed-text",
        description="Ollama embedding model"
    )
    
    # CORS
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated list of allowed CORS origins"
    )
    
    # Upload
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=50,
        description="Maximum upload file size in MB"
    )
    UPLOADS_DIR: str = Field(
        default="./uploads",
        description="Directory for uploaded files"
    )
    
    # ChromaDB
    CHROMA_DB_DIR: str = Field(
        default="./chroma_db",
        description="ChromaDB persistence directory"
    )
    
    # Celery
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/0",
        description="Celery result backend URL"
    )
    
    # App
    APP_NAME: str = Field(
        default="EduAI Africa",
        description="Application name"
    )
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Application version"
    )
    DEBUG: bool = Field(
        default=False,
        description="Debug mode"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def parse_origins(cls, v: str) -> List[str]:
        """Parse comma-separated origins into a list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Get allowed origins as a list."""
        if isinstance(self.ALLOWED_ORIGINS, list):
            return self.ALLOWED_ORIGINS
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


# Global settings instance
settings = Settings()
