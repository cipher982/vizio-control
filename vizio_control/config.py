"""Configuration management."""

import json
from pathlib import Path
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class TVEntry(BaseModel):
    """Configuration for a single TV."""
    name: str
    host: str
    port: int = 7345
    auth_token: str | None = None


class Settings(BaseSettings):
    """Application settings."""
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080

    # Config file path
    config_file: str = "config.json"

    class Config:
        env_prefix = "VIZIO_"


def load_tvs(config_file: str) -> dict[str, TVEntry]:
    """Load TV configurations from file."""
    path = Path(config_file)
    if not path.exists():
        return {}

    with open(path) as f:
        data = json.load(f)

    return {
        tv_id: TVEntry(**tv_data)
        for tv_id, tv_data in data.get("tvs", {}).items()
    }


def save_tvs(config_file: str, tvs: dict[str, TVEntry]):
    """Save TV configurations to file."""
    path = Path(config_file)
    data = {"tvs": {tv_id: tv.model_dump() for tv_id, tv in tvs.items()}}

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
