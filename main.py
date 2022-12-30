nfc_teams = ['Arizona Cardinals', 'Atlanta Falcons', 'Carolina Panthers', 'Chicago Bears', 'Dallas Cowboys', 'Detroit Lions', 'Green Bay Packers', 'Los Angeles Rams', 'Minnesota Vikings', 'New Orleans Saints', 'New York Giants', 'Philadelphia Eagles', 'San Francisco 49ers', 'Seattle Seahawks', 'Tampa Bay Buccaneers', 'Washington Football Team']

afc_teams = ['Baltimore Ravens', 'Buffalo Bills', 'Cincinnati Bengals', 'Cleveland Browns', 'Denver Broncos', 'Houston Texans', 'Indianapolis Colts', 'Jacksonville Jaguars', 'Kansas City Chiefs', 'Las Vegas Raiders', 'Miami Dolphins', 'New England Patriots', 'New York Jets', 'Pittsburgh Steelers', 'Los Angeles Chargers', 'Tennessee Titans']

nfl_teams = afc_teams + nfc_teams

user_input = input("Enter AFC, NFC, or NFL to display the list of teams: ")

if user_input.lower() == "nfc":
  for team in nfc_teams:
    print(team)
elif user_input.lower() == "afc":
  for team in afc_teams:
    print(team)
elif user_input.lower() == "nfl":
  for team in nfl_teams:
    print(team)
else:
  print("Invalid input. Please enter AFC, NFC, or NFL.")