"""
Analytics layer.

Every function here is a pure computation over the in-memory data structures
exposed by :mod:`app.data`. Heavy aggregates that are reused on many pages
are computed once at import time and cached as module-level constants, so
each HTTP request is just a dictionary lookup.

Naming convention:
    - ``compute_*``  : on-demand per-request computations (cheap)
    - ``LEAGUE_*``   : pre-computed league-wide aggregates
    - ``team_*``     : team-scoped helpers (parameterized)
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .data import (
    ALL_PICKS,
    ALL_SEASON_ROWS,
    ALL_TEAMS,
    GROUP_ORDER,
    PICKS_BY_FRANCHISE,
    PICKS_BY_YEAR,
    SEASONS_BY_FRANCHISE,
    SEASONS_BY_YEAR,
    TEAMS_BY_ABB,
    teams_in_conference,
    teams_in_division,
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _decade(year: int) -> str:
    """``1973 -> "1970s"``. Used as a chart bucket label."""
    return f"{(year // 10) * 10}s"


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


# ---------------------------------------------------------------------------
# League-wide aggregates (computed once at import)
# ---------------------------------------------------------------------------

def _build_league_aggregates() -> dict[str, Any]:
    """Compute the league dashboard's headline metrics + chart datasets."""
    total_picks = len(ALL_PICKS)
    hof_picks = [p for p in ALL_PICKS if p["hall_of_fame"]]

    # HoF rate by decade — tells the story of how draft "hit rate" evolves.
    decade_total: Counter[str] = Counter()
    decade_hof: Counter[str] = Counter()
    for p in ALL_PICKS:
        d = _decade(p["year"])
        decade_total[d] += 1
        if p["hall_of_fame"]:
            decade_hof[d] += 1
    decades = sorted(decade_total.keys())
    hof_rate_by_decade = [
        {
            "decade": d,
            "picks": decade_total[d],
            "hof": decade_hof[d],
            "hof_rate_pct": round(100 * _safe_div(decade_hof[d], decade_total[d]), 1),
        }
        for d in decades
    ]

    # Position-group distribution across the whole dataset
    group_counts: Counter[str] = Counter(p["position_group"] for p in ALL_PICKS)
    position_distribution = [
        {"group": g, "count": group_counts.get(g, 0)} for g in GROUP_ORDER
    ]

    # Position-group trends across decades — how draft priorities shifted
    by_dec_group: dict[str, Counter[str]] = defaultdict(Counter)
    for p in ALL_PICKS:
        by_dec_group[_decade(p["year"])][p["position_group"]] += 1
    position_trends = {
        "decades": decades,
        "series": {
            g: [by_dec_group[d].get(g, 0) for d in decades] for g in GROUP_ORDER
        },
    }

    # Colleges that produced the most HoFers
    college_hof: Counter[str] = Counter(p["college"] for p in hof_picks if p["college"])
    top_hof_colleges = [
        {"college": c, "count": n} for c, n in college_hof.most_common(10)
    ]

    # Most-drafted colleges overall (volume, not HoF)
    college_volume: Counter[str] = Counter(
        p["college"] for p in ALL_PICKS if p["college"]
    )
    top_volume_colleges = [
        {"college": c, "count": n} for c, n in college_volume.most_common(10)
    ]

    # HoF leaderboard by current franchise
    franchise_hof: Counter[str] = Counter(
        p["franchise"] for p in hof_picks if p["franchise"] in TEAMS_BY_ABB
    )
    franchise_total: Counter[str] = Counter(
        p["franchise"] for p in ALL_PICKS if p["franchise"] in TEAMS_BY_ABB
    )
    hof_by_team = sorted(
        (
            {
                "abbr": abbr,
                "team": TEAMS_BY_ABB[abbr]["team_name"],
                "hof": franchise_hof.get(abbr, 0),
                "picks": franchise_total.get(abbr, 0),
                "hit_rate_pct": round(
                    100 * _safe_div(franchise_hof.get(abbr, 0), franchise_total.get(abbr, 0)),
                    1,
                ),
            }
            for abbr in TEAMS_BY_ABB
        ),
        key=lambda r: (-r["hof"], -r["hit_rate_pct"]),
    )

    return {
        "totals": {
            "draft_years": len({p["year"] for p in ALL_PICKS}),
            "season_years": len({s["season"] for s in ALL_SEASON_ROWS}),
            "picks": total_picks,
            "hof": len(hof_picks),
            "teams": len(ALL_TEAMS),
            "hof_rate_pct": round(100 * _safe_div(len(hof_picks), total_picks), 1),
        },
        "hof_rate_by_decade": hof_rate_by_decade,
        "position_distribution": position_distribution,
        "position_trends": position_trends,
        "top_hof_colleges": top_hof_colleges,
        "top_volume_colleges": top_volume_colleges,
        "hof_by_team": hof_by_team,
    }


# Computed once at import; reused on every request.
LEAGUE: dict[str, Any] = _build_league_aggregates()


# ---------------------------------------------------------------------------
# Team-scoped analytics
# ---------------------------------------------------------------------------

def team_summary(abbr: str) -> dict[str, Any]:
    """
    Compute the full battle-card payload for one franchise.

    Includes headline stats, time-series for the charts, the HoF list,
    position breakdown, and the post-pick improvement correlation.
    """
    abbr = abbr.upper()
    team = TEAMS_BY_ABB[abbr]
    picks = sorted(PICKS_BY_FRANCHISE.get(abbr, []), key=lambda p: p["year"])
    seasons = SEASONS_BY_FRANCHISE.get(abbr, [])

    hof_picks = [p for p in picks if p["hall_of_fame"]]
    avg_slot = _safe_div(sum(p["overall_pick"] or 0 for p in picks), len(picks))
    earliest_pick = min((p["overall_pick"] for p in picks if p["overall_pick"]), default=None)
    earliest_pick_entry = next((p for p in picks if p["overall_pick"] == earliest_pick), None)

    # Position group breakdown for this franchise
    group_counts: Counter[str] = Counter(p["position_group"] for p in picks)
    position_breakdown = [
        {"group": g, "count": group_counts.get(g, 0)} for g in GROUP_ORDER
    ]

    # Pick-slot history time-series
    pick_slot_series = [
        {"year": p["year"], "overall_pick": p["overall_pick"], "player": p["player"]}
        for p in picks
        if p["overall_pick"] is not None
    ]

    # Win/loss history time-series
    record_series = [
        {
            "season": s["season"],
            "wins": s["wins"],
            "losses": s["losses"],
            "ties": s["ties"],
            "win_pct": s["win_pct"],
            "point_differential": s["point_differential"],
            "playoff_marker": s["playoff_marker"],
        }
        for s in seasons
    ]

    # ----- Draft -> next-season improvement -----------------------------
    # For every *season* where this franchise had at least one top-10 pick,
    # compute the wins-delta from the prior season to that season. We
    # aggregate at the (team, draft_year) level — not per pick — because a
    # single team can pick multiple times in Round 1 of the same year (via
    # trades) and the on-field outcome is one shared result, not N copies.
    # Example: Cleveland in 2018 picked at #1 (Baker Mayfield) and #4 (Denzel
    # Ward); both deltas are the same +7 wins — counting them twice would
    # bias the average.
    seasons_by_year = {s["season"]: s for s in seasons}
    picks_by_draft_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for p in picks:
        if p["overall_pick"] and p["overall_pick"] <= 10:
            picks_by_draft_year[p["year"]].append(p)

    top10_impacts: list[dict[str, Any]] = []
    for draft_year, year_picks in sorted(picks_by_draft_year.items()):
        prior = seasons_by_year.get(draft_year - 1)
        new = seasons_by_year.get(draft_year)
        if not prior or not new:
            continue
        # Headline pick = the earliest (lowest overall_pick) for that team-year
        headline = min(year_picks, key=lambda p: p["overall_pick"])
        top10_impacts.append({
            "year": draft_year,
            "pick": headline["overall_pick"],
            "player": headline["player"],
            "additional_picks": [
                {"pick": p["overall_pick"], "player": p["player"]}
                for p in year_picks if p is not headline
            ],
            "prior_wins": prior["wins"],
            "new_wins": new["wins"],
            "delta": new["wins"] - prior["wins"],
            "hof": any(p["hall_of_fame"] for p in year_picks),
        })

    # Average delta is per *team-season* with a top-10 pick (one row each).
    avg_top10_delta = (
        round(sum(i["delta"] for i in top10_impacts) / len(top10_impacts), 2)
        if top10_impacts
        else None
    )

    # ----- Records summary ---------------------------------------------
    total_wins = sum(s["wins"] for s in seasons)
    total_losses = sum(s["losses"] for s in seasons)
    total_ties = sum(s["ties"] for s in seasons)
    seasons_played = len(seasons)
    overall_win_pct = round(
        _safe_div(total_wins + 0.5 * total_ties, total_wins + total_losses + total_ties),
        3,
    )
    playoff_seasons = sum(1 for s in seasons if s["playoff_marker"])

    # Best and worst single-season records
    best_season = max(seasons, key=lambda s: (s["win_pct"], s["wins"]), default=None)
    worst_season = min(seasons, key=lambda s: (s["win_pct"], s["wins"]), default=None)

    return {
        "team": team,
        "totals": {
            "picks": len(picks),
            "hof": len(hof_picks),
            "hit_rate_pct": round(100 * _safe_div(len(hof_picks), len(picks)), 1),
            "avg_overall_pick": round(avg_slot, 1) if picks else 0,
            "earliest_pick": earliest_pick,
            "earliest_pick_year": earliest_pick_entry["year"] if earliest_pick_entry else None,
            "earliest_pick_player": earliest_pick_entry["player"] if earliest_pick_entry else None,
            "seasons_played": seasons_played,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "total_ties": total_ties,
            "overall_win_pct": overall_win_pct,
            "playoff_seasons": playoff_seasons,
            "avg_top10_next_season_delta": avg_top10_delta,
        },
        "hof_picks": [
            {
                "year": p["year"],
                "player": p["player"],
                "position": p["position"],
                "college": p["college"],
                "overall_pick": p["overall_pick"],
            }
            for p in hof_picks
        ],
        "all_picks": picks,
        "position_breakdown": position_breakdown,
        "pick_slot_series": pick_slot_series,
        "record_series": record_series,
        "top10_impacts": top10_impacts,
        "best_season": best_season,
        "worst_season": worst_season,
    }


# ---------------------------------------------------------------------------
# Group analytics (conference / division)
# ---------------------------------------------------------------------------

def _group_summary(franchises: list[str], label: str) -> dict[str, Any]:
    """Compute aggregate stats for an arbitrary set of current franchises."""
    picks = [p for p in ALL_PICKS if p["franchise"] in franchises]
    seasons = [s for s in ALL_SEASON_ROWS if s["franchise"] in franchises]
    hof_picks = [p for p in picks if p["hall_of_fame"]]

    # Per-team mini leaderboard
    team_rows = []
    for abbr in franchises:
        tp = PICKS_BY_FRANCHISE.get(abbr, [])
        ts = SEASONS_BY_FRANCHISE.get(abbr, [])
        hof = sum(1 for p in tp if p["hall_of_fame"])
        wins = sum(s["wins"] for s in ts)
        losses = sum(s["losses"] for s in ts)
        ties = sum(s["ties"] for s in ts)
        playoff = sum(1 for s in ts if s["playoff_marker"])
        team_rows.append({
            "abbr": abbr,
            "team": TEAMS_BY_ABB[abbr]["team_name"],
            "picks": len(tp),
            "hof": hof,
            "hit_rate_pct": round(100 * _safe_div(hof, len(tp)), 1),
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_pct": round(_safe_div(wins + 0.5 * ties, wins + losses + ties), 3),
            "playoff_seasons": playoff,
        })
    team_rows.sort(key=lambda r: (-r["hof"], -r["win_pct"]))

    # Position-group breakdown
    group_counts: Counter[str] = Counter(p["position_group"] for p in picks)
    position_breakdown = [
        {"group": g, "count": group_counts.get(g, 0)} for g in GROUP_ORDER
    ]

    return {
        "label": label,
        "totals": {
            "teams": len(franchises),
            "picks": len(picks),
            "hof": len(hof_picks),
            "hit_rate_pct": round(100 * _safe_div(len(hof_picks), len(picks)), 1),
            "wins": sum(s["wins"] for s in seasons),
            "losses": sum(s["losses"] for s in seasons),
            "ties": sum(s["ties"] for s in seasons),
            "playoff_seasons": sum(1 for s in seasons if s["playoff_marker"]),
        },
        "team_rows": team_rows,
        "position_breakdown": position_breakdown,
    }


def conference_summary(conf: str) -> dict[str, Any]:
    franchises = [t["abbreviation"] for t in teams_in_conference(conf)]
    return _group_summary(franchises, f"{conf.upper()} Conference")


def division_summary(conf: str, division: str) -> dict[str, Any]:
    franchises = [t["abbreviation"] for t in teams_in_division(conf, division)]
    return _group_summary(franchises, f"{conf.upper()} {division.title()}")
