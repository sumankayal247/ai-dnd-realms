import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import FileResponse, StreamingResponse

app = FastAPI(title="AI DnD Realms API", version="1.0.0")

# Same-origin deployment on Vercel does not need CORS, but keeping this permissive
# for local development makes the API easy to test from a local static server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

FREELLMAPI_URL = os.getenv("FREELLMAPI_URL", "http://127.0.0.1:8080").rstrip("/")
FREELLMAPI_API_KEY = os.getenv("FREELLMAPI_API_KEY", "")
DEFAULT_MODEL = os.getenv("FREELLMAPI_MODEL", "auto")
INDEX_FILE = Path(__file__).resolve().parent.parent / "index.html"


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(min_length=1)
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    stream: bool = False


@app.get("/")
async def frontend() -> FileResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=500, detail="Frontend index.html is missing")
    return FileResponse(INDEX_FILE, media_type="text/html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "provider": "freellmapi",
        "configured": bool(FREELLMAPI_API_KEY),
        "model": DEFAULT_MODEL,
    }


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request):
    if not FREELLMAPI_API_KEY:
        raise HTTPException(status_code=500, detail="FREELLMAPI_API_KEY is not configured")

    body: dict[str, Any] = {
        "model": payload.model or DEFAULT_MODEL,
        "messages": payload.messages,
        "stream": payload.stream,
    }
    if payload.temperature is not None:
        body["temperature"] = payload.temperature
    if payload.max_tokens is not None:
        body["max_tokens"] = payload.max_tokens

    headers = {
        "Authorization": f"Bearer {FREELLMAPI_API_KEY}",
        "Content-Type": "application/json",
    }

    url = f"{FREELLMAPI_URL}/v1/chat/completions"

    if payload.stream:
        async def stream_response():
            timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=body, headers=headers) as response:
                    if response.status_code >= 400:
                        detail = (await response.aread()).decode("utf-8", errors="replace")
                        raise RuntimeError(f"FreeLLMAPI returned {response.status_code}: {detail}")
                    async for chunk in response.aiter_bytes():
                        yield chunk

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Unable to reach FreeLLMAPI: {exc}") from exc

    if response.status_code >= 400:
        # Preserve the upstream status while avoiding exposure of our server-side key.
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return response.json()
