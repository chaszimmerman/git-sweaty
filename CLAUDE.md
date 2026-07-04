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
- `data/race_heartrate.json` — persisted to `dashboard-data`; `{activity_id: {avg, max, temp}}`. Captured in the same detail fetch as best_efforts (`_enrich_race_details` in `sync_strava.py`). `avg`/`max` are HR (bpm); `temp` is Strava `average_temp` in **°C** (device-recorded, only present where the recording device has a temp sensor — often wrist/skin-influenced, not pure ambient). Incremental: a race is fetched only if it has no cached entry yet **or** its entry predates temp capture (missing the `temp` key) — both HR and temp are immutable once recorded, so this backfills temp across all history on the first sync after deploy without needing a `full_backfill`. `avg_hr` is threaded through `normalize.py` → `generate_heatmaps.py` → `data.json` race activities (rounded int). `avg_temp_f` follows the same path, converted °C→°F in `normalize.py` (`round(c*9/5+32)`). Both only present where the sensor recorded them. Note `_load_activities` in `generate_heatmaps.py` whitelists race fields — new race fields must be copied there or they get dropped from `data.json`.
- Multi-year progression chart (`buildRaceProgressionChart`): races sharing a normalized name (`raceSeriesKey` — case/punct/whitespace-tolerant; names kept byte-identical per series in Strava) are grouped into a series. A series spanning ≥2 years is "chartable": its rows get a rotating chevron + pointer cursor, and clicking inlines an accordion (one open at a time) hand-rolled SVG dual-axis chart beneath the clicked row. X = year; left Y = pace **inverted** (faster = higher, so improvement trends up); right Y = avg HR (bpm). Pace line always drawn (cyan `#38bdf8`); HR line (rose `#f43f5e`) skips missing-HR years, falls back to a "No heart rate data" note if a series has none. Chart data is the **full cross-year series regardless of the active year-chip filter** (clicking any year's row shows the same chart). Numeric axis ticks intentionally omitted — per-point value labels show exact pace/HR. Row identity is `date::name` because `data.json` activities carry no `id`. Below the x-axis, a temperature heat-strip (Option B design) renders one continuous colored cell per year — an **absolute** °F color ramp (`_tempRgbF`: ≤40° blue → 60° emerald → 75° amber → ≥90° red, so a given temp is the same color across every series), with the °F value drawn inside each cell (contrast text color picked by luminance) and a `—` neutral cell for years missing temp. The strip only appears when ≥1 year in the series has temp; when present, `H`/`mB` grow together so the plot area geometry stays byte-identical to the no-strip layout. Legend gains a gradient swatch. Temp intentionally encoded as background "conditions" context, not a third performance line/axis.
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
