# Sprint 8 — Authentication

**Goal:** User accounts via passwordless email code and Google OAuth, JWT-based with refresh rotation.

**Depends on:** Sprint 7 (Privacy URL needed for Google's OAuth consent screen)

## Auth methods

- **Passwordless email code** (primary) — user enters email, receives a 6-digit code, enters it to sign in. Same user record handles both first sign-in and returning sign-in.
- **Google OAuth** (one-click) — for users already in the Google ecosystem.
- No password-based auth. Better UX, fewer footguns (no hashing, no reset flow, no leaks).

## Scope

### Backend
- `users` and `refresh_tokens` tables (Alembic migration); `users` has no password column
- `email_codes` table: `email`, `code_hash`, `expires_at`, `attempts`, `consumed_at`
- 6-digit numeric codes, ~10 min TTL, max 5 verify attempts before invalidation
- Codes are hashed at rest (sha256 is fine — short TTL, single-use)
- JWT access tokens (~15 min) + refresh token rotation (long-lived, hashed at rest)
- Transactional email provider (Resend or Mailgun) for delivering codes
- Google OAuth via `authlib` (links by email; first sign-in auto-creates the user)
- Endpoints:
  - `POST /auth/request-code` — email → sends code
  - `POST /auth/verify-code` — email + code → returns access + refresh
  - `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`
  - `GET /auth/google`, `GET /auth/google/callback`
- Rate limiting via `slowapi` on `/request-code` (e.g., 3/hour/email + 10/hour/IP), `/verify-code` (5/min/IP), `/auth/google/callback`
- FastAPI dependency for current user (`Depends(get_current_user)`)

### Frontend
- Auth context provider + Zustand store for current user
- Login modal: single email field → switches to a 6-digit code input on submit (auto-advance between digits, paste support)
- "Sign in with Google" button alongside the email field
- Resend code button with cooldown (e.g., 30s) and visible timer
- Account menu in navbar (when logged in)
- Token storage: HttpOnly refresh cookie + in-memory access token

## Out of scope

- Password-based auth (intentionally — replaced by email codes)
- 2FA / MFA (the email code already covers most of what 2FA gives you)
- Magic links (codes are better UX on mobile — no app-switching)
- Social providers beyond Google
- Account deletion UI (have the endpoint for GDPR, polish UI later)

## Decisions to make during impl

- Email transactional provider: Resend (developer-friendly, free tier) vs. Mailgun
- Code length / format: 6 digits is the sweet spot — short enough to type, long enough to brute-force-resist with rate limiting
- OAuth library: `authlib` vs `fastapi-sso` (probably authlib — more mature)
- Whether to invalidate previous unused codes on a new `request-code` call (probably yes — cleaner)

## Done when

- Can sign in with email + code in two screens, no password ever touched
- Can sign in with Google in one click
- Refresh token rotation works (re-using an old refresh returns 401)
- Codes expire after ~10 min and are single-use
- Verify endpoint is rate-limited; 5 wrong attempts invalidates the code
- Frontend persists session across page reloads
