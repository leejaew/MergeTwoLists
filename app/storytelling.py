"""
Storytelling layer.

Turns numerical aggregates from :mod:`app.analytics` into a small number of
human-readable, headline-style sentences. The goal is to give every page a
voice — a few "did you know" insights so the dashboard reads like analysis,
not a database dump.

Each generator returns a list of plain strings (no HTML), so the templates
stay simple and the same insight can be re-used in an API response later.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .data import PICKS_BY_FRANCHISE, TEAMS_BY_ABB
from . import analytics


def league_insights() -> list[str]:
    """High-level narrative bullets for the league dashboard."""
    L = analytics.LEAGUE
    totals = L["totals"]
    stories: list[str] = []

    stories.append(
        f"Across {totals['draft_years']} drafts ({totals['picks']} first-round picks), "
        f"{totals['hof']} players ({totals['hof_rate_pct']}%) have reached the Hall of Fame."
    )

    # Best HoF-producing decade
    best_decade = max(L["hof_rate_by_decade"], key=lambda d: d["hof_rate_pct"])
    stories.append(
        f"The {best_decade['decade']} were the most prolific era for Hall of Fame talent — "
        f"{best_decade['hof']} of {best_decade['picks']} first-round picks "
        f"({best_decade['hof_rate_pct']}%) ended up in Canton."
    )

    # Top HoF franchise
    top_team = L["hof_by_team"][0]
    stories.append(
        f"{top_team['team']} lead the league with {top_team['hof']} Hall of Famers "
        f"selected in Round 1 ({top_team['hit_rate_pct']}% hit rate on {top_team['picks']} picks)."
    )

    # Top HoF college
    if L["top_hof_colleges"]:
        top_college = L["top_hof_colleges"][0]
        stories.append(
            f"{top_college['college']} is the all-time leader for producing first-round "
            f"Hall of Famers, with {top_college['count']} alumni."
        )

    # Most-drafted position group
    top_group = max(L["position_distribution"], key=lambda g: g["count"])
    stories.append(
        f"{top_group['group']} is the most-drafted position group in Round 1, "
        f"selected {top_group['count']} times across the dataset."
    )

    return stories


def team_insights(team_summary: dict[str, Any]) -> list[str]:
    """Narrative bullets for a single team's battle card."""
    stories: list[str] = []
    t = team_summary["team"]
    tot = team_summary["totals"]
    picks = team_summary["all_picks"]

    stories.append(
        f"{t['team_name']} have made {tot['picks']} first-round selections and produced "
        f"{tot['hof']} Hall of Famers ({tot['hit_rate_pct']}% hit rate)."
    )

    if tot["earliest_pick_player"]:
        stories.append(
            f"Their highest selection on record is #{tot['earliest_pick']} overall in "
            f"{tot['earliest_pick_year']}, when they took {tot['earliest_pick_player']}."
        )

    if tot["seasons_played"]:
        stories.append(
            f"Across {tot['seasons_played']} seasons in this dataset they have a "
            f"{tot['total_wins']}-{tot['total_losses']}-{tot['total_ties']} record "
            f"({tot['overall_win_pct']:.3f}) and reached the playoffs {tot['playoff_seasons']} times."
        )

    delta = tot["avg_top10_next_season_delta"]
    if delta is not None:
        verb = "added" if delta > 0 else "lost" if delta < 0 else "saw no change in"
        # Cases are counted per team-season, not per pick — multiple top-10
        # picks in the same draft year share one shared on-field outcome.
        stories.append(
            f"In seasons after holding at least one top-10 pick, {t['team_name']} "
            f"{verb} an average of {abs(delta):.1f} wins versus the prior year "
            f"({len(team_summary['top10_impacts'])} such seasons in the data)."
        )

    # Most common position drafted
    if picks:
        pos_counts: Counter[str] = Counter(p["position_group"] for p in picks)
        top_pos, top_pos_n = pos_counts.most_common(1)[0]
        stories.append(
            f"Their most-drafted position group is {top_pos}, taken {top_pos_n} times in Round 1."
        )

    # Most common college
    college_counts: Counter[str] = Counter(p["college"] for p in picks if p["college"])
    if college_counts:
        top_col, top_col_n = college_counts.most_common(1)[0]
        if top_col_n > 1:
            stories.append(
                f"{top_col} is their go-to talent pipeline, supplying {top_col_n} first-round picks."
            )

    # Best / worst seasons
    if team_summary["best_season"]:
        b = team_summary["best_season"]
        stories.append(
            f"Their best season was {b['season']}: {b['wins']}-{b['losses']}-{b['ties']} "
            f"(+{b['point_differential']} point differential)."
        )
    if team_summary["worst_season"]:
        w = team_summary["worst_season"]
        stories.append(
            f"Their worst was {w['season']}: {w['wins']}-{w['losses']}-{w['ties']} "
            f"({w['point_differential']:+d} point differential)."
        )

    return stories


def group_insights(group_summary: dict[str, Any]) -> list[str]:
    """Narrative bullets for a conference or division page."""
    stories: list[str] = []
    g = group_summary
    t = g["totals"]

    stories.append(
        f"The {g['label']} spans {t['teams']} current franchise(s) and accounts for "
        f"{t['picks']} first-round picks and {t['hof']} Hall of Famers "
        f"({t['hit_rate_pct']}% hit rate)."
    )

    if g["team_rows"]:
        leader = g["team_rows"][0]
        stories.append(
            f"{leader['team']} lead the group with {leader['hof']} Hall of Fame selections."
        )
        top_record = max(g["team_rows"], key=lambda r: r["win_pct"])
        stories.append(
            f"{top_record['team']} carry the strongest all-time regular-season record at "
            f"{top_record['win_pct']:.3f}."
        )

    top_pos = max(g["position_breakdown"], key=lambda r: r["count"])
    stories.append(
        f"Across this group, {top_pos['group']} is the most frequently selected "
        f"position group in Round 1 ({top_pos['count']} picks)."
    )

    return stories
