# MoodMix API Routes

Base URL: `/api`

---

## Public endpoints

### `GET /api/genres`

Returns all available genres for the filter chips.

**Response `200`**
```json
[
  { "id": "uuid", "name": "Lo-Fi", "slug": "lo-fi" },
  { "id": "uuid", "name": "Jazz", "slug": "jazz" }
]
```

Cached in Redis (TTL ~1h). Invalidated when genres are added/modified.

---

### `GET /api/mixes/search`

Main search endpoint. Combines pgvector similarity with genre/vocal filters.

**Query params**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `mood` | float (-1 to 1) | `0` | Dark ↔ Bright |
| `energy` | float (-1 to 1) | `0` | Chill ↔ Dynamic |
| `instrumentation` | float (-1 to 1) | `0` | Organic ↔ Electronic |
| `genres` | string (comma-separated slugs) | _none_ | Filter by genres. Empty = all genres |
| `instrumental` | boolean | `false` | `true` = only mixes where `has_vocals = false` |
| `limit` | integer (1-50) | `20` | Results per page |
| `offset` | integer | `0` | Pagination offset |

**Response `200`**
```json
{
  "mixes": [
    {
      "id": "uuid",
      "youtube_id": "dQw4w9WgXcQ",
      "title": "Peaceful Jazz Piano - 1 Hour Relaxing Café Music",
      "channel_name": "Cafe Music BGM",
      "thumbnail_url": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
      "duration_seconds": 3600,
      "mood": 0.3,
      "energy": -0.6,
      "instrumentation": -0.8,
      "has_vocals": false,
      "genres": [
        { "name": "Jazz", "slug": "jazz" },
        { "name": "Piano", "slug": "piano" }
      ]
    }
  ],
  "total": 142,
  "limit": 20,
  "offset": 0
}
```

Cached in Redis (key = hash of all query params, TTL ~30-60s).

---

### `POST /api/mixes/ai-search`

Natural language search. LLM converts text to mood vector + optional genre/vocal inference.

**Rate limited: 5 requests/minute per IP.**

**Request body**
```json
{
  "query": "rainy day coffee shop vibes"
}
```

**Response `200`**
```json
{
  "mixes": [ ... ],
  "inferred": {
    "mood": -0.2,
    "energy": -0.6,
    "instrumentation": -0.4,
    "genres": ["jazz", "lo-fi"],
    "instrumental": true
  },
  "total": 87,
  "limit": 20,
  "offset": 0
}
```

`inferred` lets the frontend sync sliders + genre chips to what the AI understood.

**Response `429`**
```json
{
  "error": "Rate limit exceeded. Try again in 45 seconds.",
  "status": 429,
  "retry_after": 45
}
```

---

### `POST /api/mixes/{id}/report-unavailable`

User reports that a mix failed to play (video deleted, private, etc.).

**Response `200`**
```json
{
  "message": "Mix reported as unavailable."
}
```

Mix is immediately marked `status = 'unavailable'` and excluded from future searches.

---

### `GET /api/health`

Health check for monitoring.

**Response `200`**
```json
{
  "status": "healthy",
  "db_connected": true,
  "redis_connected": true,
  "last_crawl_at": "2026-03-24T02:00:00Z",
  "last_classification_at": "2026-03-24T02:15:00Z",
  "catalog_size": 3241
}
```

---

## Admin endpoints

Protected by `X-API-Key` header. Returns `401` if missing/invalid.

### `POST /api/admin/crawl/trigger`

Manually trigger a crawl run (enqueues a Celery task).

**Request body**
```json
{
  "type": "channel_crawl"
}
```

`type` options: `channel_crawl`, `keyword_search`, `availability_check`.

**Response `202`**
```json
{
  "message": "Crawl task enqueued.",
  "task_id": "celery-task-uuid"
}
```

---

### `GET /api/admin/pipeline/status`

Overview of recent pipeline activity.

**Response `200`**
```json
{
  "last_runs": {
    "channel_crawl": {
      "status": "completed",
      "started_at": "2026-03-24T02:00:00Z",
      "completed_at": "2026-03-24T02:12:00Z",
      "mixes_processed": 450,
      "mixes_added": 12
    },
    "keyword_search": {
      "status": "completed",
      "started_at": "2026-03-24T03:00:00Z",
      "completed_at": "2026-03-24T03:05:00Z",
      "mixes_processed": 150,
      "mixes_added": 8
    },
    "classification": {
      "status": "completed",
      "started_at": "2026-03-24T03:10:00Z",
      "completed_at": "2026-03-24T03:12:00Z",
      "mixes_processed": 20,
      "mixes_added": 20
    },
    "availability_check": {
      "status": "completed",
      "started_at": "2026-03-24T04:00:00Z",
      "completed_at": "2026-03-24T04:03:00Z",
      "mixes_processed": 200,
      "mixes_added": 0
    }
  },
  "today": {
    "mixes_crawled": 600,
    "mixes_classified": 20,
    "mixes_marked_unavailable": 3,
    "quota_used_estimate": 4200
  }
}
```

---

### `POST /api/admin/channels`

Add a new seed channel.

**Request body**
```json
{
  "channel_id": "UCJhjE7wbdYAae1G25m0tHAA",
  "channel_name": "Lofi Girl"
}
```

**Response `201`**
```json
{
  "id": "uuid",
  "channel_id": "UCJhjE7wbdYAae1G25m0tHAA",
  "channel_name": "Lofi Girl",
  "active": true,
  "created_at": "2026-03-24T12:00:00Z"
}
```

**Response `409`** (duplicate)
```json
{
  "error": "Channel UCJhjE7wbdYAae1G25m0tHAA already exists.",
  "status": 409
}
```

---

### `GET /api/admin/channels`

List all seed channels.

**Response `200`**
```json
[
  {
    "id": "uuid",
    "channel_id": "UCJhjE7wbdYAae1G25m0tHAA",
    "channel_name": "Lofi Girl",
    "active": true,
    "last_crawled_at": "2026-03-24T02:00:00Z",
    "total_mixes_found": 142,
    "created_at": "2026-03-20T10:00:00Z"
  }
]
```

---

### `PATCH /api/admin/channels/{id}`

Update a seed channel (activate/deactivate).

**Request body**
```json
{
  "active": false
}
```

**Response `200`**
```json
{
  "id": "uuid",
  "channel_id": "UCJhjE7wbdYAae1G25m0tHAA",
  "channel_name": "Lofi Girl",
  "active": false
}
```

---

### `GET /api/admin/analytics`

Returns the latest catalog analytics report.

**Response `200`**
```json
{
  "generated_at": "2026-03-24T05:00:00Z",
  "catalog_size": 3241,
  "mood_coverage": {
    "total_regions": 125,
    "covered_regions": 108,
    "coverage_pct": 86.4,
    "sparse_regions": [
      { "mood": [0.6, 1.0], "energy": [0.6, 1.0], "instrumentation": [-1.0, -0.6], "count": 2 },
      { "mood": [-1.0, -0.6], "energy": [0.6, 1.0], "instrumentation": [0.6, 1.0], "count": 1 }
    ],
    "suggested_queries": [
      "upbeat happy acoustic folk mix 1 hour",
      "dark intense electronic industrial mix"
    ]
  },
  "genre_distribution": [
    { "genre": "lo-fi", "count": 612, "pct": 18.9 },
    { "genre": "jazz", "count": 445, "pct": 13.7 },
    { "genre": "ambient", "count": 398, "pct": 12.3 }
  ],
  "confidence_distribution": {
    "high": { "range": [0.8, 1.0], "count": 2100, "pct": 64.8 },
    "medium": { "range": [0.5, 0.8], "count": 890, "pct": 27.5 },
    "low": { "range": [0.0, 0.5], "count": 251, "pct": 7.7 }
  },
  "vocal_distribution": {
    "instrumental": 2970,
    "vocal": 271
  }
}
```

---

## Error format (all endpoints)

```json
{
  "error": "Human-readable error message.",
  "status": 404,
  "timestamp": "2026-03-24T12:00:00Z"
}
```

Standard HTTP status codes:
- `400` — Bad request (invalid params)
- `401` — Unauthorized (missing/invalid API key on admin endpoints)
- `404` — Mix/channel not found
- `409` — Conflict (duplicate)
- `429` — Rate limit exceeded
- `500` — Internal server error
