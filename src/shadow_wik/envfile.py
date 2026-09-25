"""Read one key from another project's env file, so shared secrets are referenced, not copied."""
from __future__ import annotations

from pathlib import Path


def read_env_key(path: str, key: str) -> str:
    """Return the value of `key` in the dotenv file at `path`; raise ValueError if absent or unreadable."""
    try:
        lines = Path(path).expanduser().read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"envfile.py: cannot read {path}: {exc.strerror}") from exc
    for line in lines:
        name, _, value = line.strip().partition("=")
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    raise ValueError(f"envfile.py: {key} not found in {path}")
