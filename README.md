# NFL Draft Dashboard

A Flask storytelling dashboard for **57 years of NFL first-round draft picks (1970–2026)** combined with **season standings (1970–2025)**. The app turns the raw history into narrative insights at the league, conference, division, and team level.

## What it does

- **League view** (`/`) — Headline metrics for the modern NFL: pick volume, Hall of Fame rate by decade, position-group distribution, top HoF-producing colleges, and franchise HoF leaderboard.
- **Conference / Division views** (`/conference/<AFC|NFC>`, `/division/<conf>/<div>`) — Aggregate draft and on-field performance scoped to a group of franchises.
- **Team battle card** (`/team/<abbr>`) — Wins-per-season, pick-slot history, position breakdown, point-differential, full Hall of Famers list, top-10 pick impact (prior season → following season win delta), and every Round-1 pick the franchise has ever made.
- **The Story** — Every page renders a short narrative section that summarises the numbers in plain English.

A small JSON API mirrors the views (`/api/league`, `/api/team/<abbr>`, `/api/conference/<conf>`, `/api/division/<conf>/<div>`).

## Architecture

The app is intentionally small and layered. Each module has one job; routes are a thin presentation layer.

```
main.py              Flask routes + JSON API (thin)
app/
  data.py            JSON load, lookups, historical-abbreviation
                     normalization (BOS→NE, OAK→LV, …), startup
                     integrity check
  analytics.py       Pure computations — league aggregates memoized
                     at import; per-team / per-group summaries on demand
  storytelling.py    Numbers → narrative sentences
templates/
  base.html          Shared layout, dark UI, sticky nav, Chart.js (SRI-pinned)
  league.html        League dashboard
  group.html         Conference & division (one template, two scopes)
  team.html          Team battle card
data/
  nfl_data.json      Canonical dataset (5.5 MB, loaded once at startup)
```

### Design choices worth knowing

- **Load once, serve from memory.** The 5.5 MB JSON is parsed at import time into normalized lookups; no request touches disk or sends the full payload to the browser.
- **Historical franchise mapping.** Boston Patriots, Oakland/LA Raiders, St. Louis Rams, Houston Oilers, etc. are normalized to their current franchise so cross-era stats roll up correctly. A startup validator fails loudly if the source data ever introduces an unmapped code.
- **Top-10 pick impact is per-season, not per-pick.** A team that picked twice in the top 10 of the same draft (e.g. Cleveland 2018: Mayfield #1 + Ward #4) shares one on-field outcome — counting it twice would bias the average.
- **Subresource Integrity on CDN scripts.** Chart.js is loaded with an `integrity` hash so a compromised CDN can't inject code.

## Running locally

Requires Python 3.11+.

```bash
pip install flask
python3 main.py
```

The app serves on `http://0.0.0.0:5000`.

## Data

`data/nfl_data.json` contains:

- `metadata` — generation info
- `current_nfl_teams_2026_2027` — 32 current franchises with conference/division
- `drafts` — every Round-1 draft 1970–2026, plus that season's standings and prior-season standings (with player Hall-of-Fame flags)
- `season_results_1970_2025` — regular-season win/loss/tie and playoff results

## Stack

Flask · Jinja2 · Chart.js (CDN, SRI-pinned) · Python 3.11. No database, no build step, no client-side framework.
