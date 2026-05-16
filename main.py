from flask import Flask, render_template, request

app = Flask(__name__)

nfc_teams = [
    'Arizona Cardinals', 'Atlanta Falcons', 'Carolina Panthers',
    'Chicago Bears', 'Dallas Cowboys', 'Detroit Lions',
    'Green Bay Packers', 'Los Angeles Rams', 'Minnesota Vikings',
    'New Orleans Saints', 'New York Giants', 'Philadelphia Eagles',
    'San Francisco 49ers', 'Seattle Seahawks', 'Tampa Bay Buccaneers',
    'Washington Commanders'
]

afc_teams = [
    'Baltimore Ravens', 'Buffalo Bills', 'Cincinnati Bengals',
    'Cleveland Browns', 'Denver Broncos', 'Houston Texans',
    'Indianapolis Colts', 'Jacksonville Jaguars', 'Kansas City Chiefs',
    'Las Vegas Raiders', 'Miami Dolphins', 'New England Patriots',
    'New York Jets', 'Pittsburgh Steelers', 'Los Angeles Chargers',
    'Tennessee Titans'
]

nfl_teams = sorted(afc_teams + nfc_teams)

@app.route('/')
def index():
    conference = request.args.get('conference', 'NFL').upper()
    if conference == 'AFC':
        teams = sorted(afc_teams)
        label = 'AFC Teams'
    elif conference == 'NFC':
        teams = sorted(nfc_teams)
        label = 'NFC Teams'
    else:
        conference = 'NFL'
        teams = nfl_teams
        label = 'All NFL Teams'
    return render_template('index.html', teams=teams, label=label, active=conference)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
