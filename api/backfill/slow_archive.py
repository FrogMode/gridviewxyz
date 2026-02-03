#!/usr/bin/env python3
"""Slow, polite archive - avoids rate limits"""
import json, os, sys, time, urllib.request

JOLPICA = "https://api.jolpi.ca/ergast/f1"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "archive", "ergast")
os.makedirs(OUT_DIR, exist_ok=True)

def fetch(url, delay=2):
    time.sleep(delay)  # Be polite
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            if "429" in str(e):
                print(f"    Rate limited, waiting 30s...")
                time.sleep(30)
            else:
                print(f"    Error: {e}, retry {attempt+1}/3")
                time.sleep(5)
    return None

def archive_year(year):
    out_file = os.path.join(OUT_DIR, f"f1_{year}.json")
    if os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
        print(f"⏭️  {year} already archived, skipping")
        return
    
    print(f"\n🏎️  Archiving {year}...")
    data = {"year": year, "source": "jolpica"}
    
    # Schedule
    d = fetch(f"{JOLPICA}/{year}.json?limit=30")
    data["races"] = d["MRData"]["RaceTable"]["Races"] if d else []
    print(f"  📅 {len(data['races'])} races")
    
    if not data["races"]:
        print(f"  ⚠️  No races found for {year}")
        return
    
    # Results for each race (slower)
    for i, race in enumerate(data["races"]):
        rnd = race["round"]
        r = fetch(f"{JOLPICA}/{year}/{rnd}/results.json?limit=30", delay=1.5)
        if r and r["MRData"]["RaceTable"]["Races"]:
            race["Results"] = r["MRData"]["RaceTable"]["Races"][0].get("Results", [])
        print(f"  🏁 Round {rnd}/{len(data['races'])}", end="\r")
    print()
    
    # Driver standings
    d = fetch(f"{JOLPICA}/{year}/driverStandings.json?limit=50")
    if d and d["MRData"]["StandingsTable"]["StandingsLists"]:
        data["driverStandings"] = d["MRData"]["StandingsTable"]["StandingsLists"][0]
        print(f"  🏆 Driver standings captured")
    
    # Constructor standings
    d = fetch(f"{JOLPICA}/{year}/constructorStandings.json?limit=20")
    if d and d["MRData"]["StandingsTable"]["StandingsLists"]:
        data["constructorStandings"] = d["MRData"]["StandingsTable"]["StandingsLists"][0]
        print(f"  🏆 Constructor standings captured")
    
    # Save
    with open(out_file, "w") as f:
        json.dump(data, f, indent=2)
    size = os.path.getsize(out_file) / 1024
    print(f"  ✅ Saved f1_{year}.json ({size:.1f} KB)")

if __name__ == "__main__":
    years = [int(y) for y in sys.argv[1:]] if len(sys.argv) > 1 else list(range(1950, 2026))
    print(f"🏁 Archiving {len(years)} seasons: {min(years)}-{max(years)}")
    for y in years:
        archive_year(y)
    print("\n🏁 Archive complete!")
