#!/usr/bin/env python3
"""
URGENT: Archive Ergast F1 API before it shuts down!

Ergast API (ergast.com) is the definitive source for F1 historical data
back to 1950. It's shutting down in 2024, so we need to archive everything.

Usage:
    python ergast_archive.py                    # Archive all years (1950-2024)
    python ergast_archive.py --year 2023        # Archive single year
    python ergast_archive.py --from 2020 --to 2024  # Archive range

Output:
    Creates JSON files in ./archive/ergast/ directory
"""

import argparse
import json
import os
import time
from datetime import datetime
from typing import Optional
import urllib.request
import urllib.error

# Original Ergast is dead - using Jolpica community mirror
ERGAST_BASE = "https://api.jolpi.ca/ergast/f1"
ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "archive", "ergast")
RATE_LIMIT_DELAY = 0.25  # 250ms between requests to be polite


def fetch_json(url: str, retries: int = 3) -> Optional[dict]:
    """Fetch JSON with retries and rate limiting."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "GridView/1.0 (archiving before shutdown)"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            time.sleep(RATE_LIMIT_DELAY)
            return data
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} for {url}, attempt {attempt + 1}/{retries}")
            if e.code == 429:  # Rate limited
                time.sleep(5)
            elif e.code == 404:
                return None
        except Exception as e:
            print(f"  Error: {e}, attempt {attempt + 1}/{retries}")
            time.sleep(1)
    return None


def archive_season(year: int) -> dict:
    """Archive all F1 data for a season."""
    print(f"\n{'='*50}")
    print(f"Archiving F1 {year}")
    print(f"{'='*50}")
    
    data = {
        "year": year,
        "archived_at": datetime.now().isoformat(),
        "source": "ergast.com"
    }
    
    # 1. Season schedule
    print(f"  Fetching schedule...")
    schedule = fetch_json(f"{ERGAST_BASE}/{year}.json?limit=30")
    if schedule:
        data["schedule"] = schedule.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        print(f"    Found {len(data['schedule'])} races")
    
    # 2. Drivers
    print(f"  Fetching drivers...")
    drivers = fetch_json(f"{ERGAST_BASE}/{year}/drivers.json?limit=100")
    if drivers:
        data["drivers"] = drivers.get("MRData", {}).get("DriverTable", {}).get("Drivers", [])
        print(f"    Found {len(data['drivers'])} drivers")
    
    # 3. Constructors
    print(f"  Fetching constructors...")
    constructors = fetch_json(f"{ERGAST_BASE}/{year}/constructors.json?limit=50")
    if constructors:
        data["constructors"] = constructors.get("MRData", {}).get("ConstructorTable", {}).get("Constructors", [])
        print(f"    Found {len(data['constructors'])} constructors")
    
    # 4. Driver standings (final)
    print(f"  Fetching driver standings...")
    driver_standings = fetch_json(f"{ERGAST_BASE}/{year}/driverStandings.json?limit=50")
    if driver_standings:
        standings_list = driver_standings.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
        data["driver_standings"] = standings_list[0] if standings_list else {}
    
    # 5. Constructor standings (final)
    print(f"  Fetching constructor standings...")
    constructor_standings = fetch_json(f"{ERGAST_BASE}/{year}/constructorStandings.json?limit=20")
    if constructor_standings:
        standings_list = constructor_standings.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
        data["constructor_standings"] = standings_list[0] if standings_list else {}
    
    # 6. Results for each race
    data["race_results"] = []
    data["qualifying"] = []
    data["sprint_results"] = []
    data["lap_times"] = []
    data["pit_stops"] = []
    
    races = data.get("schedule", [])
    for i, race in enumerate(races):
        round_num = race.get("round", i + 1)
        race_name = race.get("raceName", f"Round {round_num}")
        print(f"  Round {round_num}: {race_name}")
        
        # Race results
        results = fetch_json(f"{ERGAST_BASE}/{year}/{round_num}/results.json?limit=30")
        if results:
            race_data = results.get("MRData", {}).get("RaceTable", {}).get("Races", [])
            if race_data:
                data["race_results"].append(race_data[0])
        
        # Qualifying
        quali = fetch_json(f"{ERGAST_BASE}/{year}/{round_num}/qualifying.json?limit=30")
        if quali:
            quali_data = quali.get("MRData", {}).get("RaceTable", {}).get("Races", [])
            if quali_data:
                data["qualifying"].append(quali_data[0])
        
        # Sprint results (2021+)
        if year >= 2021:
            sprint = fetch_json(f"{ERGAST_BASE}/{year}/{round_num}/sprint.json?limit=30")
            if sprint:
                sprint_data = sprint.get("MRData", {}).get("RaceTable", {}).get("Races", [])
                if sprint_data:
                    data["sprint_results"].append(sprint_data[0])
        
        # Lap times (can be large, but valuable)
        laps = fetch_json(f"{ERGAST_BASE}/{year}/{round_num}/laps.json?limit=2000")
        if laps:
            lap_data = laps.get("MRData", {}).get("RaceTable", {}).get("Races", [])
            if lap_data:
                data["lap_times"].append({
                    "round": round_num,
                    "raceName": race_name,
                    "Laps": lap_data[0].get("Laps", [])
                })
        
        # Pit stops (2012+)
        if year >= 2012:
            pits = fetch_json(f"{ERGAST_BASE}/{year}/{round_num}/pitstops.json?limit=100")
            if pits:
                pit_data = pits.get("MRData", {}).get("RaceTable", {}).get("Races", [])
                if pit_data:
                    data["pit_stops"].append({
                        "round": round_num,
                        "raceName": race_name,
                        "PitStops": pit_data[0].get("PitStops", [])
                    })
    
    # 7. Standings progression (all rounds)
    print(f"  Fetching standings progression...")
    data["standings_progression"] = {"drivers": [], "constructors": []}
    for round_num in range(1, len(races) + 1):
        # Driver standings after each round
        ds = fetch_json(f"{ERGAST_BASE}/{year}/{round_num}/driverStandings.json?limit=50")
        if ds:
            sl = ds.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
            if sl:
                data["standings_progression"]["drivers"].append({
                    "round": round_num,
                    "standings": sl[0].get("DriverStandings", [])
                })
        
        # Constructor standings after each round
        cs = fetch_json(f"{ERGAST_BASE}/{year}/{round_num}/constructorStandings.json?limit=20")
        if cs:
            sl = cs.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
            if sl:
                data["standings_progression"]["constructors"].append({
                    "round": round_num,
                    "standings": sl[0].get("ConstructorStandings", [])
                })
    
    return data


def save_archive(data: dict, year: int):
    """Save archived data to JSON file."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    filepath = os.path.join(ARCHIVE_DIR, f"f1_{year}.json")
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"\n  ✓ Saved to {filepath} ({size_mb:.2f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Archive Ergast F1 API data")
    parser.add_argument("--year", type=int, help="Archive single year")
    parser.add_argument("--from", dest="from_year", type=int, default=1950, help="Start year")
    parser.add_argument("--to", dest="to_year", type=int, default=2024, help="End year")
    parser.add_argument("--skip-existing", action="store_true", help="Skip years already archived")
    args = parser.parse_args()
    
    print("="*60)
    print("🏎️  Ergast F1 API Archive Tool")
    print("="*60)
    print(f"Archive directory: {ARCHIVE_DIR}")
    print(f"⚠️  Ergast API is shutting down - archive NOW!")
    print()
    
    if args.year:
        years = [args.year]
    else:
        years = list(range(args.from_year, args.to_year + 1))
    
    print(f"Years to archive: {years[0]} - {years[-1]} ({len(years)} seasons)")
    
    for year in years:
        # Skip if exists
        if args.skip_existing:
            filepath = os.path.join(ARCHIVE_DIR, f"f1_{year}.json")
            if os.path.exists(filepath):
                print(f"\n⏭️  Skipping {year} (already archived)")
                continue
        
        try:
            data = archive_season(year)
            save_archive(data, year)
        except Exception as e:
            print(f"\n❌ Error archiving {year}: {e}")
            continue
    
    print("\n" + "="*60)
    print("✅ Archive complete!")
    print(f"Files saved to: {ARCHIVE_DIR}")
    print("="*60)


if __name__ == "__main__":
    main()
