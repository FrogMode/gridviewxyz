#!/usr/bin/env python3
"""Quick archive - one year at a time with longer delays"""
import json, os, sys, time, urllib.request

JOLPICA = "https://api.jolpi.ca/ergast/f1"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "archive", "ergast")
os.makedirs(OUT_DIR, exist_ok=True)

def fetch(url):
    time.sleep(1)  # Longer delay to avoid rate limits
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  Error: {e}")
        return None

def archive_year(year):
    print(f"\n🏎️  Archiving {year}...")
    data = {"year": year, "source": "jolpica"}
    
    # Schedule
    d = fetch(f"{JOLPICA}/{year}.json?limit=30")
    data["races"] = d["MRData"]["RaceTable"]["Races"] if d else []
    print(f"  {len(data['races'])} races")
    
    # Results for each race
    for race in data["races"]:
        rnd = race["round"]
        r = fetch(f"{JOLPICA}/{year}/{rnd}/results.json?limit=30")
        if r:
            race["Results"] = r["MRData"]["RaceTable"]["Races"][0].get("Results", []) if r["MRData"]["RaceTable"]["Races"] else []
    
    # Driver standings
    d = fetch(f"{JOLPICA}/{year}/driverStandings.json?limit=50")
    if d and d["MRData"]["StandingsTable"]["StandingsLists"]:
        data["driverStandings"] = d["MRData"]["StandingsTable"]["StandingsLists"][0]
    
    # Constructor standings
    d = fetch(f"{JOLPICA}/{year}/constructorStandings.json?limit=20")
    if d and d["MRData"]["StandingsTable"]["StandingsLists"]:
        data["constructorStandings"] = d["MRData"]["StandingsTable"]["StandingsLists"][0]
    
    # Save
    out = os.path.join(OUT_DIR, f"f1_{year}.json")
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    size = os.path.getsize(out) / 1024
    print(f"  ✅ Saved {out} ({size:.1f} KB)")

if __name__ == "__main__":
    years = [int(y) for y in sys.argv[1:]] if len(sys.argv) > 1 else [2024, 2025]
    for y in years:
        archive_year(y)
    print("\n🏁 Done!")
