"""
HTTP entry point.

This module is intentionally thin: it wires URL routes to the data layer
(:mod:`app.data`), the analytics layer (:mod:`app.analytics`), and the
storytelling layer (:mod:`app.storytelling`), then renders templates.
Every aggregation is computed elsewhere so this file stays easy to read.
"""

from __future__ import annotations

from flask import Flask, abort, jsonify, render_template, request

from app import analytics, data, storytelling

app = Flask(__name__)

DIVISION_ORDER = ["East", "North", "South", "West"]


# ---------------------------------------------------------------------------
# Template globals — exposed once so every page can render the top nav.
# ---------------------------------------------------------------------------

@app.context_processor
def _inject_nav() -> dict[str, object]:
    """Make the conference/division map and team list available to all templates."""
    return {
        "nav_conferences": {
            conf: {
                div: data.TEAMS_BY_CONF[conf][div]
                for div in DIVISION_ORDER
                if div in data.TEAMS_BY_CONF[conf]
            }
            for conf in ("AFC", "NFC")
        },
        "all_teams_sorted": data.TEAMS_SORTED_BY_NAME,
    }


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def league_dashboard():
    """League-wide dashboard: hero metrics, charts, storytelling."""
    return render_template(
        "league.html",
        league=analytics.LEAGUE,
        stories=storytelling.league_insights(),
        active="league",
    )


@app.route("/conference/<conf>")
def conference_dashboard(conf: str):
    """Conference rollup (AFC or NFC)."""
    conf = conf.upper()
    if conf not in ("AFC", "NFC"):
        abort(404)
    summary = analytics.conference_summary(conf)
    return render_template(
        "group.html",
        summary=summary,
        stories=storytelling.group_insights(summary),
        scope="conference",
        scope_value=conf,
        active=f"conf:{conf}",
    )


@app.route("/division/<conf>/<division>")
def division_dashboard(conf: str, division: str):
    """Division rollup (e.g. /division/AFC/East)."""
    conf = conf.upper()
    division = division.title()
    if conf not in ("AFC", "NFC") or division not in DIVISION_ORDER:
        abort(404)
    summary = analytics.division_summary(conf, division)
    return render_template(
        "group.html",
        summary=summary,
        stories=storytelling.group_insights(summary),
        scope="division",
        scope_value=f"{conf} {division}",
        active=f"div:{conf}:{division}",
    )


@app.route("/team/<abbr>")
def team_dashboard(abbr: str):
    """Team battle card: draft history, season history, impact analysis."""
    abbr = abbr.upper()
    if abbr not in data.TEAMS_BY_ABB:
        abort(404)
    summary = analytics.team_summary(abbr)
    return render_template(
        "team.html",
        summary=summary,
        stories=storytelling.team_insights(summary),
        active=f"team:{abbr}",
    )


# ---------------------------------------------------------------------------
# JSON API (lightweight; future features / external consumers)
# ---------------------------------------------------------------------------

@app.route("/api/teams")
def api_teams():
    conf = request.args.get("conference", "").upper()
    div = request.args.get("division", "").title()
    teams = data.ALL_TEAMS
    if conf:
        teams = [t for t in teams if t["conference"] == conf]
    if div:
        teams = [t for t in teams if t["division"] == div]
    return jsonify(teams)


@app.route("/api/team/<abbr>")
def api_team(abbr: str):
    abbr = abbr.upper()
    if abbr not in data.TEAMS_BY_ABB:
        abort(404)
    return jsonify(analytics.team_summary(abbr))


@app.route("/api/league")
def api_league():
    return jsonify(analytics.LEAGUE)


@app.route("/api/meta")
def api_meta():
    return jsonify({
        "draft_years": data.METADATA["draft_years_included"],
        "record_counts": data.METADATA["record_counts"],
        "fact_check_status": data.METADATA["fact_check"]["status"],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
