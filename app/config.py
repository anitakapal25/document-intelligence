"""Minimal local secret loading; cloud deployments use environment variables."""

import os
from pathlib import Path


def load_local_secret(requested_name: str) -> bool:
    if os.getenv(requested_name):
        return True
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return False
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        if separator and name.strip() == requested_name:
            key = value.strip().strip('"').strip("'")
            if key and key != "replace_me":
                os.environ[requested_name] = key
                return True
    return False


def load_openai_key() -> bool:
    return load_local_secret("OPENAI_API_KEY")
