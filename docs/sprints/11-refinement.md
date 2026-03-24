# Sprint 11 — Refinement (future)

**Goal:** Polish, feedback loop, and optional features.

**Depends on:** Sprints 1-10 (core app complete)

## Tasks

### 11.1 — User feedback loop
- [ ] `POST /api/mixes/{id}/feedback` endpoint (already defined in API routes)
- [ ] UI: subtle thumbs up/down or "this feels more chill" nudge buttons on playing card
- [ ] Store feedback in a `mix_feedback` table (new migration)
- [ ] Periodic Celery task: aggregate feedback, adjust mood vectors for mixes with enough signal

### 11.2 — UI polish
- [ ] Loading skeleton cards (shimmer effect) while fetching
- [ ] Smooth transitions when results change (framer-motion `layout` prop on grid items)
- [ ] Empty state if no results match filters (friendly message + suggestion to adjust sliders)
- [ ] Keyboard shortcuts: space = play/pause, arrow keys = next/prev card
- [ ] Favicon + page title + meta tags for sharing

### 11.3 — Responsive mobile layout
- [ ] Test on actual mobile devices
- [ ] Top bar collapses to a compact layout on mobile:
  - Sliders stacked vertically or behind a toggle
  - Genre chips horizontally scrollable
  - Search bar full width
- [ ] Player card expands to full width on mobile
- [ ] Note: YouTube embeds pause on mobile background — add info tooltip

### 11.4 — Optional: user accounts
- [ ] Supabase Auth integration (email + Google OAuth)
- [ ] `users` table + `user_preferences` table
- [ ] Save favorite mixes, preferred genres, last slider positions server-side
- [ ] Login is optional — app works fully without it, accounts just add persistence across devices
- [ ] "Sign in to save your preferences" prompt after user has already gotten value

### 11.5 — Optional: mix queue
- [ ] "Play next" / queue system
- [ ] When current mix ends, auto-play next mix from results
- [ ] Small queue indicator showing upcoming mixes
