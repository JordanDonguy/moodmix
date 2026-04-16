# Sprint 7 — Static Pages & Legal

**Goal:** Privacy Policy, Terms of Service, Help, and About pages — required before launching auth or analytics.

**Depends on:** Sprint 6

## Scope

- Privacy Policy (GDPR-aware: data collected, retention, deletion rights, contact)
- Terms of Service
- Help / FAQ (how mood vectors work, how to use sliders, AI search tips)
- About page (project context, tech stack, link to portfolio)
- Contact page with a simple form (name, email, message) — doubles as the GDPR deletion-request channel and the general "user wants to request something" inbox. Posts to a backend endpoint that emails the admin (reuses Sprint 8's transactional email provider, or use a free service like Formspree if Sprint 8 isn't ready yet)
- Frontend routing (lazy-loaded; these are rarely visited). All pages render in-place as SPA routes — playback continues because the player iframe lives on `document.body` (overlay architecture)

### Navigation

- **No footer** — the app's infinite-scroll grid means a footer would never be reached. Keeping the layout clean.
- **Single dropdown entry** — one item in the user dropdown labeled e.g. *"Legal & contact"* (or *"More"* / *"About"* — pick during impl). Navigates to a parent route like `/info` that defaults to one of the pages (probably About or Help).
- **Sidebar within `/info/*` routes** — once on any of these pages, a small left-side nav lists Privacy, Terms, Help, About, Contact. Active page highlighted. Mobile: collapses to a top tab strip or hamburger.
- **Auth modal references** (Sprint 8) — links like "By signing in, you agree to our [Terms]" open the relevant page in a **new tab** (`target="_blank"`) so the user can check without losing the auth flow.

## Out of scope

- Cookie banner — only needed if we add non-essential cookies later
- Multi-language content

## Done when

- All five pages (Privacy, ToS, Help, About, Contact) reachable from the user dropdown via a single "Legal & contact" entry
- Sidebar within `/info/*` routes lets the user switch between the five pages
- Player keeps playing while navigating between info pages (verify overlay still tracks the active card on `/`)
- Privacy URL is publishable to Google for the OAuth consent screen in Sprint 8
- Contact form successfully delivers to the admin inbox
- Pages render correctly in light/dark theme
