# Auth Architecture

How user authentication works in MoodMix.

> **Status:** the foundation (schema, JWT, refresh rotation, `get_current_user` dependency) lands in Sprint 8 / PR 1. Endpoints, cookies, and the frontend integration arrive in subsequent PRs of the same sprint. Sections marked _(planned)_ describe what's coming.

## Overview

Two sign-in methods, no passwords:

- **Passwordless email code** (primary) — user types email, receives a 6-digit code, enters it.
- **Google OAuth** (one-click) — for users already in the Google ecosystem.

Both methods produce the same outcome: a `User` row + a token pair (access + refresh). Downstream routes don't care which method signed the user in.

We chose passwordless over passwords for product reasons (better mobile UX, no reset flow) and security reasons (nothing to leak — no hashes in the DB, no reuse across sites).

## Token model

| | Access token | Refresh token |
| --- | --- | --- |
| **Format** | JWT (HS256, signed) | Opaque random string (256 bits) |
| **Lifetime** | ~15 min | ~30 days |
| **Storage server-side** | None (stateless) | sha256 hash in `refresh_tokens` |
| **Storage client-side** | In-memory only | HttpOnly cookie _(planned)_ |
| **Sent on each API call** | Yes, `Authorization: Bearer …` | No, only to `/auth/refresh` and `/auth/logout` |
| **Revocable** | No (waits for `exp`) | Yes |

### Why JWT for access, opaque for refresh?

- Access tokens are checked on **every** API request. Statelessness (no DB lookup to verify) matters at that frequency. The 15-min TTL bounds the damage if one leaks.
- Refresh tokens are used **rarely** (once every ~15 min) and need to be revocable (logout, theft detection). Statefulness is fine — the lookup cost is negligible.

This is the standard JWT-with-refresh pattern; nothing exotic.

### What's in the JWT

```json
{
    "sub": "<user-uuid>",
    "iat": 1746201600,
    "exp": 1746202500,
    "type": "access"
}
```

- `sub` — user id (stringified UUID).
- `iat` / `exp` — Unix timestamps. `exp` is enforced automatically by PyJWT during decode.
- `type: "access"` — non-standard, defends against confused-deputy attacks if we ever issue other JWT-shaped artifacts signed with the same secret. The decoder rejects anything that isn't `"access"`.

The JWT carries **no email, no role, no other state**. We deliberately keep it minimal: more claims = more staleness bugs (e.g. a renamed user keeps their old name in the JWT until refresh). Fresh user data is fetched in [`get_current_user`](../backend/app/middleware/auth.py) on every request, against the user-id PK index, sub-millisecond.

## Database schema

Three tables added by [migration 007](../backend/alembic/versions/007_add_users_and_auth_tables.py):

```
users                       refresh_tokens                   email_codes
─────                       ──────────────                   ───────────
id           UUID  PK       id           UUID  PK             id           UUID  PK
email        TEXT  UQ       user_id      UUID  FK→users       email        TEXT
created_at   TS             token_hash   TEXT  UQ             code_hash    TEXT
last_login_at TS?           family_id    UUID                 expires_at   TS
                            expires_at   TS                   attempts     INT
                            replaced_at  TS?                  consumed_at  TS?
                            revoked_at   TS?                  created_at   TS
                            created_at   TS
```

**Notes:**
- `users` has no password column. Identity is the email.
- Tokens (refresh + email codes) are **only** stored as sha256 hashes. The plaintext lives in the user's cookie / email body and never in the DB. A DB exfiltration leaks no usable credentials.
- `email_codes` is populated/consumed in PR 3 (this PR creates the table only).

## Refresh token rotation

Every successful refresh **swaps** the token: present token A → receive token B, A becomes invalid. The chain is anchored by a `family_id` shared across all rotations of one sign-in.

### Happy path

```
sign-in          rotate          rotate          rotate
   │               │               │               │
   ▼               ▼               ▼               ▼
 ┌────┐ replaced ┌────┐ replaced ┌────┐ replaced ┌────┐  active
 │ T₀ │────────▶ │ T₁ │────────▶ │ T₂ │────────▶ │ T₃ │
 └────┘          └────┘          └────┘          └────┘
   │               │               │               │
   └───────────────┴───────────────┴───────────────┘
                  family_id = F
```

Each row in `refresh_tokens` is created once and never updated except to set `replaced_at` (on rotation) or `revoked_at` (on logout / family kill). The latest non-replaced, non-revoked, non-expired row in the family is the "active" token.

### Theft detection — the alarm

The chain exists for one specific reason: detecting stolen tokens.

**Without rotation chains**, this attack works:

1. Attacker steals the refresh cookie.
2. Attacker refreshes first → new token B; the user still has A in their cookie.
3. User refreshes → server says "unknown token" → user just sees "session expired."
4. Attacker keeps using B. User has no idea their session was hijacked.

**With rotation chains**, step 3 changes:

3'. User presents A → server sees A's `replaced_at` is already set → revokes the entire family → attacker's B is now also invalid → both parties get logged out, user signs back in cleanly.

So a token whose `replaced_at` is set being presented again is **the** signal of theft. The implementation in [`RefreshTokenService.rotate`](../backend/app/services/refresh_token_service.py) treats it as the strongest possible auth failure: revoke the whole family, raise `RefreshReuseError`.

### When a family is revoked

- **Reuse detection** (above) — revoke the family.
- **Logout** (planned) — revoke the single token presented (`revoke`), not the family. A user signing out on one device shouldn't sign them out on others.
- **"Sign out everywhere"** (future) — calls `revoke_family`. Not in Sprint 8 scope, but the method exists.

### Storage growth

A 30-day session refreshing every 15 minutes produces ~2880 rows per user. A periodic cleanup (`DELETE FROM refresh_tokens WHERE expires_at < now()`) bounds that. Sprint 11 (background jobs) is the natural home — until then, the `expires_at` index keeps queries fast even as rows accumulate.

## Threat model

**Protected against:**
- DB exfiltration → tokens are hashed, attackers can't impersonate users from a dump.
- Stolen refresh cookie → reuse detection alarms on the next rotation race, killing both parties' access.
- Forged JWTs → HS256 with a 32+ byte secret; alg=none rejected by explicit `algorithms=[…]` whitelist.
- Wrong-token-type confusion → `type: "access"` claim required.
- Replay of expired tokens → `exp` enforced by PyJWT; `expires_at` enforced by `RefreshTokenService`.

**Not protected against (out of scope for Sprint 8):**
- Live access-token theft within its 15-min TTL — accepted bound, mitigated by short TTL + HttpOnly + HTTPS-only.
- 2FA / MFA — passwordless email already covers most of what 2FA gives us for a music app.
- Account deletion UI — endpoint will exist for GDPR, polished UI deferred.

## Configuration

Set in [`backend/app/config.py`](../backend/app/config.py), populated from `.env`:

| Variable | Default | Notes |
| --- | --- | --- |
| `JWT_SECRET` | `""` | **Must be set** in any environment that issues tokens. Use 32+ bytes. Empty → `JwtService` raises on every call. |
| `JWT_ALGORITHM` | `"HS256"` | Symmetric. RS256 only matters if multiple services verify tokens. |
| `ACCESS_TTL_MINUTES` | `15` | Short enough that token theft is bounded; long enough to avoid hammering `/auth/refresh`. |
| `REFRESH_TTL_DAYS` | `30` | "Stay signed in for a month." |

## File map

The auth foundation is split across these files. Reading them in order is a reasonable on-ramp:

| File | Responsibility |
| --- | --- |
| [`models/user.py`](../backend/app/models/user.py) | `User` ORM model |
| [`models/refresh_token.py`](../backend/app/models/refresh_token.py) | `RefreshToken` ORM model — chain + family fields |
| [`models/email_code.py`](../backend/app/models/email_code.py) | `EmailCode` ORM model — used in PR 3 |
| [`schemas/auth.py`](../backend/app/schemas/auth.py) | Pydantic: `UserResponse`, `AccessClaims`, `TokenPair` |
| [`services/jwt_service.py`](../backend/app/services/jwt_service.py) | Pure JWT encode/decode, no DB |
| [`services/user_service.py`](../backend/app/services/user_service.py) | User persistence (`get_or_create_by_email`, `touch_last_login`) |
| [`services/refresh_token_service.py`](../backend/app/services/refresh_token_service.py) | Issue / rotate / revoke + reuse detection |
| [`middleware/auth.py`](../backend/app/middleware/auth.py) | `get_current_user` dep — turns a `Bearer` header into a `User` |
| [`exceptions.py`](../backend/app/exceptions.py) | `InvalidCredentialsError`, `TokenExpiredError`, `RefreshReuseError` |

### How a future route consumes auth

```python
from fastapi import Depends
from app.middleware.auth import get_current_user
from app.models.user import User

@router.get("/some-protected-route")
async def handler(user: User = Depends(get_current_user)) -> ...:
    # `user` is a real User row — token already validated, 401 already raised on failure
    ...
```

That's the whole API surface a route author needs.

## Design decisions worth knowing

- **Three services, not one.** `JwtService`, `UserService`, `RefreshTokenService` each have one reason to change. A unified `AuthService` would muddle pure crypto, persistence, and rotation lifecycle.
- **`family_id` over update-in-place.** In-place rotation (one row per session) would be simpler and bounded in storage, but loses theft detection. Music app threat model is mild, but the alarm is cheap and standard.
- **Errors mapped through `AppException`, not `HTTPException`.** Keeps the JSON shape consistent with the rest of the API (one error contract for clients).
- **Service deps are constructor-injected.** Same pattern as `ContactService` / `MixService`. Tests pass an in-memory mock or a rolled-back DB session; no monkey-patching globals.
- **Lookup the user every request.** No caching layer. The PK lookup is sub-millisecond, FastAPI deduplicates `Depends(get_current_user)` within a request, and caching would create a staleness window for deleted/changed users.
