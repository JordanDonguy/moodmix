# Sprint 10 — MCP Server

**Goal:** AI agents (Claude Desktop, Claude Code) can interact with the MoodMix catalog via MCP.

**Depends on:** Sprint 9 (analytics service exists to expose via MCP)

## Tasks

### 10.1 — MCP server scaffold
- [ ] Add `mcp` SDK to dependencies
- [ ] `mcp_server/server.py` — MCP server entrypoint
  - Connects to the same Supabase DB (reuses SQLAlchemy models and config)
  - Registers tools from `tools.py`
  - Runs via stdio transport (for Claude Desktop / Claude Code)

### 10.2 — Read tools
- [ ] `search_mixes(mood, energy, instrumentation, genres, instrumental, limit)` — same logic as the search endpoint
- [ ] `get_catalog_stats()` — total mixes, mixes per genre, mood coverage summary
- [ ] `get_catalog_analytics()` — returns latest analytics report
- [ ] `get_low_confidence_mixes(threshold, limit)` — mixes below confidence threshold for review

### 10.3 — Write tools
- [ ] `add_seed_channel(channel_id, channel_name)` — insert into seed_channels
- [ ] `trigger_crawl(type)` — enqueue a Celery task (channel_crawl | keyword_search)
- [ ] `update_mix_classification(mix_id, mood, energy, instrumentation, genres, has_vocals)` — manually fix a misclassified mix

### 10.4 — Claude Desktop configuration
- [ ] Document how to add the MCP server to Claude Desktop config:
  ```json
  {
    "mcpServers": {
      "moodmix": {
        "command": "python",
        "args": ["path/to/mcp_server/server.py"],
        "env": {
          "DATABASE_URL": "..."
        }
      }
    }
  }
  ```

### 10.5 — Test
- [ ] Connect via Claude Desktop
- [ ] Test: "Find me chill jazz mixes" → `search_mixes` tool called → results returned
- [ ] Test: "What genres are underrepresented?" → `get_catalog_analytics` → meaningful answer
- [ ] Test: "Add this channel: UC..." → `add_seed_channel` → confirms added
- [ ] Test: "Show me low confidence classifications" → `get_low_confidence_mixes` → review list

## Done when

- [ ] MCP server starts and registers all tools
- [ ] Claude Desktop can discover and use all tools
- [ ] Read tools return accurate data from the catalog
- [ ] Write tools modify the database correctly
- [ ] Usable as an admin interface for catalog management
