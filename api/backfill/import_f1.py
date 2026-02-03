#!/usr/bin/env python3
"""
Import F1 data from Ergast archive into Supabase.

Usage:
    python import_f1.py                              # Import all archived years
    python import_f1.py --year 2024                  # Import single year
    python import_f1.py --file archive/ergast/f1_2024.json  # Import from file
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

# Add parent dirs to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.supabase import get_admin_client

ARCHIVE_DIR = Path(__file__).parent.parent.parent / "archive" / "ergast"


def load_archive(year: int) -> Optional[dict]:
    """Load archived Ergast data for a year."""
    filepath = ARCHIVE_DIR / f"f1_{year}.json"
    if not filepath.exists():
        print(f"  ⚠️  Archive not found: {filepath}")
        return None
    
    with open(filepath) as f:
        return json.load(f)


def get_or_create_series(client) -> str:
    """Ensure F1 series exists and return its ID."""
    result = client.table("series").select("id").eq("code", "f1").execute()
    if result.data:
        return result.data[0]["id"]
    
    # Create it
    result = client.table("series").insert({
        "code": "f1",
        "name": "Formula 1",
        "short_name": "F1",
        "color": "#E10600",
        "priority": 1
    }).execute()
    return result.data[0]["id"]


def import_tracks(client, races: List[dict]) -> Dict[str, str]:
    """Import tracks and return mapping of circuit_id -> uuid."""
    track_map = {}
    
    for race in races:
        circuit = race.get("Circuit", {})
        circuit_id = circuit.get("circuitId")
        if not circuit_id or circuit_id in track_map:
            continue
        
        # Check if exists
        result = client.table("tracks").select("id").eq(
            "external_ids->>ergast", circuit_id
        ).execute()
        
        if result.data:
            track_map[circuit_id] = result.data[0]["id"]
            continue
        
        # Create track
        location = circuit.get("Location", {})
        result = client.table("tracks").insert({
            "name": circuit.get("circuitName"),
            "country": location.get("country"),
            "city": location.get("locality"),
            "latitude": float(location.get("lat", 0)) if location.get("lat") else None,
            "longitude": float(location.get("long", 0)) if location.get("long") else None,
            "external_ids": {"ergast": circuit_id},
            "track_type": "road"  # F1 tracks are road courses
        }).execute()
        
        track_map[circuit_id] = result.data[0]["id"]
        print(f"    Created track: {circuit.get('circuitName')}")
    
    return track_map


def import_drivers(client, drivers: List[dict]) -> Dict[str, str]:
    """Import drivers and return mapping of driver_id -> uuid."""
    driver_map = {}
    
    for driver in drivers:
        driver_id = driver.get("driverId")
        if not driver_id:
            continue
        
        # Check if exists
        result = client.table("drivers").select("id").eq(
            "external_ids->>ergast", driver_id
        ).execute()
        
        if result.data:
            driver_map[driver_id] = result.data[0]["id"]
            continue
        
        # Parse date of birth
        dob = driver.get("dateOfBirth")
        
        # Create driver
        result = client.table("drivers").insert({
            "first_name": driver.get("givenName"),
            "last_name": driver.get("familyName"),
            "code": driver.get("code"),
            "permanent_number": int(driver.get("permanentNumber")) if driver.get("permanentNumber") else None,
            "nationality": driver.get("nationality"),
            "date_of_birth": dob,
            "wikipedia_url": driver.get("url"),
            "external_ids": {"ergast": driver_id}
        }).execute()
        
        driver_map[driver_id] = result.data[0]["id"]
    
    print(f"    Imported {len(driver_map)} drivers")
    return driver_map


def import_constructors(client, constructors: List[dict]) -> Dict[str, str]:
    """Import constructors/teams and return mapping."""
    team_map = {}
    
    for constructor in constructors:
        constructor_id = constructor.get("constructorId")
        if not constructor_id:
            continue
        
        # Check if exists
        result = client.table("teams").select("id").eq(
            "external_ids->>ergast", constructor_id
        ).execute()
        
        if result.data:
            team_map[constructor_id] = result.data[0]["id"]
            continue
        
        # Create team
        result = client.table("teams").insert({
            "name": constructor.get("name"),
            "nationality": constructor.get("nationality"),
            "external_ids": {"ergast": constructor_id}
        }).execute()
        
        team_map[constructor_id] = result.data[0]["id"]
    
    print(f"    Imported {len(team_map)} constructors")
    return team_map


def import_races_and_results(
    client,
    series_id: str,
    year: int,
    race_results: List[dict],
    qualifying: List[dict],
    track_map: Dict[str, str],
    driver_map: Dict[str, str],
    team_map: Dict[str, str]
):
    """Import races, sessions, and results."""
    
    # Build lookup for qualifying by round
    quali_by_round = {
        int(q.get("round", 0)): q.get("QualifyingResults", [])
        for q in qualifying
    }
    
    for race_data in race_results:
        round_num = int(race_data.get("round", 0))
        race_name = race_data.get("raceName", f"Round {round_num}")
        circuit_id = race_data.get("Circuit", {}).get("circuitId")
        
        print(f"    Round {round_num}: {race_name}")
        
        # Check if race exists
        result = client.table("races").select("id").eq(
            "series_id", series_id
        ).eq("season", year).eq("round", round_num).execute()
        
        if result.data:
            race_id = result.data[0]["id"]
        else:
            # Create race
            result = client.table("races").insert({
                "series_id": series_id,
                "track_id": track_map.get(circuit_id),
                "season": year,
                "round": round_num,
                "name": race_name,
                "date": race_data.get("date"),
                "status": "completed",
                "external_ids": {"ergast": f"{year}/{round_num}"}
            }).execute()
            race_id = result.data[0]["id"]
        
        # Create qualifying session
        quali_results = quali_by_round.get(round_num, [])
        if quali_results:
            result = client.table("sessions").select("id").eq(
                "race_id", race_id
            ).eq("type", "qualifying").execute()
            
            if result.data:
                quali_session_id = result.data[0]["id"]
            else:
                result = client.table("sessions").insert({
                    "race_id": race_id,
                    "type": "qualifying",
                    "name": "Qualifying",
                    "status": "completed"
                }).execute()
                quali_session_id = result.data[0]["id"]
            
            # Import qualifying results
            for qr in quali_results:
                driver_ergast_id = qr.get("Driver", {}).get("driverId")
                constructor_ergast_id = qr.get("Constructor", {}).get("constructorId")
                
                if driver_ergast_id and driver_ergast_id in driver_map:
                    # Parse qualifying times
                    q1 = qr.get("Q1")
                    q2 = qr.get("Q2")
                    q3 = qr.get("Q3")
                    
                    client.table("results").upsert({
                        "session_id": quali_session_id,
                        "driver_id": driver_map[driver_ergast_id],
                        "team_id": team_map.get(constructor_ergast_id),
                        "position": int(qr.get("position", 0)),
                        "car_number": qr.get("number"),
                        "extra_data": {
                            "Q1": q1,
                            "Q2": q2,
                            "Q3": q3
                        }
                    }, on_conflict="session_id,driver_id").execute()
        
        # Create race session
        result = client.table("sessions").select("id").eq(
            "race_id", race_id
        ).eq("type", "race").execute()
        
        if result.data:
            race_session_id = result.data[0]["id"]
        else:
            result = client.table("sessions").insert({
                "race_id": race_id,
                "type": "race",
                "name": "Race",
                "status": "completed"
            }).execute()
            race_session_id = result.data[0]["id"]
        
        # Import race results
        for rr in race_data.get("Results", []):
            driver_ergast_id = rr.get("Driver", {}).get("driverId")
            constructor_ergast_id = rr.get("Constructor", {}).get("constructorId")
            
            if not driver_ergast_id or driver_ergast_id not in driver_map:
                continue
            
            # Parse time
            time_data = rr.get("Time", {})
            time_ms = None
            if time_data.get("millis"):
                time_ms = int(time_data["millis"])
            
            # Parse status
            status_text = rr.get("status", "")
            if status_text == "Finished" or status_text.startswith("+"):
                status = "finished"
            elif "Disqualified" in status_text:
                status = "dsq"
            else:
                status = "dnf"
            
            # Fastest lap
            fastest_lap = rr.get("FastestLap", {})
            fl_rank = int(fastest_lap.get("rank", 0)) if fastest_lap.get("rank") else None
            fl_lap = int(fastest_lap.get("lap", 0)) if fastest_lap.get("lap") else None
            fl_time = fastest_lap.get("Time", {}).get("time")
            
            # Convert fastest lap time to ms
            fl_time_ms = None
            if fl_time:
                try:
                    parts = fl_time.split(":")
                    if len(parts) == 2:
                        mins, secs = parts
                        fl_time_ms = int(int(mins) * 60000 + float(secs) * 1000)
                except:
                    pass
            
            client.table("results").upsert({
                "session_id": race_session_id,
                "driver_id": driver_map[driver_ergast_id],
                "team_id": team_map.get(constructor_ergast_id),
                "position": int(rr.get("position", 0)),
                "position_text": rr.get("positionText"),
                "grid_position": int(rr.get("grid", 0)) if rr.get("grid") else None,
                "points": float(rr.get("points", 0)),
                "laps_completed": int(rr.get("laps", 0)),
                "time_ms": time_ms,
                "time_text": time_data.get("time"),
                "status": status,
                "status_detail": status_text if status != "finished" else None,
                "car_number": rr.get("number"),
                "fastest_lap_rank": fl_rank,
                "fastest_lap_time_ms": fl_time_ms,
                "fastest_lap_number": fl_lap
            }, on_conflict="session_id,driver_id").execute()


def import_standings(
    client,
    series_id: str,
    year: int,
    standings_progression: dict,
    driver_map: Dict[str, str],
    team_map: Dict[str, str]
):
    """Import standings snapshots for championship progression."""
    
    driver_progression = standings_progression.get("drivers", [])
    constructor_progression = standings_progression.get("constructors", [])
    
    for round_data in driver_progression:
        round_num = round_data.get("round")
        standings = round_data.get("standings", [])
        
        for standing in standings:
            driver_ergast_id = standing.get("Driver", {}).get("driverId")
            if not driver_ergast_id or driver_ergast_id not in driver_map:
                continue
            
            client.table("standings_snapshots").upsert({
                "series_id": series_id,
                "season": year,
                "after_round": round_num,
                "type": "driver",
                "driver_id": driver_map[driver_ergast_id],
                "position": int(standing.get("position", 0)),
                "points": float(standing.get("points", 0)),
                "wins": int(standing.get("wins", 0)),
                "snapshot_date": f"{year}-12-31"  # Approximate
            }, on_conflict="series_id,season,after_round,type,driver_id,team_id").execute()
    
    for round_data in constructor_progression:
        round_num = round_data.get("round")
        standings = round_data.get("standings", [])
        
        for standing in standings:
            constructor_ergast_id = standing.get("Constructor", {}).get("constructorId")
            if not constructor_ergast_id or constructor_ergast_id not in team_map:
                continue
            
            client.table("standings_snapshots").upsert({
                "series_id": series_id,
                "season": year,
                "after_round": round_num,
                "type": "constructor",
                "team_id": team_map[constructor_ergast_id],
                "position": int(standing.get("position", 0)),
                "points": float(standing.get("points", 0)),
                "wins": int(standing.get("wins", 0)),
                "snapshot_date": f"{year}-12-31"
            }, on_conflict="series_id,season,after_round,type,driver_id,team_id").execute()
    
    print(f"    Imported standings for {len(driver_progression)} rounds")


def import_year(year: int, archive_data: Optional[dict] = None):
    """Import all F1 data for a year."""
    print(f"\n{'='*50}")
    print(f"Importing F1 {year}")
    print(f"{'='*50}")
    
    if archive_data is None:
        archive_data = load_archive(year)
    
    if not archive_data:
        print(f"  ❌ No archive data for {year}")
        return False
    
    client = get_admin_client()
    
    # Get or create F1 series
    series_id = get_or_create_series(client)
    print(f"  Series ID: {series_id}")
    
    # Import tracks
    print("  Importing tracks...")
    races_for_tracks = archive_data.get("race_results", [])
    track_map = import_tracks(client, races_for_tracks)
    
    # Import drivers
    print("  Importing drivers...")
    driver_map = import_drivers(client, archive_data.get("drivers", []))
    
    # Import constructors
    print("  Importing constructors...")
    team_map = import_constructors(client, archive_data.get("constructors", []))
    
    # Import races and results
    print("  Importing races and results...")
    import_races_and_results(
        client,
        series_id,
        year,
        archive_data.get("race_results", []),
        archive_data.get("qualifying", []),
        track_map,
        driver_map,
        team_map
    )
    
    # Import standings progression
    if archive_data.get("standings_progression"):
        print("  Importing standings...")
        import_standings(
            client,
            series_id,
            year,
            archive_data["standings_progression"],
            driver_map,
            team_map
        )
    
    print(f"\n  ✅ Imported F1 {year} successfully!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Import F1 data into Supabase")
    parser.add_argument("--year", type=int, help="Import single year")
    parser.add_argument("--file", type=str, help="Import from specific file")
    parser.add_argument("--from", dest="from_year", type=int, default=2020, help="Start year")
    parser.add_argument("--to", dest="to_year", type=int, default=2024, help="End year")
    args = parser.parse_args()
    
    print("="*60)
    print("🏎️  F1 Historical Data Import")
    print("="*60)
    
    if args.file:
        with open(args.file) as f:
            data = json.load(f)
        year = data.get("year", 0)
        import_year(year, data)
    elif args.year:
        import_year(args.year)
    else:
        years = range(args.from_year, args.to_year + 1)
        for year in years:
            import_year(year)
    
    print("\n" + "="*60)
    print("✅ Import complete!")
    print("="*60)


if __name__ == "__main__":
    main()
