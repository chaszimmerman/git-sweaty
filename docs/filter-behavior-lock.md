# Filter Behavior Lock

This document captures the current filter interaction contract in `site/app.js`.
Refactors should preserve these behaviors exactly unless a deliberate product change is approved.

## Top Row Buttons

### Type button row (`toggleType`)

1. Fresh-load default state is implicit all (`allTypesMode = true`, `selectedTypes` empty) with no active top-row type chip highlight.
2. Clicking `all` from implicit all switches to explicit all (`allTypesMode = false`, `selectedTypes` contains every type).
3. Clicking `all` from explicit all toggles back to implicit all.
4. Clicking a specific type while in all mode exits all mode and selects only that type.
5. Clicking a selected type removes it.
6. If the last selected type is removed, the state snaps back to all mode.

### Year button row (`toggleYear`)

1. Fresh-load default state is implicit all (`allYearsMode = true`, `selectedYears` empty) with no active top-row year chip highlight.
2. Clicking `all` from implicit all switches to explicit all (`allYearsMode = false`, `selectedYears` contains every visible year).
3. Clicking `all` from explicit all toggles back to implicit all.
4. Clicking a specific year while in all mode exits all mode and selects only that year.
5. Clicking a selected year removes it.
6. If the last selected year is removed, the state snaps back to all mode.
7. Year values outside `currentVisibleYears` are ignored.

### Month button row (`toggleMonth`)

1. Fresh-load default state is implicit all (`allMonthsMode = true`, `selectedMonths` empty) with no active top-row month chip highlight.
2. Clicking `all` from implicit all switches to explicit all (`allMonthsMode = false`, `selectedMonths` contains all twelve months).
3. Clicking `all` from explicit all toggles back to implicit all.
4. Clicking a specific month while in all mode exits all mode and selects only that month.
5. Clicking a selected month removes it.
6. If the last selected month is removed, the state snaps back to all mode.
7. The month domain is always the fixed calendar Jan–Dec (`MONTH_INDICES`, 0-based); values outside 0–11 are ignored.

## Dropdown Menus

### Type dropdown (`toggleTypeMenu`)

1. Clicking `all` in the open menu from a partial draft selection updates the type draft state to all mode and clears draft explicit selections.
2. Clicking `all` while already in all mode (or while explicit-all is selected) toggles to non-all mode with an empty set.
3. Clicking a specific type while in all mode exits all mode and draft-selects all types except the clicked type.
4. Clicking a selected type removes it from the draft; clicking an unselected type adds it to the draft.
5. Invalid types are ignored.

### Year dropdown (`toggleYearMenu`)

1. Clicking `all` in the open menu from a partial draft selection updates the year draft state to all mode and clears draft explicit selections.
2. Clicking `all` while already in all mode (or while explicit-all is selected) toggles to non-all mode with an empty set.
3. Clicking a specific year while in all mode exits all mode and draft-selects all visible years except the clicked year.
4. Clicking a selected year removes it from the draft; clicking an unselected year adds it to the draft.
5. Invalid/non-visible years are ignored.

### Month dropdown (`toggleMonthMenu`)

1. Clicking `all` in the open menu from a partial draft selection updates the month draft state to all mode and clears draft explicit selections.
2. Clicking `all` while already in all mode (or while explicit-all is selected) toggles to non-all mode with an empty set.
3. Clicking a specific month while in all mode exits all mode and draft-selects all months except the clicked month.
4. Clicking a selected month removes it from the draft; clicking an unselected month adds it to the draft.
5. Invalid month values are ignored.

### Done button behavior (`finalizeTypeSelection`, `finalizeYearSelection`, `finalizeMonthSelection`)

1. Clicking `Done` commits the current draft state into live filter state.
2. Type selection does not auto-compress explicit-all into implicit-all after `Done`; explicit-all remains explicit.
3. Year selection still compresses explicit-all into implicit-all after `Done`.
4. Month selection compresses explicit-all (all twelve selected) into implicit-all after `Done`, like year.
5. Closing a dropdown without `Done` (outside tap or toggling closed) discards the draft and keeps live filters unchanged.
6. Opening any one of the three filter menus closes the other two and discards their drafts.

### Dropdown apply timing

1. Menu option clicks update menu UI only (checkmarks/label text) and do not rerender dashboard cards.
2. Dashboard cards rerender only when committed state changes (for example on `Done`, top-row buttons, clear, reset).

### Mobile type action button

1. On narrow/mobile layout, the type action button shows `Select All` (enabled) in implicit-all mode.
2. Pressing `Select All` on mobile switches type state to explicit all.
3. When not in implicit-all mode, the button label is `Clear` and restores implicit all when pressed.

## Summary Cards and Card-Level Filters

### Summary type cards

1. Summary type cards delegate to the same behavior as top row type buttons.

### Year metric cards and summary metric cards

1. Each year card has a single-select metric toggle (distance, time, elevation).
2. Clicking an active metric on a year card clears that year’s metric.
3. Summary metric active state is derived:
   - exactly one metric is selected across all visible years where that metric is filterable
   - any mismatch or partial applicability disables the active summary state
4. Clicking an active summary metric clears that metric for all visible years.
5. Clicking an inactive summary metric applies it to all visible years where filterable.

### Frequency fact cards and metric chips

1. Frequency fact cards are global single-select toggles.
2. Clicking an active fact clears it; clicking an inactive fact sets it active.
3. Non-filterable facts are disabled.
4. Frequency metric chips (distance, time, elevation) are single-select toggles for the frequency card heatmaps.
5. Top summary metric active state requires both:
   - exactly one derived year metric is active across visible year cards (existing rule), and
   - the frequency metric chip selection matches that same metric.
6. Clicking an inactive summary metric applies that metric to all eligible year cards and the frequency metric chip (if filterable).
7. Clicking an active summary metric clears that metric from all eligible year cards and clears the frequency metric chip.
8. Non-filterable metric chips are unavailable/unclickable and show a disabled-state appearance.
9. Clicking any summary metric card clears the active frequency fact selection (for example `Most Active Month`).

## Reset Behavior

### Reset-all enabled state

`Reset All` is enabled whenever any of the following are true:

1. Types are not in all mode.
2. Years are not in all mode.
3. Months are not in all mode.
4. Any year metric selection exists.
5. A frequency fact selection exists.
6. A frequency metric chip selection exists.

### Reset-all click

Clicking `Reset All` restores default state:

1. Type, year, and month filters reset to all mode.
2. Year metric, frequency fact, and frequency metric chip selections are cleared.
3. Visible/filterable metric/fact tracking maps are cleared.
4. Summary hover-cleared visual state is cleared.
5. On narrow/mobile layouts, the page scroll position resets to top and card horizontal scroll restoration is skipped (cards return to far-left).

## Card Scroll State

1. Each year/frequency card uses a stable scroll key per logical card identity.
2. On full dashboard rerender, horizontal `scrollLeft` is restored for matching cards when possible.
3. Scroll keys include the committed month selection (`:m:all` or `:m:5,6`), so changing the month filter intentionally resets card scroll positions.

## Month Filter Consumption

The committed month selection applies to the same areas as the year filter:

1. Summary cards (totals, active days, and the days-off denominator count only elapsed days inside selected months).
2. Activity Frequency (matrices, facts, and days-off entries).
3. Monthly Activity heatmap (only selected months' columns render; YoY badges still compare the same month in the prior year).
4. Per-year heatmap cards (full Jan–Dec grid shape is kept; in-year days outside selected months render as empty, non-interactive `.cell.month-muted` cells with no tooltip, race ring, or metric paint; stat totals reflect selected months only).
5. Races card (table rows filter by month; series/PR/medal computations are unchanged).
6. A year with no activity in the selected months drops its year card (same rule as an empty year).
7. All-months mode is a true no-op: consumers receive a null month set and behave exactly as before the month filter existed.
