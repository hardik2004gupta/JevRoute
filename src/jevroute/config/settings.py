"""Application configuration using Pydantic Settings.

Secrets are loaded from environment variables / .env files only.
Never hardcode credentials in this file.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DECISION_SCHEMA_VERSION = "1.0"
POLICY_VERSION = "support-policy-1.0"
APPLICATION_VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    environment: Literal["development", "staging", "production"] = "development"
    app_version: str = APPLICATION_VERSION
    decision_schema_version: str = DECISION_SCHEMA_VERSION
    policy_version: str = POLICY_VERSION

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    # Policy
    hallucination_threshold: float = 0.8

    # Provider credentials — optional, not required for Phase 1 mock path
    jev_api_key: str | None = None
    llm_api_key: str | None = None
    model_name: str | None = None
    model_input_price: float | None = None
    model_output_price: float | None = None
    jev_input_price: float | None = None
    jev_output_price: float | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
