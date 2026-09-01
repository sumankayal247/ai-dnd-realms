import os
import re
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="AI DnD Realms Chat API", version="1.0.0")
FREELLMAPI_URL = os.getenv("FREELLMAPI_URL", "http://127.0.0.1:8080").rstrip("/")
FREELLMAPI_API_KEY = os.getenv("FREELLMAPI_API_KEY", "")
DEFAULT_MODEL = os.getenv("FREELLMAPI_MODEL", "auto")

ECONOMY_PROTOCOL = """GAME ECONOMY PROTOCOL — NPC CONVERSATIONS:
You are controlling an NPC in a game. The game engine, not the prose, owns inventory, gold, prices, and equipment.
If and ONLY if the NPC genuinely agrees to an economy-changing outcome, append exactly one or more hidden machine tags at the very END of your response, after the dialogue/narration.
- Give coins: [[GOLD:+N]] where N is 1-20.
- Give an item for free: [[GIFT]]. The engine will choose an appropriate item from the NPC's wares when possible.
- Give a merchant discount: [[DISCOUNT:P]] where P is 10-75 percent. Only use this when the NPC actually agrees to lower prices.
- Sharpen/repair/reinforce the player's equipped weapon: [[WEAPON_UPGRADE:N]] where N is 1-5 permanent weapon power.
Never emit a tag when the NPC refuses. Never describe a tag or machine protocol to the player. Do not put tags in code fences.
Example: "Very well, take this draught. [[GIFT]]"
Example: "I'll lower my prices for you. [[DISCOUNT:25]]"
"""

class ChatRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(min_length=1)
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    stream: bool = False

async def call_upstream(payload: dict[str, Any]):
    if not FREELLMAPI_API_KEY:
        raise HTTPException(status_code=500, detail="FREELLMAPI_API_KEY is not configured")
    headers={"Authorization":f"Bearer {FREELLMAPI_API_KEY}","Content-Type":"application/json"}
    timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response=await client.post(f"{FREELLMAPI_URL}/v1/chat/completions",json=payload,headers=headers)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response

def add_protocol(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out=[dict(m) for m in messages]
    system={"role":"system","content":ECONOMY_PROTOCOL}
    for i,m in enumerate(out):
        if m.get("role")=="system":
            out[i]={**m,"content":str(m.get("content", ""))+"\n\n"+ECONOMY_PROTOCOL}
            return out
    return [system]+out

def clean_content(text: str) -> str:
    text=re.sub(r"(?is)<think>.*?</think>","",str(text or ""))
    text=re.sub(r"(?is)<analysis>.*?</analysis>","",text)
    return text.strip()

@app.post("/api/chat")
async def chat(payload: ChatRequest):
    body={"model":DEFAULT_MODEL,"messages":add_protocol(payload.messages),"stream":False}
    if payload.temperature is not None: body["temperature"]=payload.temperature
    if payload.max_tokens is not None: body["max_tokens"]=payload.max_tokens
    response=await call_upstream(body)
    data=response.json()
    for choice in data.get("choices",[]):
        if isinstance(choice,dict) and isinstance(choice.get("message"),dict):
            choice["message"]["content"]=clean_content(choice["message"].get("content",""))
        if isinstance(choice,dict) and isinstance(choice.get("text"),str):
            choice["text"]=clean_content(choice["text"])
    return data

@app.get("/api/health")
async def health():
    return {"ok":True,"provider":"freellmapi","configured":bool(FREELLMAPI_API_KEY),"model":DEFAULT_MODEL}
