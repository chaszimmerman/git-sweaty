# git-sweaty — Claude Context

## What This Project Is
A GitHub Pages dashboard that turns Strava/Garmin workout activities into GitHub-style contribution heatmaps. Forked from `aspain/git-sweaty`.

- **Live dashboard:** https://chaszimmerman.github.io/git-sweaty/
- **Data source:** Strava
- **Units:** miles / feet

## Repository Structure
- `site/` — frontend: `index.html`, `app.js`, logo/assets
- `scripts/` — Python pipeline: sync, normalize, aggregate, generate heatmaps
- `config.yaml` — base config (committed); secrets go in `config.local.yaml` (gitignored)
- `data/` — generated pipeline output (not committed to `main`)
- `.github/workflows/sync.yml` — daily sync at 15:00 UTC, pushes data to `dashboard-data` branch
- `.github/workflows/pages.yml` — deploys `site/` to GitHub Pages after sync completes

## Branches
- `main` — source code only; no generated data
- `dashboard-data` — generated `data/` and `site/data.json` artifacts (auto-managed by CI)

## GitHub Actions Workflows
- **Sync Heatmaps** (`sync.yml`) — runs daily at 15:00 UTC; can be triggered manually via Actions tab
  - Manual run options: override source, update README link, full backfill reset
- **Deploy Pages** (`pages.yml`) — triggers automatically after Sync Heatmaps succeeds, or on pushes to `site/`

## Secrets & Variables (GitHub repo settings)
- `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN` — Strava API credentials
- `DASHBOARD_SOURCE` — repo variable set to `strava`
- Strava API app created at https://www.strava.com/settings/api with callback domain `localhost`

## Local Development
- Python 3.14 (via Homebrew at `/opt/homebrew/bin/python3.14`)
- Virtual environment at `.venv/` — created with Python 3.14 (system Python 3.9 is too old for `garminconnect>=0.2.25`)
- Setup script: `python3 scripts/setup_auth.py`
- GitHub CLI (`gh`) installed via Homebrew; requires `repo` and `workflow` scopes

## Keeping Up to Date
- Pull upstream changes via GitHub's **Sync fork** button on `main`
- Locally: `git fetch origin && git reset --hard origin/main`

## Config Notes
- `config.yaml` — base defaults (committed)
- `config.local.yaml` — secrets/overrides (gitignored, written by CI from GitHub secrets)
- Key config options: `source`, `sync.lookback_years`, `sync.start_date`, `activities.types`, `units.distance`, `heatmaps.week_start`
- `activities.exclude_race_ids` — list of Strava activity IDs to exclude from race detection (name-pattern false positives)

## Fork Customizations (vs upstream aspain/git-sweaty)
Changes made to `site/app.js` and `site/index.html` — do not blindly overwrite on upstream sync.

### Monthly Activity Heatmap (`buildMonthlyHeatmap`)
New section added between Activity Frequency and the year-by-year heatmaps.
- Per-type row layout with gradient cells (light = low, dark = high), scaled independently per activity type
- Miles / Count toggle chips
- Year chips driven by the top-level year filter (Option 1 behavior: if a specific year is selected at the top, the monthly section respects it; if All Years, chips appear)
- YoY badge on each cell: `+8%` / `-4%` showing % change vs. same month, prior year
- Tooltip shows count + distance, each with their own vs-prior-year delta
- Legend: gradient scale row + YoY footnote row

### Activity type color overrides
Added to `TYPE_ACCENT_OVERRIDES` in `app.js` for visual distinction across all dashboard sections:
- `TrailRun: "#9b5de5"` (purple — was too similar to Run's cyan-blue)
- `Hike: "#fb5607"` (orange — was identical to Walk's yellow-green)

### Section ordering
Layout order within the heatmaps section (top → bottom):
1. Activity Frequency
2. Monthly Activity (new)
3. Year heatmaps (2026, 2025, ...)
4. Races (new)

### Races card (`buildRacesCard`)
New section below all year heatmaps, listing all detected race activities.
- Columns: Date · Name · Distance · Time · Pace · Elevation · PR badge
- Year chips filter the table; "All" is default. PR ranks always computed across all time regardless of year filter — an all-time PR doesn't reset when filtering to one year.
- Race detection: two-signal — Strava `workout_type == 1` OR name-pattern regex (covers older activities before Strava's race tag existed). Belt-and-suspenders approach.
- PR detection: Strava `best_efforts` `pr_rank` for standard distances (5K, 10K, Half-Marathon, Marathon); pace-based fallback for non-standard (4 Mi, 5 Mi, 10 Mi, 12 Mi)
- PR badges: "PR" (gold `#fee440`), "2nd" (silver `#c0c0c0`), "3rd" (bronze `#cd7f32`)
- `data/race_best_efforts.json` — persisted to `dashboard-data` branch; re-fetched every sync to stay current when new PRs are set
- `data/race_heartrate.json` — persisted to `dashboard-data`; `{activity_id: {avg, max}}`. Captured in the same detail fetch as best_efforts (`_enrich_race_details` in `sync_strava.py`). Incremental: a race is fetched for HR only if it has no cached entry yet (HR is immutable once recorded), so the first sync after deploy backfills all history; the `full_backfill` workflow toggle deletes this file to force a full HR re-fetch. `avg_hr` is threaded through `normalize.py` → `data.json` race activities (rounded int). Only present where an HR monitor was worn.
- Tooltips on all race-day heatmap cells show "Race · pace" in addition to normal activity info
- Race days get an orange ring border (`#fb5607`, `outline: 2px solid`) on heatmap cells — preserves type color fill
- False positives (naming errors): add the Strava activity ID to `activities.exclude_race_ids` in `config.yaml`

### Year card metric reset (Total Activities button)
In `buildCard` in `app.js`, the "Total Activities" stat card is now a `button` (was a plain `div`).
- Shows as active (highlighted) when no other metric is selected (the default count view)
- When Distance / Time / Elevation is active, clicking Total Activities resets back to the default count view — equivalent to clicking the active metric card a second time to deselect it
- Both paths still work: re-clicking the active metric card toggles it off, or clicking Total Activities resets it

### Layout centering
`justify-content: center` added to `.card-body` and `.more-stats` in `index.html` so year card heatmaps and the Activity Frequency graphs center horizontally within their cards on wider viewports. No visual change on mobile (stacked layouts use `1fr` columns which already fill full width).
