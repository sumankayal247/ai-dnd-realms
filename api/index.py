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
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","), allow_credentials=False, allow_methods=["POST", "GET", "OPTIONS"], allow_headers=["*"])
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
    if not INDEX_FILE.exists(): raise HTTPException(status_code=500, detail="Frontend index.html is missing")
    html = INDEX_FILE.read_text(encoding="utf-8")
    frontend_patch = '''
<style id="backend-model-routing-ui">.field:has(#modelList){display:none!important}</style>
<script>window.getModel=function(){return 'auto'};window.setModel=function(){};window.renderModelList=function(){};</script>
'''
    html = html.replace("</head>", frontend_patch + "</head>", 1)
    rest_patch = '''
<script id="paid-rest-mechanic">
(function(){function install(){if(typeof buildActions!=='function'||typeof btn!=='function'||window.__paidRestInstalled)return;window.__paidRestInstalled=true;const original=buildActions;buildActions=function(room){original(room);add(room)};function add(room){if(!room||(room.type!=='entrance'&&room.type!=='hub')||typeof state==='undefined'||state.mode!=='explore')return;const actions=document.querySelector('#actions');if(!actions||actions.querySelector('[data-action="rest"]'))return;const b=btn('🌙 Rest — 1–2 gold',rest,'small');b.dataset.action='rest';actions.appendChild(b)}function rest(){if(typeof state==='undefined')return;if(state.mode!=='explore'){if(typeof flash==='function')flash('You cannot rest during combat.');return}const room=state.map&&state.map.rooms?state.map.rooms[state.currentId]:null;if(!room||(room.type!=='entrance'&&room.type!=='hub')){if(typeof flash==='function')flash('This is not a safe place to rest.');return}const cost=Math.random()<.5?1:2,p=state.player;if(p.gold<cost){if(typeof flash==='function')flash('Not enough gold for a room tonight (need '+cost+' gold).');return}p.gold-=cost;p.hp=p.maxHp;state.updatedAt=Date.now();state.steps=(state.steps||0)+1;if(typeof addEntry==='function'){addEntry('heal','🌙 You rent a room for the night. After a peaceful rest, your wounds are fully healed.');addEntry('sys','You spend '+cost+' gold. A new day begins.')}if(typeof renderStats==='function')renderStats();if(typeof renderInv==='function')renderInv();if(typeof autosave==='function')autosave();buildActions(room)}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();setTimeout(install,0)})();
</script>
'''
    html = html.replace("</body>", rest_patch + "</body>", 1)
    economy_patch = '''
<script id="persuasion-economy-sync">
(function(){
const RULES=`PERSUASION ECONOMY — IMPORTANT:\n- If the player genuinely persuades an NPC to give coins, append [[GOLD:+N]] as the final hidden tag, N from 1 to 20.\n- If the NPC genuinely gives an item, use [[GIFT]]. Prefer an item from that NPC's own wares when they have wares.\n- If a merchant genuinely lowers prices after persuasion, append [[DISCOUNT:P]] where P is 10 to 75. This discount applies to this NPC's current and future wares for this adventure.\n- Never use a tag unless the NPC has actually agreed. Never mention tags in dialogue.`;
function install(){if(window.__persuasionEconomyInstalled||typeof state==='undefined')return;window.__persuasionEconomyInstalled=true;
function syncWares(npc){if(!npc||!npc._stock)return;const d=Math.max(0,Math.min(75,npc.tradeDiscount||0));npc._stock.forEach(it=>{if(it._basePrice==null&&it.price!=null)it._basePrice=it.price;if(it._basePrice!=null)it.price=Math.max(1,Math.ceil(it._basePrice*(1-d/100)))})}
if(typeof grantPersuadedGift==='function'){const originalGift=grantPersuadedGift;grantPersuadedGift=function(npc){if(npc&&npc._stock&&npc._stock.length){const idx=Math.floor(Math.random()*npc._stock.length),it=npc._stock.splice(idx,1)[0];delete it.price;delete it._basePrice;state.player.inventory.push(it);addEntry('loot','🎁 '+esc(npc.name)+' gives you: '+esc(it.name)+'!');if(it.type==='weapon'&&(!state.player.weapon||it.power>state.player.weapon.power))equip(it);if(it.type==='armor'&&(!state.player.armor||it.power>state.player.armor.power))equip(it);renderInv();renderStats();blip(990);return true}return originalGift(npc)}}
function applyEconomy(text,npc){text=String(text||'');const gm=text.match(/\[\[GOLD:\s*\+?(\d+)\]\]/i),dm=text.match(/\[\[DISCOUNT:\s*(\d+)\]\]/i);const gold=gm?Math.max(1,Math.min(20,parseInt(gm[1],10))):0,discount=dm?Math.max(10,Math.min(75,parseInt(dm[1],10))):0;if(npc){if(gold)state.player.gold+=gold;if(discount)npc.tradeDiscount=Math.max(npc.tradeDiscount||0,discount);syncWares(npc)}return{gold,discount}}
if(typeof applyNpcTags==='function'){const originalTags=applyNpcTags;applyNpcTags=function(text,npc){const result=originalTags(text,npc),e=applyEconomy(text,npc);if(e.gold)addEntry('loot','🪙 '+esc(npc.name)+' gives you '+e.gold+' gold.');if(e.discount)addEntry('sys','🤝 '+esc(npc.name)+' lowers their prices by '+e.discount+'%.');renderStats();return Object.assign(result,{gold:e.gold,discount:e.discount})}}
if(typeof openWares==='function'){const originalOpen=openWares;openWares=function(holder,title){syncWares(holder);return originalOpen(holder,title)}}
if(typeof buyWare==='function'){const originalBuy=buyWare;buyWare=function(i){const holder=state&&state._waresHolder;if(holder)syncWares(holder);return originalBuy(i)}}
function ensureRules(){if(typeof state!=='undefined'&&state.systemPrompt&&!state.systemPrompt.includes('PERSUASION ECONOMY — IMPORTANT'))state.systemPrompt+='\\n\\n'+RULES}ensureRules();setInterval(ensureRules,1000)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();setTimeout(install,0)})();
</script>
'''
    html = html.replace("</body>", economy_patch + "</body>", 1)
    return HTMLResponse(content=html, media_type="text/html")

@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "provider": "freellmapi", "configured": bool(FREELLMAPI_API_KEY), "model": DEFAULT_MODEL}

_REASONING_MARKERS = re.compile(r"(?is)(?:^|\n)\s*(?:here(?:'s| is)\s+(?:a\s+)?(?:thinking|reasoning)\s+process|thinking\s+process\s*:|chain[- ]of[- ]thought\s*:|analysis\s*:|check\s+constraints\s*:|analyze\s+user\s+input\s*:|final\s+answer\s*:).*?(?=\n\s*(?:sable\s*:|narration\s*:|scene\s*:)|\Z)")
def sanitize_narration(text: str) -> str:
    text=str(text or "").strip()
    if not text:return text
    text=re.sub(r"(?is)<think>.*?</think>","",text);text=re.sub(r"(?is)<analysis>.*?</analysis>","",text);text=_REASONING_MARKERS.sub("",text).strip();return re.sub(r"(?is)^\s*(?:final\s+response|narration|scene)\s*:\s*","",text).strip()
def sanitize_response(data: Any) -> Any:
    if not isinstance(data,dict):return data
    result=dict(data);choices=result.get("choices")
    if isinstance(choices,list):
        out=[]
        for choice in choices:
            item=dict(choice) if isinstance(choice,dict) else choice
            if isinstance(item,dict) and isinstance(item.get("message"),dict):
                msg=dict(item["message"])
                if "content" in msg:msg["content"]=sanitize_narration(msg["content"])
                item["message"]=msg
            if isinstance(item,dict) and isinstance(item.get("text"),str):item["text"]=sanitize_narration(item["text"])
            out.append(item)
        result["choices"]=out
    return result

@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request):
    if not FREELLMAPI_API_KEY:raise HTTPException(status_code=500,detail="FREELLMAPI_API_KEY is not configured")
    body={"model":DEFAULT_MODEL,"messages":payload.messages,"stream":payload.stream}
    if payload.temperature is not None:body["temperature"]=payload.temperature
    if payload.max_tokens is not None:body["max_tokens"]=payload.max_tokens
    headers={"Authorization":f"Bearer {FREELLMAPI_API_KEY}","Content-Type":"application/json"};url=f"{FREELLMAPI_URL}/v1/chat/completions"
    if payload.stream:
        async def stream_response():
            timeout=httpx.Timeout(connect=10.0,read=120.0,write=30.0,pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST",url,json=body,headers=headers) as response:
                    if response.status_code>=400:raise RuntimeError(f"FreeLLMAPI returned {response.status_code}: {(await response.aread()).decode('utf-8',errors='replace')}")
                    async for chunk in response.aiter_bytes():yield chunk
        return StreamingResponse(stream_response(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
    try:
        timeout=httpx.Timeout(connect=10.0,read=120.0,write=30.0,pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:response=await client.post(url,json=body,headers=headers)
    except httpx.HTTPError as exc:raise HTTPException(status_code=502,detail=f"Unable to reach FreeLLMAPI: {exc}") from exc
    if response.status_code>=400:raise HTTPException(status_code=response.status_code,detail=response.text)
    return sanitize_response(response.json())
