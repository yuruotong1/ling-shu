import json
from pathlib import Path
from config import AGENTS_DIR


def load(name: str) -> tuple[str | None, dict | None]:
    """Return (system_prompt, json_schema) for the named agent, or (None, None) if not found."""
    agent_dir = AGENTS_DIR / name
    if not agent_dir.is_dir():
        return None, None

    prompt: str | None = None
    prompt_file = agent_dir / "prompt.md"
    if prompt_file.exists():
        prompt = prompt_file.read_text(encoding="utf-8").strip()

    schema: dict | None = None
    schema_file = agent_dir / "schema.json"
    if schema_file.exists():
        schema = json.loads(schema_file.read_text(encoding="utf-8"))

    return prompt, schema
