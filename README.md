# AI DnD Realms 🎲

An AI-native, browser-based D&D-style RPG with deterministic game systems and an AI world director.

Pick a realm (Fantasy, Sci-Fi, Horror, Noir, Post-Apocalyptic, or a custom setting), interact with persistent NPCs, explore a simulated world, manage quests and factions, and fight using deterministic rules with AI-driven narrative presentation.

## ▶️ Play it live

**Production / recommended:** https://ai-dnd-realms.vercel.app/

The production deployment uses the Vercel backend for AI requests. The GitHub Pages deployment is a static frontend and does **not** execute the FastAPI backend, so its `/api/chat` route cannot provide the same server-side AI connection.

## AI architecture

```text
Browser
   ↓
Vercel /api/chat
   ↓
AI DnD FastAPI backend
   ↓
FreeLLMAPI
https://**********-***.onrender.com/v1/chat/completions
   ↓
Configured AI provider/model
```

The FreeLLMAPI server is used as the upstream OpenAI-compatible AI gateway. The browser does not need access to the FreeLLMAPI secret key.

### Backend configuration

The backend expects these environment variables:

```env
FREELLMAPI_URL=https://**********-***.onrender.com
FREELLMAPI_API_KEY=<your FreeLLMAPI unified key>
FREELLMAPI_MODEL=auto
```

`FREELLMAPI_API_KEY` must be configured in the deployment environment and must **not** be committed to GitHub or exposed in frontend code.

## How to play

1. Open the production Vercel link above.
2. Start a new adventure.
3. Choose a realm and character/background.
4. Explore, talk, fight, complete quests, manage equipment, and shape the world through your decisions.

## Game architecture

The upgraded runtime separates presentation, deterministic simulation, persistence, and AI narration:

- **Command system** — player actions are normalized before execution.
- **Deterministic rules engine** — authoritative HP, damage, inventory, equipment, quests, rewards, and progression are calculated in code.
- **Event/history system** — important actions produce structured events for replay, memory, and debugging.
- **Combat system** — deterministic combat rules with AI used for narrative framing rather than authoritative game-state mutation.
- **Quest system** — objectives, progress, rewards, and active/completed quest state.
- **NPC memory & relationships** — NPC trust, relationships, knowledge, and recent memories persist in campaign state.
- **Faction/reputation system** — world factions track player standing and consequences.
- **World simulation** — day, weather, threat, flags, and other world state can evolve independently of narration.
- **Dynamic encounters** — encounters are selected from game state instead of being hard-coded solely into AI prose.
- **Inventory/equipment/loot** — deterministic item ownership, equipment, rewards, and progression.
- **AI world director** — generates concise narration, dialogue, and plausible choices while respecting established state.
- **Context/memory budgeting** — only relevant state and recent memories are supplied to the AI to control context growth.
- **Persistence** — local campaign state uses browser persistence with LocalStorage/IndexedDB support.
- **Offline fallback** — core gameplay remains usable when the AI service is unavailable.

### Core rule

> **AI proposes possibilities; the deterministic game engine creates authoritative reality.**

The AI must not directly award items, change HP, complete quests, or mutate player statistics merely by claiming that it happened in narration.

## Project structure

The original single-file prototype remains available at the repository root. The upgraded modular runtime lives under `upgrade/v3/`.

```text
.
├── index.html              # Main/static frontend entry
├── api/
│   ├── chat.py             # Server-side AI proxy /api/chat
│   └── index.py            # FastAPI application entrypoint
├── upgrade/
│   ├── ARCHITECTURE.md
│   ├── README.md
│   └── v3/
│       ├── index.html
│       ├── game.js
│       ├── engine.js
│       ├── data.js
│       ├── ai.js
│       ├── systems.js
│       ├── persistence.js
│       ├── renderer.js
│       └── selftest.js
├── requirements.txt
└── vercel.json
```

## Security

- AI provider credentials are kept server-side through environment variables.
- Do not commit `FREELLMAPI_API_KEY` or any other provider secret.
- The browser communicates with the AI DnD backend rather than receiving the upstream provider secret.
- CORS is configured by the backend for browser requests.

## GitHub Pages vs Vercel

GitHub Pages is suitable for the static frontend, but it cannot run the Python/FastAPI backend contained in `api/`. Therefore the **Vercel deployment is the supported production deployment for the AI-powered version**.

If the GitHub Pages URL is used, the static frontend may load, but server-side `/api/chat` functionality is not available there unless a separate backend is configured and the frontend is explicitly pointed at it.

## Development

Install the Python dependencies for the FastAPI backend:

```bash
pip install -r requirements.txt
```

Configure the required environment variables, then run the FastAPI application using your preferred ASGI server/deployment platform.

For the browser runtime, the project remains compatible with a static frontend workflow; the production AI path should use the deployed `/api/chat` backend.
