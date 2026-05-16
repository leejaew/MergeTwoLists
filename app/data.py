"""
Data layer for the NFL draft dashboard.

Responsibilities:
    - Read the bundled JSON dataset exactly once at import time.
    - Build read-only lookup structures (by team, by year, etc.).
    - Normalize historical team abbreviations to current franchise codes so
      analytics can roll up correctly across relocations / renames.

Design notes:
    Loading happens at import (module-level) so the cost is paid once per
    process, not per HTTP request. Because Flask is run as a long-lived
    process, every route gets O(1) access to pre-built dictionaries.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "nfl_data.json"
)

# ---------------------------------------------------------------------------
# Historical abbreviation map -> current franchise abbreviation.
#
# Source data uses historical abbreviations (e.g. "BOS" for the Boston
# Patriots before they became the New England Patriots). We collapse them
# to the modern franchise so we can attribute all drafts and seasons to the
# team that exists today. Year-sensitive cases are resolved with a callable.
# ---------------------------------------------------------------------------

# Simple aliases (no temporal ambiguity)
_STATIC_ABBR_MAP: dict[str, str] = {
    # Patriots
    "BOS": "NE", "NWE": "NE",
    # Raiders
    "OAK": "LV", "RAI": "LV", "LVR": "LV",
    # Chargers
    "SDG": "LAC", "SD": "LAC",
    # Cardinals
    "PHO": "ARI",
    # Titans (Houston Oilers -> Tennessee Oilers -> Tennessee Titans)
    "HOUO": "TEN", "TENO": "TEN",
    # Rams (Cleveland/St. Louis/LA all map to LAR)
    "RAM": "LAR",
    # Common ones the source uses in alt forms
    "GNB": "GB", "KAN": "KC", "NOR": "NO", "SFO": "SF", "TAM": "TB",
}


def _resolve_abbr(raw: str, year: int | None = None) -> str:
    """
    Map a historical abbreviation to its current franchise code.

    The ``STL`` and ``LA`` codes are temporally ambiguous because more than
    one franchise has used them, so we disambiguate by year.

    Args:
        raw: Source abbreviation as it appears in the JSON file.
        year: Season or draft year, used only for ambiguous codes.

    Returns:
        Current 2026 franchise abbreviation (e.g. ``"LAR"``, ``"ARI"``).
    """
    if raw in _STATIC_ABBR_MAP:
        return _STATIC_ABBR_MAP[raw]

    if raw == "STL":
        # Cardinals played in STL 1960-1987, Rams in STL 1995-2015.
        if year is not None and year <= 1987:
            return "ARI"
        return "LAR"

    if raw == "LA":
        # Both LAC and LAR use LA in some sources. Standings data uses "LA"
        # for the Rams; LAC sources use "LAC" or "SD".
        return "LAR"

    return raw


# ---------------------------------------------------------------------------
# Position group normalization
#
# Round-one picks across 1970-2026 use a mix of position labels (e.g. "T"
# vs "OT", "SAF" vs "S"). For analytics we bucket them into stable groups
# while keeping the raw label available on each pick.
# ---------------------------------------------------------------------------

POSITION_GROUPS: dict[str, str] = {
    "QB": "QB",
    "RB": "RB", "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "T": "OL", "OT": "OL", "G": "OL", "OG": "OL", "C": "OL", "OL": "OL",
    "DE": "DL", "DT": "DL", "NT": "DL", "DL": "DL",
    "LB": "LB", "ILB": "LB", "OLB": "LB",
    "CB": "DB", "S": "DB", "SAF": "DB", "DB": "DB",
    "K": "ST", "P": "ST",
}

GROUP_ORDER = ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "ST"]


def position_group(pos: str) -> str:
    """Return the canonical position group bucket for a raw position label."""
    return POSITION_GROUPS.get(pos, pos)


# ---------------------------------------------------------------------------
# Dataset load (executed once at import)
# ---------------------------------------------------------------------------

with open(DATA_PATH, "r") as _f:
    _raw: dict[str, Any] = json.load(_f)

METADATA: dict[str, Any] = _raw["metadata"]
ALL_TEAMS: list[dict[str, Any]] = _raw["current_nfl_teams_2026_2027"]
_DRAFTS_RAW: list[dict[str, Any]] = _raw["drafts"]

# ---------------------------------------------------------------------------
# Build lookups
# ---------------------------------------------------------------------------

TEAMS_BY_ABB: dict[str, dict[str, Any]] = {t["abbreviation"]: t for t in ALL_TEAMS}

# {conference: {division: [team, ...]}}
TEAMS_BY_CONF: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
    lambda: defaultdict(list)
)
for _t in ALL_TEAMS:
    TEAMS_BY_CONF[_t["conference"]][_t["division"]].append(_t)

# Flatten every Round-1 pick once with year + normalized franchise.
# This is the master list every analytics computation will iterate.
ALL_PICKS: list[dict[str, Any]] = []
for _draft in _DRAFTS_RAW:
    _yr = _draft["year"]
    for _p in _draft.get("picks", []):
        franchise = _resolve_abbr(
            _p.get("current_franchise_abbreviation") or _p.get("source_team_abbreviation", ""),
            _yr,
        )
        ALL_PICKS.append({
            "year": _yr,
            "draft_order": _p.get("draft_order"),
            "overall_pick": _p.get("overall_pick"),
            "source_team_abbreviation": _p.get("source_team_abbreviation"),
            "franchise": franchise,
            "team_name_at_pick": _p.get("team_name"),
            "player": _p.get("player"),
            "position": _p.get("position"),
            "position_group": position_group(_p.get("position", "")),
            "college": _p.get("college"),
            "hall_of_fame": bool(_p.get("hall_of_fame")),
        })

# Picks bucketed by current franchise
PICKS_BY_FRANCHISE: dict[str, list[dict[str, Any]]] = defaultdict(list)
for _p in ALL_PICKS:
    PICKS_BY_FRANCHISE[_p["franchise"]].append(_p)

# Picks bucketed by draft year
PICKS_BY_YEAR: dict[int, list[dict[str, Any]]] = defaultdict(list)
for _p in ALL_PICKS:
    PICKS_BY_YEAR[_p["year"]].append(_p)

# ---------------------------------------------------------------------------
# Season standings: flatten to one row per (franchise, season).
#
# Each draft entry contains a season_results array (the season *that year*).
# The 2026 entry has empty season_results because the season is incomplete,
# but its prior_season_final_results array holds the 2025 final standings.
# ---------------------------------------------------------------------------

ALL_SEASON_ROWS: list[dict[str, Any]] = []
_seen_seasons: set[tuple[str, int]] = set()
for _draft in _DRAFTS_RAW:
    _yr = _draft["year"]
    for _row in _draft.get("season_results", []) or []:
        season = _row.get("season", _yr)
        franchise = _resolve_abbr(
            _row.get("team_abbreviation_source_normalized", ""), season
        )
        key = (franchise, season)
        if key in _seen_seasons:
            continue  # de-duplicate; same season can appear in multiple drafts
        _seen_seasons.add(key)
        ALL_SEASON_ROWS.append({
            "season": season,
            "franchise": franchise,
            "team_name": _row.get("team_name"),
            "conference": _row.get("conference"),
            "division": _row.get("division"),
            "division_rank": _row.get("division_rank"),
            "wins": _row.get("wins", 0),
            "losses": _row.get("losses", 0),
            "ties": _row.get("ties", 0),
            "win_pct": _row.get("win_percentage", 0.0),
            "points_for": _row.get("points_for", 0),
            "points_against": _row.get("points_against", 0),
            "point_differential": _row.get("point_differential", 0),
            "playoff_marker": _row.get("playoff_marker"),
            "conference_rank": _row.get("conference_rank_by_record"),
        })

# Pull 2025 final standings out of the 2026 draft's prior_season_final_results
# so we cover the most recent completed season even though the 2026 season
# itself isn't done yet.
for _draft in _DRAFTS_RAW:
    if _draft["year"] != 2026:
        continue
    for _row in _draft.get("prior_season_final_results", []) or []:
        season = _row.get("season", 2025)
        franchise = _resolve_abbr(
            _row.get("team_abbreviation_source_normalized", ""), season
        )
        key = (franchise, season)
        if key in _seen_seasons:
            continue
        _seen_seasons.add(key)
        ALL_SEASON_ROWS.append({
            "season": season,
            "franchise": franchise,
            "team_name": _row.get("team_name"),
            "conference": _row.get("conference"),
            "division": _row.get("division"),
            "division_rank": _row.get("division_rank"),
            "wins": _row.get("wins", 0),
            "losses": _row.get("losses", 0),
            "ties": _row.get("ties", 0),
            "win_pct": _row.get("win_percentage", 0.0),
            "points_for": _row.get("points_for", 0),
            "points_against": _row.get("points_against", 0),
            "point_differential": _row.get("point_differential", 0),
            "playoff_marker": _row.get("playoff_marker"),
            "conference_rank": _row.get("conference_rank_by_record"),
        })

# Seasons bucketed by franchise (sorted chronologically for time-series charts)
SEASONS_BY_FRANCHISE: dict[str, list[dict[str, Any]]] = defaultdict(list)
for _s in ALL_SEASON_ROWS:
    SEASONS_BY_FRANCHISE[_s["franchise"]].append(_s)
for _v in SEASONS_BY_FRANCHISE.values():
    _v.sort(key=lambda r: r["season"])

# Seasons bucketed by season year (for league-wide aggregates)
SEASONS_BY_YEAR: dict[int, list[dict[str, Any]]] = defaultdict(list)
for _s in ALL_SEASON_ROWS:
    SEASONS_BY_YEAR[_s["season"]].append(_s)

DRAFT_YEARS: list[int] = sorted({p["year"] for p in ALL_PICKS})
SEASON_YEARS: list[int] = sorted({s["season"] for s in ALL_SEASON_ROWS})

# Pre-sorted view of all current teams for nav dropdowns. Computed once
# at import so the per-request context processor is a pure lookup.
TEAMS_SORTED_BY_NAME: list[dict[str, Any]] = sorted(
    ALL_TEAMS, key=lambda t: t["team_name"]
)

# ---------------------------------------------------------------------------
# Startup integrity check.
#
# Every pick and every season row must resolve to a current franchise that
# exists in TEAMS_BY_ABB. If the upstream JSON schema ever introduces a new
# historical abbreviation, this check fails loudly at boot rather than
# silently mis-attributing data to no franchise at all. Cheap to run once.
# ---------------------------------------------------------------------------

def _validate_franchise_mapping() -> None:
    unmapped_picks = {p["franchise"] for p in ALL_PICKS} - set(TEAMS_BY_ABB)
    unmapped_seasons = {s["franchise"] for s in ALL_SEASON_ROWS} - set(TEAMS_BY_ABB)
    if unmapped_picks or unmapped_seasons:
        raise RuntimeError(
            "Unmapped franchise abbreviations detected — update _STATIC_ABBR_MAP "
            f"or _resolve_abbr. picks={sorted(unmapped_picks)} "
            f"seasons={sorted(unmapped_seasons)}"
        )


_validate_franchise_mapping()


def team(abbr: str) -> dict[str, Any] | None:
    """Look up a current franchise by its modern abbreviation (case-insensitive)."""
    return TEAMS_BY_ABB.get(abbr.upper())


def teams_in_conference(conf: str) -> list[dict[str, Any]]:
    """Return all current teams in a given conference (``"AFC"`` or ``"NFC"``)."""
    return [
        t for divs in TEAMS_BY_CONF.get(conf.upper(), {}).values() for t in divs
    ]


def teams_in_division(conf: str, division: str) -> list[dict[str, Any]]:
    """Return teams in a specific conference + division (e.g. ``"AFC"``, ``"East"``)."""
    return list(TEAMS_BY_CONF.get(conf.upper(), {}).get(division.title(), []))
