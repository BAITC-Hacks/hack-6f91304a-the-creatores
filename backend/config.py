from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    demo_mode: bool = False
    calculation_module: str = "backend.calculations.provider"
    data_dir: Path = Path(".data")
    cors_origins: list[str] = ["http://localhost:5500", "http://127.0.0.1:5500"]
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    openai_timeout_seconds: float = Field(default=30, gt=0, le=120)
    chat_timeout_seconds: float = Field(default=120, gt=0, le=300)
    max_tool_calls: int = Field(default=8, ge=1, le=20)
    max_upload_files: int = Field(default=8, ge=1, le=30)
    max_file_bytes: int = Field(default=10 * 1024**2, ge=1)
    max_request_bytes: int = Field(default=80 * 1024**2, ge=1)
    max_uncompressed_bytes: int = Field(default=50 * 1024**2, ge=1)
    max_workbook_cells: int = Field(default=500_000, ge=1)

    @property
    def ai_configured(self) -> bool:
        return bool(self.openai_api_key.get_secret_value().strip() and self.openai_model.strip())
