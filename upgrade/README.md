# Realms Engine v2

Open `upgrade/index.html` directly in a browser or serve the repository with any static HTTP server.

## AI connection

The page calls `/api/chat` by default. If the API is hosted elsewhere, set `localStorage.AI_DND_API_BASE` to the API origin before playing.

Example in the browser console:

```js
localStorage.setItem('AI_DND_API_BASE', 'https://your-api.example.com')
location.reload()
```

No API key is embedded in the client.

## Controls

- **Act**: free-form player intent.
- **Choice buttons**: resolve through deterministic game rules.
- **Save/Load**: versioned local save.
- **Inventory / World / Log**: inspect state and the audit trail.

## Failure behavior

If the AI endpoint is unavailable or returns invalid data, the game automatically uses deterministic local narration. Combat, checks, progression and saves remain playable.

## Important production boundary

The existing backend remains untouched. Because the current server contract is chat-only, v2 does not claim server-authoritative anti-cheat or server persistence. Those require backend state/command endpoints and are specified in `ARCHITECTURE.md` for a later server phase.
