# Sprint 10 — Analytics & Admin Panel

**Goal:** Catalog health metrics + product usage metrics, surfaced in an admin frontend with mix editing.

**Depends on:** Sprint 9 (user-generated data — likes, preferences — feeds product analytics)

## Scope

### Analytics service (pandas)
- Catalog health: mood-space coverage (5×5×5 bins), genre distribution, classification confidence histogram, vocal split
- Product usage: top filter combinations, search frequency, like rates, anonymous vs authenticated traffic
- Sparse mood-region detection with suggested YouTube search queries to fill gaps
- `analytics_reports` table for storing snapshots (JSONB column for the full report)
- Generated on demand via admin endpoint; scheduled generation moves to Sprint 11 (Celery)

### Admin frontend
- New route group `/admin/*`, gated by `is_admin` boolean on `users`
- Dashboard view: catalog + product analytics with charts (recharts or similar)
- Mix browser: searchable table of all mixes, sortable by classification confidence, view count, etc.
- Mix editor: edit mood/energy/instrumentation, toggle vocals, add/remove genres
- `PATCH /admin/mixes/{id}` endpoint

## Out of scope

- Full RBAC — single `is_admin` boolean is enough for now
- Analytics export (CSV, dashboards beyond the in-app view)
- Admin audit log

## Decisions to make during impl

- Charting library: recharts (simple, React-native), Chart.js (more powerful), or just raw SVG
- Replace existing sqladmin panel or run alongside? Probably keep sqladmin for raw DB access, build the new admin UI on top of typed APIs

## Done when

- Admin dashboard renders catalog health + product usage
- Sparse mood regions surfaced with actionable search suggestions
- Can edit a mix's classification from the admin UI without writing SQL
- Non-admin users get 403 on any `/admin/*` route or endpoint
