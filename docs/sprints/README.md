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

## Phase 2 - User platform & catalog

| Sprint | Name | Depends on | Focus |
|--------|------|------------|-------|
| [07](07-static-pages.md) | Static Pages & Legal | 06 | Privacy, ToS, Help, About, Contact - single dropdown entry, sidebar nav within `/info/*` |
| [08](08-auth.md) | Authentication | 07 | Passwordless email-code auth + Google OAuth, JWT with refresh rotation |
| [09](09-user-features.md) | User Features | 08 | Playback persistence (DB + localStorage), login-time state migration, smart play |
| [10](10-artists-tracks.md) | Artists & Tracks Catalog | 09 | Artists/tracks models, Spotify/Deezer resolution pipeline, chapter backfill, all ingestion scripts |
| [11](11-classification-and-embedding.md) | Classification & Embedding | 10 | Essentia audio classification + 1280-d embeddings, streaming URL resolution (SoundCloud + YouTube), reusable per-track / per-artist services |
| [12](12-admin-panel.md) | Admin Panel | 11 | Genre + classification coverage dashboard, artist management, all pipeline triggers, track browser with previews + mood context |
| [13](13-track-scenes-poc.md) | Track Scenes POC | 11, 12 | Admin workbench for experimenting with anchor-based playlist generation (embedding similarity + mood-vector shifting). Answers design questions before building the user-facing playlist engine. |

## Notes

- **Sprint format is intentionally lean** - high-level scope and acceptance criteria, not a step-by-step task list. Adjust during implementation.
- **Phase 2 has a strict order**: each sprint unblocks the next.
- **Sprint 10 is the data foundation**: all scripts are idempotent and can be re-run as new channels are crawled.
- **Sprint 11 layers audio understanding** on top of the catalog: deterministic classification, embeddings for similarity, and playback URLs. Long-term services replace the one-shot backfill scripts used for initial seeding.
- **Sprint 12 admin panel** is the primary tool for ongoing catalog curation — adding artists, auditioning tracks via Deezer previews, and triggering classification / streaming resolution on demand.
- **Sprint 13 is a research sprint**: build the experimentation tool, run trials, document findings. Output is a set of recommended defaults (anchor mode, vocals threshold, shuffle strategy, etc.) that inform whatever user-facing playlist sprint comes next.
