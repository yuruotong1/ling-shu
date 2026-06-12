import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

import agent
import config
from config import AGENTS_DIR, HOST

load_dotenv()


def _init_workspace():
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    if not config.CONFIG_FILE.exists():
        template = Path(__file__).parent / "examples" / "config.toml"
        shutil.copy(template, config.CONFIG_FILE)
        print(f"Created default config: {config.CONFIG_FILE}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_workspace()
    config.load()
    print(f"Agents directory: {AGENTS_DIR}")
    print(f"Config file:      {config.CONFIG_FILE}")
    print(f"Upstream:         {config.upstream_base_url()}")
    async with httpx.AsyncClient(timeout=120) as client:
        app.state.http = client
        yield


app = FastAPI(lifespan=lifespan)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model: str = body.get("model", "")

    prompt, schema = agent.load(model)

    if prompt:
        messages: list = body.setdefault("messages", [])
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = prompt + "\n\n" + messages[0]["content"]
        else:
            messages.insert(0, {"role": "system", "content": prompt})

    if schema is not None:
        if config.response_format_mode() == "json_object":
            # DeepSeek / most OSS models: inject schema into system prompt
            import json as _json
            schema_hint = f"\nRespond with valid JSON matching this schema:\n```json\n{_json.dumps(schema.get('schema', schema), ensure_ascii=False, indent=2)}\n```"
            messages: list = body.setdefault("messages", [])
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] += schema_hint
            else:
                messages.insert(0, {"role": "system", "content": schema_hint})
            body["response_format"] = {"type": "json_object"}
        else:
            body["response_format"] = {"type": "json_schema", "json_schema": schema}

    body["model"] = config.resolve_model(model)

    upstream_url = f"{config.upstream_base_url()}/v1/chat/completions"
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() in ("openai-organization", "openai-project")
    }
    if config.upstream_api_key():
        headers["Authorization"] = f"Bearer {config.upstream_api_key()}"

    stream: bool = body.get("stream", False)
    client: httpx.AsyncClient = request.app.state.http

    if stream:
        async def event_stream():
            async with client.stream("POST", upstream_url, json=body, headers=headers) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    resp = await client.post(upstream_url, json=body, headers=headers)
    return Response(content=resp.content, status_code=resp.status_code, media_type="application/json")


@app.get("/v1/models")
async def list_models():
    """List available agents as model objects."""
    models = []
    if AGENTS_DIR.is_dir():
        for d in sorted(AGENTS_DIR.iterdir()):
            if d.is_dir():
                models.append({"id": d.name, "object": "model", "owned_by": "ling-shu"})
    return {"object": "list", "data": models}


if __name__ == "__main__":
    config.load()
    uvicorn.run("main:app", host=HOST, port=config.port(), reload=True)
