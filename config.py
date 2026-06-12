import os
import tomllib
from pathlib import Path

LING_SHU_DIR = Path(os.environ.get("LING_SHU_DIR", Path.home() / ".ling-shu"))
AGENTS_DIR = LING_SHU_DIR / "agents"
CONFIG_FILE = LING_SHU_DIR / "config.toml"

HOST = os.environ.get("HOST", "0.0.0.0")

_cfg: dict = {}


def load():
    global _cfg
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            _cfg = tomllib.load(f)


def port() -> int:
    return int(_cfg.get("server", {}).get("port", os.environ.get("PORT", 5490)))


def upstream_base_url() -> str:
    return _cfg.get("upstream", {}).get(
        "base_url", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
    ).rstrip("/")


def upstream_api_key() -> str | None:
    return _cfg.get("upstream", {}).get("api_key", os.environ.get("OPENAI_API_KEY"))


def response_format_mode() -> str:
    """Return 'json_schema' or 'json_object'. Use json_object for DeepSeek/most OSS models."""
    return _cfg.get("upstream", {}).get("response_format", "json_schema")


def resolve_model(agent_name: str) -> str:
    """Return the actual upstream model for the given agent name.

    Priority: agents.<name>.model > default.model > agent_name itself.
    """
    agent_cfg = _cfg.get("agents", {}).get(agent_name, {})
    if "model" in agent_cfg:
        return agent_cfg["model"]
    return _cfg.get("default", {}).get("model", agent_name)
