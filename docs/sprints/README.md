# MoodMix - Sprint Plan

## MVP (Sprints 1-6) - shipped

| Sprint | Name | Focus |
|--------|------|-------|
| [01](01-fastapi-foundation.md) | FastAPI Foundation | Project scaffold, DB schema, models, config, error handling |
| [02](02-data-pipeline.md) | Data Pipeline | YouTube crawler, initial seed classification, automated classifier |
| [03](03-api-layer.md) | API Layer | All REST endpoints, rate limiting |
| [04](04-frontend-mvp.md) | Frontend MVP | React app, sliders, grid, player, AI search |
| [05](05-testing.md) | Testing | Unit + integration + DB tests |
| [06](06-deployment.md) | Deployment | Docker, CI/CD, nginx, SSL |

## Phase 2 - User platform & admin tooling

| Sprint | Name | Depends on | Focus |
|--------|------|------------|-------|
| [07](07-static-pages.md) | Static Pages & Legal | 06 | Privacy, ToS, Help, About, Contact - single dropdown entry, sidebar nav within `/info/*` |
| [08](08-auth.md) | Authentication | 07 | Passwordless email-code auth + Google OAuth, JWT with refresh rotation |
| [09](09-user-features.md) | User Features | 08 | Likes, library page, preference sync, auto-mood, smart play, resume playback, listening data collection |
| [10](10-analytics-admin.md) | Analytics & Admin Panel | 09 | pandas analytics, admin frontend with mix editor |
| [11](11-background-jobs.md) | Background Jobs | 10 | Celery + Redis broker for crawl/classify/availability/analytics |

## Phase 3 - Reach & polish

| Sprint | Name | Depends on | Focus |
|--------|------|------------|-------|
| [12](12-mobile-app.md) | Mobile App (Capacitor) | 09 | iOS + Android wrapper with background audio + native bottom-nav UX |
| [13](13-caching.md) | Caching (Redis) | 11 | Cache hot search queries - defer until measured |
| [14](14-mcp-server.md) | MCP Server | 10 | Optional - admin via Claude Desktop |

## Notes

- **Sprint format for phase 2 and 3 is intentionally lean** - high-level scope and acceptance criteria, not a step-by-step task list. Adjust during implementation.
- **Phase 2 has a strict order**: each sprint unblocks the next (legal pages → auth that needs the privacy URL → user data that needs auth → analytics that benefits from user data → background jobs that include analytics generation).
- **Sprint 9 is the largest** - it bundles likes, the library page, preference sync, auto-mood, smart play, resume playback, and silent listening-data collection. Bundled together because they all share the same data model and the same player/store touchpoints; splitting would mean re-touching the same files repeatedly.
- **Phase 3 sprints are more flexible**: 12 and 13 can run in parallel; 14 is strategic and optional.
- **Caching (13) is gated on observed need**, not a fixed milestone. Don't ship until analytics shows specific slow endpoints.
