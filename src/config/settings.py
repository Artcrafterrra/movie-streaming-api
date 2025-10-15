import os
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class BaseAppSettings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "developing")

    BASE_DIR: Path = Path(__file__).parent.parent
    PATH_TO_DB: str = str(BASE_DIR / "database" / "source" / "theater.db")
    PATH_TO_MOVIES_CSV: str = str(
        BASE_DIR / "database" / "seed_data" / "imdb_movies.csv"
    )

    PATH_TO_EMAIL_TEMPLATES_DIR: str = str(
        BASE_DIR / "notifications" / "templates"
    )
    ACTIVATION_EMAIL_TEMPLATE_NAME: str = "activation_request.html"
    ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME: str = "activation_complete.html"
    PASSWORD_RESET_TEMPLATE_NAME: str = "password_reset_request.html"
    PASSWORD_RESET_COMPLETE_TEMPLATE_NAME: str = "password_reset_complete.html"

    LOGIN_TIME_DAYS: int = 7

    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "host")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", 25))
    EMAIL_HOST_USER: str = os.getenv("EMAIL_HOST_USER", "testuser")
    EMAIL_HOST_PASSWORD: str = os.getenv(
        "EMAIL_HOST_PASSWORD", "test_password"
    )
    EMAIL_USE_TLS: bool = os.getenv("EMAIL_USE_TLS", "False").lower() == "true"
    MAILHOG_API_PORT: int = os.getenv("MAILHOG_API_PORT", 8025)

    HOST_NAME: str = os.getenv("HOST_NAME", "127.0.0.1:8000")

    # S3 Configuration - flexible for both MinIO and AWS S3
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_STORAGE_HOST: str = os.getenv(
        "S3_STORAGE_HOST", os.getenv("MINIO_HOST", "")
    )
    S3_STORAGE_PORT: int = int(
        os.getenv("S3_STORAGE_PORT", os.getenv("MINIO_PORT", 9000))
    )
    S3_STORAGE_ACCESS_KEY: str = os.getenv(
        "AWS_ACCESS_KEY_ID", os.getenv("MINIO_ROOT_USER", "minioadmin")
    )
    S3_STORAGE_SECRET_KEY: str = os.getenv(
        "AWS_SECRET_ACCESS_KEY",
        os.getenv("MINIO_ROOT_PASSWORD", "some_password"),
    )
    S3_BUCKET_NAME: str = os.getenv(
        "S3_BUCKET_NAME", os.getenv("MINIO_STORAGE", "theater-storage")
    )
    S3_USE_SSL: bool = os.getenv("S3_USE_SSL", "False").lower() == "true"

    @property
    def S3_STORAGE_ENDPOINT(self) -> str | None:  # NOQA N802
        """
        Returns S3 endpoint URL for custom S3-compatible services (like MinIO).
        Returns None for AWS S3 (uses default endpoints).
        """
        if not self.S3_STORAGE_HOST:
            return None  # Use default AWS S3 endpoints

        protocol = "https" if self.S3_USE_SSL else "http"
        if self.S3_STORAGE_PORT in [80, 443]:
            return f"{protocol}://{self.S3_STORAGE_HOST}"
        return f"{protocol}://{self.S3_STORAGE_HOST}:{self.S3_STORAGE_PORT}"


class Settings(BaseAppSettings):
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "test_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "test_password")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "test_host")
    POSTGRES_DB_PORT: int = int(os.getenv("POSTGRES_DB_PORT", 5432))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "test_db")

    SECRET_KEY_ACCESS: str = os.getenv(
        "SECRET_KEY_ACCESS", os.urandom(32).hex()
    )
    SECRET_KEY_REFRESH: str = os.getenv(
        "SECRET_KEY_REFRESH", os.urandom(32).hex()
    )
    JWT_SIGNING_ALGORITHM: str = os.getenv("JWT_SIGNING_ALGORITHM", "HS256")


class TestingSettings(BaseAppSettings):
    SECRET_KEY_ACCESS: str = "SECRET_KEY_ACCESS"
    SECRET_KEY_REFRESH: str = "SECRET_KEY_REFRESH"
    JWT_SIGNING_ALGORITHM: str = "HS256"

    def model_post_init(self, __context: dict[str, Any] | None = None) -> None:
        object.__setattr__(self, "PATH_TO_DB", ":memory:")
        object.__setattr__(
            self,
            "PATH_TO_MOVIES_CSV",
            str(self.BASE_DIR / "database" / "seed_data" / "test_data.csv"),
        )


base_app_settings = BaseAppSettings()
