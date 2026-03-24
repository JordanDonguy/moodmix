# MoodMix — Sprint Plan

## MVP (Sprints 1-6)

| Sprint | Name | Depends on | Focus |
|--------|------|------------|-------|
| [01](01-fastapi-foundation.md) | FastAPI Foundation | — | Project scaffold, DB schema, models, config, error handling |
| [02](02-data-pipeline.md) | Data Pipeline | 01 | YouTube crawler, initial seed classification, automated classifier |
| [03](03-api-layer.md) | API Layer | 02 | All REST endpoints, auth, rate limiting |
| [04](04-testing.md) | Testing | 03 | Unit + integration + DB tests |
| [05](05-frontend-mvp.md) | Frontend MVP | 03 | React app, sliders, grid, player, AI search |
| [06](06-deployment.md) | Deployment | 05 | Docker, CI/CD, nginx, SSL |

## Enhancements (Sprints 7-10)

| Sprint | Name | Depends on | Focus |
|--------|------|------------|-------|
| [07](07-redis-caching.md) | Redis Caching | 06 | Search + genre caching, invalidation |
| [08](08-celery.md) | Celery Task Queue | 07 | Production background jobs, replace APScheduler |
| [09](09-analytics.md) | Catalog Analytics | 08 | pandas reports: mood coverage, genre distribution, gap detection |
| [10](10-mcp-server.md) | MCP Server | 09 | AI agent integration for catalog admin |

## Future (Sprint 11)

| Sprint | Name | Depends on | Focus |
|--------|------|------------|-------|
| [11](11-refinement.md) | Refinement | 10 | Feedback loop, UI polish, mobile, optional accounts |
