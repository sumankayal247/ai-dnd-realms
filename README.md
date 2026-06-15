# AI DnD Realms 🎲

A single-file, browser-based text adventure / RPG powered by the **Google Gemini Flash** API
(auto-detects a current Flash model for your key — Gemini 1.5 was retired by Google in 2025).
Pick a realm (Fantasy, Sci-Fi, Horror, Noir, Post-Apocalyptic, or write your own), talk to NPCs
who remember everything you say, and fight in a fast hybrid combat system.

▶️ **Play it live:** https://sumankayal247.github.io/ai-dnd-realms/

## How to play
1. Open the live link (or `index.html` locally in Chrome).
2. Click **⚙️ Settings** and paste your own **Gemini API key**
   (free tier available — get one at https://aistudio.google.com/apikey).
3. Click **⚔️ New Adventure** and play. Your key is stored only in *your* browser.

## Design highlights
- **One model, one brain** — a single Gemini instance voices every NPC from one system prompt.
- **Hybrid combat** — all the math runs instantly in code; Gemini is called only for the
  fight intro, the finishing blow, and boss aftermaths (~2–3 calls per fight).
- **API-efficient** — room descriptions are cached; movement/inventory/menus are pure code.
  A normal session uses ~20–30 calls. A daily-limit "the realm sleeps" screen guards the quota.
- **Self-contained** — one HTML file with art and favicon inlined as data URIs. No build, no server.

## Security notes
- No secret keys are committed — each player supplies their own key, kept in `localStorage`.
- A strict Content-Security-Policy restricts network access to Google's endpoint only.
- Because this is a static site, the source is public — that's fine, there are no secrets in it.
- For heavier use, restrict your key in Google AI Studio / Cloud Console to your Pages URL.

Built with the help of Claude Code.
