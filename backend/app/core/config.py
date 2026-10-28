import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(ROOT_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{ROOT_DIR / 'data' / 'customeriq.db'}"

    def model_post_init(self, __context) -> None:
        # resolve relative sqlite paths against the project root (not cwd)
        if self.database_url.startswith("sqlite:///"):
            raw = self.database_url[len("sqlite:///"):]
            if raw and not Path(raw).is_absolute():
                self.database_url = f"sqlite:///{ROOT_DIR / raw}"
    spark_master: str = "local[2]"
    spark_app_name: str = "CustomerIQ"
    kmeans_k: int = 6
    kmeans_seed: int = 42
    kmeans_max_iter: int = 50
    spark_shuffle_partitions: int = 8
    max_upload_mb: int = 512
    preview_rows: int = 10
    reference_date_policy: str = "dataset_max_plus_one"
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    data_dir: Path = ROOT_DIR / "data"
    raw_dir: Path = ROOT_DIR / "data" / "raw"
    processed_dir: Path = ROOT_DIR / "data" / "processed"
    model_dir: Path = ROOT_DIR / "data" / "models"

    @property
    def sqlite_path(self) -> Path:
        url = self.database_url
        if url.startswith("sqlite:///"):
            p = url[len("sqlite:///"):]
            path = Path(p)
            if not path.is_absolute():
                path = ROOT_DIR / path
            return path
        raise ValueError("Only sqlite:// URLs are supported in local development")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
