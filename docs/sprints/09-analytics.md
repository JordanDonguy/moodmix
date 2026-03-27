# Sprint 9 — Catalog Analytics (pandas)

**Goal:** Automated catalog health reports with actionable insights for catalog growth.

**Depends on:** Sprint 8 (Celery for scheduling the analytics task)

## Tasks

### 9.1 — Analytics service
- [ ] Add `pandas` + `numpy` to dependencies
- [ ] `app/services/analytics_service.py`
- [ ] `generate_report() -> dict` — fetches all classified mixes, produces a full report

### 9.2 — Mood space coverage analysis
- [ ] Divide each axis into 5 bins: [-1, -0.6], [-0.6, -0.2], [-0.2, 0.2], [0.2, 0.6], [0.6, 1]
- [ ] 5x5x5 = 125 regions
- [ ] Count mixes per region using pandas `cut()` + `groupby()`
- [ ] Identify sparse regions (< 5 mixes)
- [ ] Generate suggested search queries for sparse regions:
  - Map bin ranges to descriptive terms (e.g., mood [0.6, 1] = "bright/uplifting", energy [-1, -0.6] = "ambient/calm")
  - Combine terms into YouTube search queries

### 9.3 — Genre distribution
- [ ] Count mixes per genre via JOIN query → pandas DataFrame
- [ ] Calculate percentage of total
- [ ] Flag underrepresented genres (< 3% of catalog)

### 9.4 — Confidence distribution
- [ ] Histogram of classification_confidence values
- [ ] Buckets: high (0.8-1.0), medium (0.5-0.8), low (0.0-0.5)
- [ ] Count + percentage per bucket

### 9.5 — Vocal distribution
- [ ] Count of has_vocals=true vs has_vocals=false

### 9.6 — Store report
- [ ] Alembic migration: create `analytics_reports` table (report_type, report_data jsonb, generated_at)
- [ ] Save report as JSONB row in `analytics_reports` table

### 9.7 — Celery task
- [ ] `generate_analytics_task()` in `pipeline_tasks.py`
- [ ] Add to Celery Beat schedule: weekly (e.g., Sunday after crawl tasks complete)
- [ ] Creates pipeline_run record

### 9.8 — Admin endpoint
- [ ] `GET /api/admin/analytics` — returns latest report from `analytics_reports` table
- [ ] Protected by API key

## Done when

- [ ] `GET /api/admin/analytics` returns a full report with:
  - Mood coverage with sparse regions + suggested queries
  - Genre distribution with percentages
  - Confidence distribution
  - Vocal distribution
- [ ] Report data is computed via pandas (groupby, cut, pivot)
- [ ] Task runs on schedule via Celery Beat
- [ ] Sparse region suggestions are actionable (could be fed back to crawler)
