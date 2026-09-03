# AI DnD Realms v3 — Reforged

This is the production-oriented frontend vertical slice added without changing the existing backend.

## Implemented

- Deterministic command/rules engine; AI cannot directly mutate stats.
- Event history/audit stream with typed gameplay events.
- Data-driven abilities, enemies, items, equipment and quests.
- d20 checks with natural 20 / natural 1 handling.
- Combat with abilities, armor, critical hits, resources, defeat/recovery and loot.
- XP, level progression, equipment and consumables.
- Quest objectives, progress and rewards.
- Factions and reputation.
- Persistent NPC relationship/memory model.
- Lightweight world simulation, threat and dynamic encounter selection.
- Campaign creation and background-dependent starting state.
- Versioned local save plus IndexedDB autosave repository.
- Structured AI director boundary with compact context, timeout and local fallback.
- Phaser presentation layer kept separate from simulation state.
- Responsive DOM HUD and narrative interface.
- Debug/audit surface for development.

## Backend boundary

No backend source or endpoint was modified. The AI adapter continues to target the existing `/api/chat` contract. If the browser is hosted separately from the API, set `localStorage.AI_DND_API_BASE` to the API origin.

## Production limitations that require backend permission later

A static client cannot provide authoritative anti-cheat, cross-device cloud saves, secure server-side progression, request idempotency or authoritative multiplayer. Those are deliberately not faked in this release.

## Runtime

Open `upgrade/v3/index.html` from a web server. Phaser is currently loaded from jsDelivr for this migration slice; the next packaging step should bundle Phaser and TypeScript with Vite for immutable production assets, automated tests and CI.
