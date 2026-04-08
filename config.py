"""
Configuration module for SentinelFlow.

Centralized configuration for all application settings.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database Configuration
    instance_connection_name: Optional[str] = Field(
        default=None, env="INSTANCE_CONNECTION_NAME", description="AlloyDB instance in format project_id:region:instance"
    )
    project_id: Optional[str] = Field(
        default=None, env="PROJECT_ID", description="Google Cloud Project ID"
    )
    db_user: str = Field(default="postgres", env="DB_USER")
    db_pass: str = Field(default="", env="DB_PASS")
    db_name: str = Field(default="sentinelflow", env="DB_NAME")

    # Local Database (for development)
    local_db: bool = Field(default=False, env="LOCAL_DB")
    db_host: str = Field(default="localhost", env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT")

    # API Configuration
    port: int = Field(default=8080, env="PORT")
    debug: bool = Field(default=False, env="DEBUG")
    reload: bool = Field(default=False, env="RELOAD")

    # Database Configuration
    sql_echo: bool = Field(default=False, env="SQL_ECHO")
    pool_size: int = Field(default=20, env="POOL_SIZE")
    max_overflow: int = Field(default=40, env="MAX_OVERFLOW")

    # Vertex AI Configuration
    vertex_ai_model: str = Field(default="gemini-1.5-pro", env="VERTEX_AI_MODEL")
    embedding_model: str = Field(
        default="text-embedding-004", env="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(default=768, env="EMBEDDING_DIMENSION")

    # Google Cloud Configuration
    # Note: Authentication uses Application Default Credentials (ADC)
    # Set via: gcloud auth application-default login (local)
    # or attached service account (Cloud Run)
    google_cloud_project: Optional[str] = Field(
        default=None, env="PROJECT_ID"
    )

    # Application Configuration
    app_name: str = "SentinelFlow"
    app_version: str = "0.1.0"
    app_description: str = (
        "AI-driven multi-agent task managing system"
    )

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_database_url(self) -> str:
        """Get the database connection URL."""
        if self.local_db:
            # Local PostgreSQL connection
            return (
                f"postgresql+pg8000://{self.db_user}:{self.db_pass}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        else:
            # AlloyDB connection (requires connector)
            return "postgresql+pg8000://"


# Global settings instance
settings = Settings()


def print_settings():
    """Print current settings (without sensitive information)."""
    print("\n" + "=" * 70)
    print("SentinelFlow Configuration")
    print("=" * 70)
    print(f"App: {settings.app_name} v{settings.app_version}")
    print(f"Port: {settings.port}")
    print(f"Debug: {settings.debug}")
    print(f"Database: {settings.db_name}@{settings.db_host or 'AlloyDB'}")
    print(f"Vertex AI Model: {settings.vertex_ai_model}")
    print(f"Embedding Model: {settings.embedding_model} ({settings.embedding_dimension}D)")
    print(f"SQL Echo: {settings.sql_echo}")
    print("=" * 70 + "\n")
