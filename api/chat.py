import os
import re
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="AI DnD Realms Chat API", version="1.3.1")
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS or ["*"], allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])

# FreeLLMAPI Render deployment. Override with FREELLMAPI_URL in production if needed.
FREELLMAPI_URL = os.getenv("FREELLMAPI_URL", "https://freellmapi-dnd.onrender.com").rstrip("/")
for suffix in ("/v1/chat/completions", "/v1"):
    if FREELLMAPI_URL.lower().endswith(suffix):
        FREELLMAPI_URL = FREELLMAPI_URL[: -len(suffix)].rstrip("/")
        break
FREELLMAPI_API_KEY = os.getenv("FREELLMAPI_API_KEY", "")
DEFAULT_MODEL = os.getenv("FREELLMAPI_MODEL", "auto")
UPSTREAM_CHAT_PATH = "/v1/chat/completions"

ECONOMY_PROTOCOL = """GAME ECONOMY PROTOCOL — NPC CONVERSATIONS:
You are controlling an NPC in a game. The game engine, not the prose, owns inventory, gold, prices, and equipment.
If and ONLY if the NPC genuinely agrees to an economy-changing outcome, append the appropriate hidden machine tag at the VERY END of your response, after the dialogue/narration.
- Give coins: [[GOLD:+N]] where N is 1-20.
- Give an item for free: [[GIFT]]. The engine will choose an appropriate item from the NPC's wares when possible.
- Give a merchant discount: [[DISCOUNT:P]] where P is 10-75 percent. Only use this when the NPC actually agrees to lower prices.
- Sharpen/repair/reinforce the player's equipped weapon: [[WEAPON_UPGRADE:N]] where N is 1-5 permanent weapon power.
Never emit a tag when the NPC refuses. Never describe a tag or machine protocol to the player. Do not put tags in code fences.
"""

class ChatRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(min_length=1)
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    stream: bool = False


def safe_provider_url() -> str:
    return FREELLMAPI_URL


def upstream_error(response: httpx.Response) -> HTTPException:
    detail = response.text.strip()
    if len(detail) > 1200:
        detail = detail[:1200] + "…"
    status = response.status_code
    return HTTPException(status_code=502, detail={
        "stage": "upstream",
        "status": status,
        "message": f"FreeLLMAPI rejected POST {UPSTREAM_CHAT_PATH} with HTTP {status}.",
        "endpoint": f"{safe_provider_url()}{UPSTREAM_CHAT_PATH}",
        "upstream_response": detail or "<empty response>",
        "hint": "The supplied /models/chat URL is a dashboard/model page. The API-compatible chat endpoint is /v1/chat/completions.",
    })


async def call_upstream(payload: dict[str, Any]):
    if not FREELLMAPI_API_KEY:
        raise HTTPException(status_code=503, detail={"stage":"configuration","status":503,"message":"FREELLMAPI_API_KEY is not configured on the backend."})
    headers={"Authorization":f"Bearer {FREELLMAPI_API_KEY}","Content-Type":"application/json"}
    endpoint=f"{FREELLMAPI_URL}{UPSTREAM_CHAT_PATH}"
    timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response=await client.post(endpoint,json=payload,headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail={"stage":"upstream","status":502,"message":"Backend could not reach FreeLLMAPI.","endpoint":endpoint,"error":str(exc)}) from exc
    if response.status_code >= 400:
        raise upstream_error(response)
    return response


def add_protocol(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out=[dict(m) for m in messages]
    for i,m in enumerate(out):
        if m.get("role")=="system":
            out[i]={**m,"content":str(m.get("content", ""))+"\n\n"+ECONOMY_PROTOCOL}
            return out
    return [{"role":"system","content":ECONOMY_PROTOCOL}]+out


def clean_content(text: str) -> str:
    text=re.sub(r"(?is)<think>.*?</think>","",str(text or ""))
    text=re.sub(r"(?is)<analysis>.*?</analysis>","",text)
    text=re.sub(r"(?is)^\s*(?:final\s+(?:answer|response)|narration|scene)\s*:\s*", "", text, count=1)
    return text.strip()


def extract_text(data: Any) -> str:
    if not isinstance(data, dict): return ""
    choices=data.get("choices")
    if isinstance(choices,list) and choices:
        for choice in choices:
            if not isinstance(choice,dict): continue
            message=choice.get("message")
            if isinstance(message,dict):
                content=message.get("content")
                if isinstance(content,str) and content.strip(): return clean_content(content)
                if isinstance(content,list):
                    parts=[part["text"] for part in content if isinstance(part,dict) and isinstance(part.get("text"),str)]
                    if parts: return clean_content("".join(parts))
            if isinstance(choice.get("text"),str) and choice["text"].strip(): return clean_content(choice["text"])
    for key in ("output_text","text","content"):
        value=data.get(key)
        if isinstance(value,str) and value.strip(): return clean_content(value)
    return ""


@app.post("/")
@app.post("/api/chat")
async def chat(payload: ChatRequest):
    body={"model":payload.model or DEFAULT_MODEL,"messages":add_protocol(payload.messages),"stream":False}
    if payload.temperature is not None: body["temperature"]=payload.temperature
    if payload.max_tokens is not None: body["max_tokens"]=payload.max_tokens
    response=await call_upstream(body)
    try: data=response.json()
    except ValueError as exc: raise HTTPException(status_code=502,detail={"stage":"upstream","status":502,"message":"FreeLLMAPI returned invalid JSON","endpoint":f"{safe_provider_url()}{UPSTREAM_CHAT_PATH}"}) from exc
    text=extract_text(data)
    if not text: raise HTTPException(status_code=502,detail={"stage":"upstream","status":502,"message":"FreeLLMAPI returned no final narration text","endpoint":f"{safe_provider_url()}{UPSTREAM_CHAT_PATH}"})
    if isinstance(data,dict) and isinstance(data.get("choices"),list) and data["choices"]:
        first=data["choices"][0]
        if isinstance(first,dict):
            message=first.get("message")
            if isinstance(message,dict):
                message=dict(message); message["content"]=text; first["message"]=message
            else: first["message"]={"role":"assistant","content":text}
            return data
    return {"choices":[{"message":{"role":"assistant","content":text}}],"model":payload.model or DEFAULT_MODEL}


@app.get("/health")
@app.get("/api/health")
async def health():
    return {"ok":True,"stage":"backend","provider":"freellmapi","configured":bool(FREELLMAPI_API_KEY),"model":DEFAULT_MODEL,"upstream_base":safe_provider_url(),"chat_endpoint":f"{safe_provider_url()}{UPSTREAM_CHAT_PATH}","cors":CORS_ORIGINS}
