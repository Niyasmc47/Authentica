import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Authentica Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Validation settings (configurable via environment variables)
    MAX_FILE_SIZE_MB: int = 100
    MAX_DURATION_SECONDS: float = 90.0
    
    ALLOWED_EXTENSIONS: set[str] = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    ALLOWED_MIME_TYPES: set[str] = {
        "video/mp4",
        "video/x-msvideo",
        "video/quicktime",
        "video/x-matroska",
        "video/webm",
        "application/octet-stream",  # often sent by generic HTTP clients for binary video
    }
    
    # Video sampling settings
    FRAME_SAMPLE_FPS: float = 1.0  # Sample approx 1 frame per second
    
    # Temporary workspace root directory
    TEMP_DIR: Path = Path(__file__).resolve().parent.parent.parent / "temp"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


settings = Settings()

# Ensure base temp directory exists
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
