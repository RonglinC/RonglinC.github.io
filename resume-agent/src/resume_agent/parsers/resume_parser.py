from __future__ import annotations

from pathlib import Path

import yaml

from resume_agent.config import load_resume
from resume_agent.models.resume import Resume


def parse_resume(path: Path) -> Resume:
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return load_resume(path)
    if suffix == ".json":
        import json

        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return Resume.model_validate(data)
    raise ValueError(f"Unsupported resume format: {suffix}. Use .yaml or .json")


def resume_to_yaml(resume: Resume) -> str:
    return yaml.dump(
        resume.model_dump(mode="json", exclude_none=True),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
