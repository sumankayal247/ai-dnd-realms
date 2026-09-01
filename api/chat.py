import os
import re
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="AI DnD Realms Chat API", version="1.1.0")
FREELLMAPI_URL = os.getenv("FREELLMAPI_URL", "http://127.0.0.1:8080").rstrip("/")
FREELLMAPI_API_KEY = os.getenv("FREELLMAPI_API_KEY", "")
DEFAULT_MODEL = os.getenv("FREELLMAPI_MODEL", "auto")

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

async def call_upstream(payload: dict[str, Any]):
    if not FREELLMAPI_API_KEY:
        raise HTTPException(status_code=500, detail="FREELLMAPI_API_KEY is not configured")
    headers={"Authorization":f"Bearer {FREELLMAPI_API_KEY}","Content-Type":"application/json"}
    timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response=await client.post(f"{FREELLMAPI_URL}/v1/chat/completions",json=payload,headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Unable to reach FreeLLMAPI: {exc}") from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
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
    # Remove only obvious leading labels; never greedily delete the answer.
    text=re.sub(r"(?is)^\s*(?:final\s+(?:answer|response)|narration|scene)\s*:\s*", "", text, count=1)
    return text.strip()

def extract_text(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices=data.get("choices")
    if isinstance(choices,list) and choices:
        for choice in choices:
            if not isinstance(choice,dict):
                continue
            message=choice.get("message")
            if isinstance(message,dict):
                content=message.get("content")
                if isinstance(content,str) and content.strip():
                    return clean_content(content)
                if isinstance(content,list):
                    parts=[]
                    for part in content:
                        if isinstance(part,dict) and isinstance(part.get("text"),str):
                            parts.append(part["text"])
                    if parts:
                        return clean_content("".join(parts))
            if isinstance(choice.get("text"),str) and choice["text"].strip():
                return clean_content(choice["text"])
            if isinstance(choice.get("delta"),dict) and isinstance(choice["delta"].get("content"),str):
                return clean_content(choice["delta"]["content"])
    for key in ("output_text","text","content"):
        value=data.get(key)
        if isinstance(value,str) and value.strip():
            return clean_content(value)
    output=data.get("output")
    if isinstance(output,list):
        parts=[]
        for item in output:
            if not isinstance(item,dict):
                continue
            content=item.get("content")
            if isinstance(content,str):
                parts.append(content)
            elif isinstance(content,list):
                for part in content:
                    if isinstance(part,dict) and isinstance(part.get("text"),str):
                        parts.append(part["text"])
        if parts:
            return clean_content("".join(parts))
    return ""

@app.post("/api/chat")
async def chat(payload: ChatRequest):
    body={"model":DEFAULT_MODEL,"messages":add_protocol(payload.messages),"stream":False}
    if payload.temperature is not None: body["temperature"]=payload.temperature
    if payload.max_tokens is not None: body["max_tokens"]=payload.max_tokens
    response=await call_upstream(body)
    data=response.json()
    text=extract_text(data)
    if not text:
        raise HTTPException(status_code=502, detail="AI provider returned no final narration text")
    # Return the OpenAI-compatible shape expected by the existing frontend.
    if isinstance(data,dict) and isinstance(data.get("choices"),list) and data["choices"]:
        first=data["choices"][0]
        if isinstance(first,dict):
            message=first.get("message")
            if isinstance(message,dict):
                message=dict(message)
                message["content"]=text
                first["message"]=message
            else:
                first["message"]={"role":"assistant","content":text}
            return data
    return {"choices":[{"message":{"role":"assistant","content":text}}],"model":DEFAULT_MODEL}

@app.get("/api/health")
async def health():
    return {"ok":True,"provider":"freellmapi","configured":bool(FREELLMAPI_API_KEY),"model":DEFAULT_MODEL}
