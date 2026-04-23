import requests

api_key = "72afa426ab5fb0a7c964261b8b25f977"
headers = {'x-apisports-key': api_key}

print("--- LOGICBET DEEP DIAGNOSTIC ---")
try:
    # 1. Get ALL fixtures for today to see what's actually there
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"date": "2026-04-09"}
    resp = requests.get(url, headers=headers, params=params).json()
    
    fixtures = resp.get('response', [])
    print(f"Total fixtures today: {len(fixtures)}")
    
    leagues_seen = {}
    for f in fixtures:
        l = f['league']
        # Filter for anything that sounds like a major league
        name = l['name'].lower()
        if "league" in name or "premier" in name:
             leagues_seen[l['id']] = f"{l['name']} ({l['country']})"
             
    print("\nMajor Leagues found today in your API:")
    for l_id, name in leagues_seen.items():
        print(f" - ID: {l_id} | Name: {name}")

except Exception as e:
    print(f"Diagnostic failed: {e}")
