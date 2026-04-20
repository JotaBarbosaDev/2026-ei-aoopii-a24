from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .models import BrandingProfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AgentConfig:
    branding: BrandingProfile
    quality_threshold: float = 8.5
    max_improvement_rounds: int = 2
    generated_dir: Path = PROJECT_ROOT / "data" / "generated"
    public_dir: Path = PROJECT_ROOT / "data" / "public"
    memory_path: Path = PROJECT_ROOT / "data" / "memory" / "executions.jsonl"
    public_base_url: str | None = None


def load_branding_profile(path: Path | str) -> BrandingProfile:
    branding_path = Path(path)
    with branding_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return BrandingProfile.from_dict(payload)


def load_config(
    branding_path: Path | str = PROJECT_ROOT / "config" / "branding.json",
    quality_threshold: float = 8.5,
    max_improvement_rounds: int = 2,
    generated_dir: Path | str | None = None,
    public_dir: Path | str | None = None,
    memory_path: Path | str | None = None,
) -> AgentConfig:
    return AgentConfig(
        branding=load_branding_profile(branding_path),
        quality_threshold=quality_threshold,
        max_improvement_rounds=max_improvement_rounds,
        generated_dir=Path(generated_dir) if generated_dir else PROJECT_ROOT / "data" / "generated",
        public_dir=Path(public_dir) if public_dir else PROJECT_ROOT / "data" / "public",
        memory_path=Path(memory_path) if memory_path else PROJECT_ROOT / "data" / "memory" / "executions.jsonl",
        public_base_url=os.getenv("PUBLIC_BASE_URL"),
    )
