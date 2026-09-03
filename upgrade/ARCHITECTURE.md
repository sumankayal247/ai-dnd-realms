# AI DnD Realms — Production Architecture

## Current implementation boundary

The existing backend is intentionally unchanged. It exposes an OpenAI-compatible `POST /api/chat` plus health, and proxies requests to FreeLLMAPI. The production frontend therefore treats AI as a **narrative adapter**, never as the authoritative game-state engine.

The new `upgrade/index.html` implements the browser-side vertical slice with:

- deterministic d20 checks and combat math;
- character progression, XP, levels and stats;
- inventory, equipment and consumables;
- temporary conditions;
- faction reputation and world flags;
- threat/day progression;
- branching AI-generated choices;
- local AI fallback when the network/provider fails;
- local save/load with corruption recovery;
- DOM HUD + Phaser render surface;
- Web Audio/Phaser-ready renderer boundary;
- responsive desktop/mobile layout.

## Runtime architecture

```text
                    +---------------------------+
                    |      Browser Shell        |
                    | DOM HUD / accessibility   |
                    +-------------+-------------+
                                  |
                    +-------------v-------------+
                    |      Game State Store     |
                    | serializable authoritative|
                    | player/world/history      |
                    +------+------+-------------+
                           |      |
             +-------------+      +----------------+
             v                                       v
   +------------------+                    +------------------+
   | Deterministic    |                    | AI Narrative     |
   | Rules Engine     |                    | Adapter          |
   | dice/combat/xp   |                    | context/choices  |
   +--------+---------+                    +--------+---------+
            |                                       |
            +----------------+----------------------+
                             v
                    +------------------+
                    | Phaser Renderer  |
                    | scene/camera/fx  |
                    +------------------+
```

The renderer is disposable. State is serializable. AI output is untrusted text and can suggest narrative choices but cannot directly mutate HP, gold, inventory or progression.

## RPG systems

### Narrative state

- `world.flags`: durable boolean/string story facts.
- `world.factions`: reputation scores, bounded by game rules.
- `world.threat`: global pressure meter.
- `world.day`: campaign time.
- `ai.memory`: recent player/narrator events.
- `ai.summary`: future compaction buffer for long campaigns.
- `history`: append-only player-facing event journal.

### Character progression

- Level + XP thresholds.
- Might, agility, mind and will attributes.
- HP/MP derived from progression.
- Equipment slots represented by item state.
- Consumable inventory quantities.
- Temporary status effects with turn expiry.
- Talent ranks: Iron Will, Quick Hands, Arcane Edge.

### Encounters

Every deterministic check is:

`d20 + attribute modifier + level bonus >= DC`

Natural 20 succeeds; natural 1 fails unless a future talent explicitly changes that rule.

Combat resolves damage and defeat recovery locally. AI is only responsible for flavor, scene setup and aftermath, preventing LLM latency from becoming a gameplay dependency.

### Branching

Choices are generated from current context but resolve through deterministic handlers. This creates a clean split:

- AI decides **what could happen**.
- Game rules decide **what actually happens**.

## AI orchestration contract

The existing backend currently accepts chat messages and forwards them to FreeLLMAPI. No new backend endpoint is assumed by the upgrade.

The frontend sends compact state context rather than the complete event journal:

```json
{
  "location": "Whispering Crossroads",
  "threat": 2,
  "factions": {"Wardens": 3, "VeiledCourt": -1},
  "flags": {"persuaded": true},
  "player": {"level": 2, "stats": {"might": 4, "mind": 3}}
}
```

Production evolution, when the backend may eventually change, should add:

1. schema-validated JSON response objects;
2. request IDs and idempotency keys;
3. bounded retry with exponential backoff;
4. provider timeout/circuit breaker;
5. context compaction into durable summaries;
6. server-owned state transitions;
7. WebSocket/SSE event streaming;
8. server-side action validation and replay protection;
9. observability for latency, token usage and failure classes.

These are deliberately documented rather than faked in the unchanged backend.

## Persistence

Current upgrade uses versioned LocalStorage because it is universally available and keeps the vertical slice dependency-free. The production migration path is:

```text
LocalStorage bootstrap -> IndexedDB save repository -> optional server save
```

Every save must include a schema version. Loading must reject unsupported versions and recover from malformed JSON without taking down the game.

## Offline/network behavior

- Deterministic actions remain playable without AI.
- AI failures automatically switch to local fallback narration.
- The UI never waits forever: requests are bounded by the browser/network and failures are surfaced as game events.
- Save is local-first.
- Future IndexedDB implementation should queue AI-independent state mutations and reconcile them by monotonic turn number.

## Anti-cheat boundary

A static client cannot provide real anti-cheat guarantees. Client-side hashes are useful only for corruption detection. Real anti-cheat requires a server-owned authoritative state and validated commands.

When backend changes become allowed, use:

```text
client command -> server validates command against state/version -> server commits event -> server returns authoritative snapshot
```

Never accept `gold`, `xp`, `damage`, inventory or reputation values directly from an untrusted client.

## Asset/audio strategy

The current vertical slice uses procedural visuals so it has no fragile asset dependency. For a full content pass:

```text
assets/
  characters/
  environment/
  ui/
  fx/
  audio/
  data/
```

Use stable manifest keys rather than embedding filenames throughout gameplay code. Audio should be lazy-loaded and unlocked from a user gesture; effects should be short and pooled.

## Production acceptance criteria

- No gameplay rule depends on an LLM completing successfully.
- No renderer object is persisted in a save.
- No AI response can directly award client-authoritative currency or stats.
- Invalid saves fail closed and recover to a clean state.
- Mobile layout remains playable without horizontal scrolling.
- AI latency/failure is visible but does not soft-lock the player.
- State mutations are deterministic and auditable through `history`.
- API URLs are configurable and no secret is embedded in the static client.

## Roadmap

### Phase 1 — implemented vertical slice

Core state model, narrative feed, choices, d20 checks, combat, XP/leveling, inventory, factions, world flags, local save/load, AI fallback, Phaser presentation.

### Phase 2 — content depth

Quest graph, procedural encounter director, talent tree UI, equipment comparison, item rarity, status-effect library, NPC relationship model, codex and journal.

### Phase 3 — production frontend

TypeScript/Vite module split, IndexedDB repository, service worker caching, asset manifest, audio manager, lazy asset streaming, telemetry hooks, accessibility pass.

### Phase 4 — authoritative backend (only when backend changes are permitted)

Server state ownership, command validation, persistence, WebSocket/SSE streaming, schema validation, rate limiting, replay protection, AI circuit breaker and observability.

### Phase 5 — QA

Browser smoke tests, mobile viewport tests, save corruption tests, network failure tests, AI timeout tests, deterministic combat fixtures, and performance budgets.
