import json
import os
from flask import Flask, render_template, request, jsonify, abort

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Data layer — loaded once at startup, never re-read per request
# ---------------------------------------------------------------------------

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "nfl_data.json")

with open(DATA_PATH, "r") as f:
    _raw = json.load(f)

METADATA = _raw["metadata"]
ALL_TEAMS = _raw["current_nfl_teams_2026_2027"]
DRAFTS = _raw["drafts"]

# Lookup structures built once
TEAMS_BY_ABB = {t["abbreviation"]: t for t in ALL_TEAMS}

TEAMS_BY_CONF = {}
for t in ALL_TEAMS:
    TEAMS_BY_CONF.setdefault(t["conference"], {})
    TEAMS_BY_CONF[t["conference"]].setdefault(t["division"], [])
    TEAMS_BY_CONF[t["conference"]][t["division"]].append(t)

# All picks flattened, indexed by current_franchise_abbreviation
PICKS_BY_TEAM = {}
for draft in DRAFTS:
    for pick in draft.get("picks", []):
        abbr = pick.get("current_franchise_abbreviation") or pick.get("source_team_abbreviation")
        PICKS_BY_TEAM.setdefault(abbr, [])
        PICKS_BY_TEAM[abbr].append({**pick, "year": draft["year"]})

DRAFT_YEARS = sorted(d["year"] for d in DRAFTS)

# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

DIVISION_ORDER = ["East", "North", "South", "West"]


@app.route("/")
def index():
    conf = request.args.get("conference", "ALL").upper()
    if conf == "AFC":
        confs = ["AFC"]
    elif conf == "NFC":
        confs = ["NFC"]
    else:
        conf = "ALL"
        confs = ["AFC", "NFC"]

    grouped = {}
    for c in confs:
        grouped[c] = {}
        for div in DIVISION_ORDER:
            if div in TEAMS_BY_CONF.get(c, {}):
                grouped[c][div] = sorted(
                    TEAMS_BY_CONF[c][div], key=lambda t: t["team_name"]
                )

    total = sum(
        len(teams)
        for divs in grouped.values()
        for teams in divs.values()
    )

    return render_template(
        "index.html",
        grouped=grouped,
        active=conf,
        total=total,
        conf_keys=confs,
        division_order=DIVISION_ORDER,
    )


# ---------------------------------------------------------------------------
# API routes  (JSON only — consumed by future features / JS)
# ---------------------------------------------------------------------------

@app.route("/api/teams")
def api_teams():
    conf = request.args.get("conference", "").upper()
    div = request.args.get("division", "").title()
    teams = ALL_TEAMS
    if conf:
        teams = [t for t in teams if t["conference"] == conf]
    if div:
        teams = [t for t in teams if t["division"] == div]
    return jsonify(teams)


@app.route("/api/teams/<abbr>")
def api_team_detail(abbr):
    abbr = abbr.upper()
    team = TEAMS_BY_ABB.get(abbr)
    if not team:
        abort(404)
    picks = PICKS_BY_TEAM.get(abbr, [])
    return jsonify({
        "team": team,
        "first_round_picks_count": len(picks),
        "hall_of_fame_count": sum(1 for p in picks if p.get("hall_of_fame")),
    })


@app.route("/api/drafts")
def api_drafts():
    """
    Query params:
      team=<abbr>          filter by current franchise abbreviation
      year=<YYYY>          filter by draft year
      position=<POS>       filter by position
      hof=true             only Hall of Fame picks
      page=<n>             1-based page (default 1)
      per_page=<n>         results per page (default 25, max 100)
    """
    team = request.args.get("team", "").upper() or None
    year = request.args.get("year", type=int)
    pos = request.args.get("position", "").upper() or None
    hof_only = request.args.get("hof", "").lower() == "true"
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, max(1, request.args.get("per_page", 25, type=int)))

    results = []
    for draft in DRAFTS:
        if year and draft["year"] != year:
            continue
        for pick in draft.get("picks", []):
            abbr = pick.get("current_franchise_abbreviation") or pick.get("source_team_abbreviation")
            if team and abbr != team:
                continue
            if pos and pick.get("position") != pos:
                continue
            if hof_only and not pick.get("hall_of_fame"):
                continue
            results.append({**pick, "year": draft["year"]})

    total = len(results)
    start = (page - 1) * per_page
    page_results = results[start: start + per_page]

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": -(-total // per_page),
        "picks": page_results,
    })


@app.route("/api/drafts/years")
def api_draft_years():
    return jsonify(DRAFT_YEARS)


@app.route("/api/meta")
def api_meta():
    return jsonify({
        "draft_years": METADATA["draft_years_included"],
        "record_counts": METADATA["record_counts"],
        "fact_check_status": METADATA["fact_check"]["status"],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
