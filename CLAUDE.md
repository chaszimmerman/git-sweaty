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
