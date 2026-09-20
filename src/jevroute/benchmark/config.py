"""Benchmark configuration: typed models and YAML loading.

Every benchmark run must carry its full configuration so results are reproducible.
Configuration must be committed with the benchmark output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RetryConfig(BaseModel):
    max_attempts: int = Field(2, ge=1, le=10)
    backoff_ms: int = Field(250, ge=0)


class MetricsConfig(BaseModel):
    latency: bool = True
    token_usage: bool = True
    cost: bool = True
    accuracy: bool = True
    f1: bool = True
    calibration: bool = True


class ExperimentConfig(BaseModel):
    name: str
    dataset: str
    split: str = "test"
    concurrency: int = Field(8, ge=1, le=64)
    max_examples: int | None = None


class DecisionSchemaConfig(BaseModel):
    version: str = "1.0"


class BenchmarkConfig(BaseModel):
    """Complete benchmark run configuration.

    Must be committed alongside every result bundle for reproducibility.
    """

    experiment: ExperimentConfig
    decision_schema: DecisionSchemaConfig = Field(default_factory=DecisionSchemaConfig)
    routers: list[str] = Field(default_factory=list)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    extra: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path | str) -> "BenchmarkConfig":
        """Load a benchmark configuration from a YAML file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Benchmark config not found: {p}")
        with p.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls.model_validate(raw)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
