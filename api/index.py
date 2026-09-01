import os
import re
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import HTMLResponse, StreamingResponse

app = FastAPI(title="AI DnD Realms API", version="1.0.0")

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
async def frontend() -> HTMLResponse:
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=500, detail="Frontend index.html is missing")

    html = INDEX_FILE.read_text(encoding="utf-8")
    frontend_patch = """
<style id="backend-model-routing-ui">
  .field:has(#modelList) { display: none !important; }
</style>
<script>
  window.getModel = function(){ return 'auto'; };
  window.setModel = function(){};
  window.renderModelList = function(){};
</script>
"""
    html = html.replace("</head>", frontend_patch + "</head>", 1)

    rest_patch = """
<script id="paid-rest-mechanic">
(function(){
  function installPaidRest(){
    if(typeof buildActions !== 'function' || typeof btn !== 'function') return;
    if(window.__paidRestInstalled) return;
    window.__paidRestInstalled = true;

    const originalBuildActions = buildActions;
    buildActions = function(room){
      originalBuildActions(room);
      addRestAction(room);
    };

    function addRestAction(room){
      if(!room || (room.type !== 'entrance' && room.type !== 'hub')) return;
      if(typeof state === 'undefined' || state.mode !== 'explore') return;

      const actions = document.querySelector('#actions');
      if(!actions || actions.querySelector('[data-action="rest"]')) return;

      const restButton = btn('🌙 Rest — 1–2 gold', restAtSafeSpace, 'small');
      restButton.dataset.action = 'rest';
      actions.appendChild(restButton);
    }

    function restAtSafeSpace(){
      if(typeof state === 'undefined') return;
      if(state.mode !== 'explore'){
        if(typeof flash === 'function') flash('You cannot rest during combat.');
        return;
      }

      const room = state.map && state.map.rooms ? state.map.rooms[state.currentId] : null;
      if(!room || (room.type !== 'entrance' && room.type !== 'hub')){
        if(typeof flash === 'function') flash('This is not a safe place to rest.');
        return;
      }

      const cost = Math.random() < 0.5 ? 1 : 2;
      const player = state.player;
      if(player.gold < cost){
        if(typeof flash === 'function') flash('Not enough gold for a room tonight (need '+cost+' gold).');
        return;
      }

      player.gold -= cost;
      player.hp = player.maxHp;
      state.updatedAt = Date.now();
      state.steps = (state.steps || 0) + 1;

      if(typeof addEntry === 'function'){
        addEntry('heal', '🌙 You rent a room for the night. After a peaceful rest, your wounds are fully healed.');
        addEntry('sys', 'You spend '+cost+' gold. A new day begins.');
      }
      if(typeof renderStats === 'function') renderStats();
      if(typeof renderInv === 'function') renderInv();
      if(typeof autosave === 'function') autosave();
      buildActions(room);
    }
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installPaidRest);
  else installPaidRest();
  setTimeout(installPaidRest, 0);
})();
</script>
"""
    html = html.replace("</body>", rest_patch + "</body>", 1)
    return HTMLResponse(content=html, media_type="text/html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "provider": "freellmapi",
        "configured": bool(FREELLMAPI_API_KEY),
        "model": DEFAULT_MODEL,
    }


# Defensive output filter. The game must display only final in-world narration,
# never a provider's analysis, chain-of-thought, prompt reconstruction, or meta text.
_REASONING_MARKERS = re.compile(
    r"(?is)(?:^|\n)\s*(?:here(?:'s| is)\s+(?:a\s+)?(?:thinking|reasoning)\s+process|"
    r"thinking\s+process\s*:|chain[- ]of[- ]thought\s*:|analysis\s*:|"
    r"check\s+constraints\s*:|analyze\s+user\s+input\s*:|final\s+answer\s*:).*?(?=\n\s*(?:sable\s*:|narration\s*:|scene\s*:)|\Z)"
)


def sanitize_narration(text: str) -> str:
    """Return player-visible narration without leaked reasoning/meta-instructions."""
    text = str(text or "").strip()
    if not text:
        return text

    text = re.sub(r"(?is)<think>.*?</think>", "", text)
    text = re.sub(r"(?is)<analysis>.*?</analysis>", "", text)
    text = _REASONING_MARKERS.sub("", text).strip()
    text = re.sub(r"(?is)^\s*(?:final\s+response|narration|scene)\s*:\s*", "", text).strip()
    return text


def sanitize_response(data: Any) -> Any:
    """Sanitize OpenAI-compatible chat completion message content recursively."""
    if isinstance(data, dict):
        result = dict(data)
        choices = result.get("choices")
        if isinstance(choices, list):
            new_choices = []
            for choice in choices:
                item = dict(choice) if isinstance(choice, dict) else choice
                if isinstance(item, dict) and isinstance(item.get("message"), dict):
                    msg = dict(item["message"])
                    if "content" in msg:
                        msg["content"] = sanitize_narration(msg["content"])
                    item["message"] = msg
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    item["text"] = sanitize_narration(item["text"])
                new_choices.append(item)
            result["choices"] = new_choices
        return result
    return data


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request):
    if not FREELLMAPI_API_KEY:
        raise HTTPException(status_code=500, detail="FREELLMAPI_API_KEY is not configured")

    # The browser cannot choose the provider/model. FreeLLMAPI/backend routing
    # decides which available AI handles the request.
    body: dict[str, Any] = {
        "model": DEFAULT_MODEL,
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
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return sanitize_response(response.json())
