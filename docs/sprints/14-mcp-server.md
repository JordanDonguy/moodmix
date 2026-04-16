# Sprint 14 — MCP Server (Optional)

**Goal:** Expose admin operations via Model Context Protocol so they can be invoked from Claude Desktop.

**Depends on:** Sprint 10 (admin operations defined and stable)

**Status:** Optional / strategic. Build when the core product is past 1.0. The admin frontend (Sprint 10) covers the same operational surface — MCP is a developer-experience win, not a user-facing feature.

## Scope

- MCP server exposing tools: `list_mixes`, `get_mix`, `update_mix_classification`, `trigger_crawl`, `trigger_classify`, `get_analytics_report`, `get_pipeline_runs`
- Authentication via long-lived API key
- Documented config snippet for Claude Desktop's `mcp.json`
- Read-only mode (default) vs read-write mode (explicit flag)

## Out of scope

- Public MCP marketplace listing
- Multi-tenant authentication

## Done when

- Common admin tasks (edit a mix, kick off a crawl, read analytics) can be done in a Claude Desktop conversation
- All operations require the API key
- README documents the setup steps
