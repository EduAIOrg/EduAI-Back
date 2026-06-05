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
    
    # Hugging Face Settings
    HF_TOKEN: str = Field(
        default="",
        description="Hugging Face API Token"
    )
    HF_LLM_MODEL: str = Field(
        default="Qwen/Qwen2.5-7B-Instruct",
        description="Hugging Face LLM model name"
    )
    HF_EMBEDDING_MODEL: str = Field(
        default="intfloat/multilingual-e5-large",
        description="Hugging Face Embedding model name"
    )
    HF_RERANK_MODEL: str = Field(
        default="BAAI/bge-reranker-large",
        description="Hugging Face Rerank model name"
    )
    
    # Local Audio Services (Whisper & XTTS-v2)
    WHISPER_API_URL: str = Field(
        default="http://localhost:8000/v1",
        description="Faster-Whisper OpenAI-compatible API base URL"
    )
    XTTS_API_URL: str = Field(
        default="http://localhost:8020",
        description="XTTS-v2 local API URL"
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
    
    # Supabase Storage
    SUPABASE_URL: str = Field(
        default="",
        description="Supabase project URL"
    )
    SUPABASE_KEY: str = Field(
        default="",
        description="Supabase access key/token"
    )
    SUPABASE_BUCKET: str = Field(
        default="eduai-documents",
        description="Supabase Storage bucket name"
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
