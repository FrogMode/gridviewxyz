"""NASCAR API - fetches schedule and results from NASCAR's public JSON feeds.

Data Sources:
- cf.nascar.com/cacher/{year}/race_list_basic.json - Full schedule
- cf.nascar.com/live/feeds/series_{series_id}/{race_id}/live_feed.json - Race results
- Series IDs: 1=Cup, 2=Xfinity, 3=Truck
"""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
from datetime import datetime
from typing import Optional

NASCAR_BASE = "https://cf.nascar.com"
SERIES_MAP = {
    "cup": 1,
    "xfinity": 2,
    "truck": 3,
    "1": 1,
    "2": 2,
    "3": 3
}
SERIES_NAMES = {
    1: "NASCAR Cup Series",
    2: "NASCAR Xfinity Series",
    3: "NASCAR Craftsman Truck Series"
}

# Simple in-memory cache
_cache = {}
_cache_ttl = 300  # 5 minutes


def _cached_fetch(url: str, timeout: int = 15) -> dict:
    """Fetch with simple caching."""
    now = datetime.now().timestamp()
    if url in _cache:
        data, timestamp = _cache[url]
        if now - timestamp < _cache_ttl:
            return data
    
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    
    _cache[url] = (data, now)
    return data


def fetch_schedule(year: int = None, series_id: int = None) -> list:
    """Fetch NASCAR schedule for a year and optional series."""
    if year is None:
        year = datetime.now().year
    
    if series_id:
        url = f"{NASCAR_BASE}/cacher/{year}/{series_id}/race_list_basic.json"
    else:
        url = f"{NASCAR_BASE}/cacher/{year}/race_list_basic.json"
    
    try:
        data = _cached_fetch(url)
    except Exception:
        return []
    
    # Handle both formats (full schedule has series_* keys, series-specific is a list)
    races = []
    if isinstance(data, list):
        races = data
    elif isinstance(data, dict):
        for key in ["series_1", "series_2", "series_3"]:
            if key in data:
                races.extend(data[key])
    
    results = []
    for race in races:
        results.append({
            "race_id": race.get("race_id"),
            "series_id": race.get("series_id"),
            "series": SERIES_NAMES.get(race.get("series_id"), "NASCAR"),
            "name": race.get("race_name"),
            "track": race.get("track_name"),
            "date": race.get("date_scheduled"),
            "scheduled_laps": race.get("scheduled_laps"),
            "actual_laps": race.get("actual_laps"),
            "distance": race.get("scheduled_distance"),
            "tv": race.get("television_broadcaster"),
            "radio": race.get("radio_broadcaster"),
            "winner_id": race.get("winner_driver_id"),
            "stage_1_laps": race.get("stage_1_laps"),
            "stage_2_laps": race.get("stage_2_laps"),
            "stage_3_laps": race.get("stage_3_laps"),
        })
    
    return sorted(results, key=lambda x: x.get("date") or "")


def fetch_race_results(series_id: int, race_id: int) -> Optional[dict]:
    """Fetch detailed race results (live or finished)."""
    url = f"{NASCAR_BASE}/live/feeds/series_{series_id}/{race_id}/live_feed.json"
    
    try:
        data = _cached_fetch(url)
    except Exception:
        return None
    
    if not data:
        return None
    
    vehicles = data.get("vehicles", [])
    results = []
    
    for v in vehicles:
        driver = v.get("driver", {})
        results.append({
            "position": v.get("running_position"),
            "number": v.get("vehicle_number"),
            "driver": driver.get("full_name"),
            "driver_id": driver.get("driver_id"),
            "manufacturer": v.get("vehicle_manufacturer"),
            "sponsor": v.get("sponsor_name"),
            "laps_completed": v.get("laps_completed"),
            "laps_led": sum((ll.get("end_lap", 0) - ll.get("start_lap", 0)) for ll in v.get("laps_led", [])),
            "status": "Running" if v.get("status") == 1 else "Out",
            "delta": v.get("delta"),
            "avg_speed": v.get("average_speed"),
            "best_lap_speed": v.get("best_lap_speed"),
            "starting_position": v.get("starting_position"),
        })
    
    # Sort by position
    results.sort(key=lambda x: x.get("position") or 999)
    
    return {
        "race_id": race_id,
        "series_id": series_id,
        "series": SERIES_NAMES.get(series_id, "NASCAR"),
        "lap_number": data.get("lap_number"),
        "laps_in_race": data.get("laps_in_race"),
        "laps_to_go": data.get("laps_to_go"),
        "flag_state": data.get("flag_state"),  # 1=green, 2=yellow, 9=checkered
        "elapsed_time": data.get("elapsed_time"),
        "results": results[:40]  # Top 40
    }


def get_upcoming_races(series_id: int = None, limit: int = 5) -> list:
    """Get upcoming races (not yet completed)."""
    schedule = fetch_schedule(series_id=series_id)
    now = datetime.now().isoformat()
    
    upcoming = []
    for race in schedule:
        date = race.get("date")
        if date and date >= now[:10]:  # Compare date portion
            if race.get("winner_id") == 0 or race.get("winner_id") is None:
                upcoming.append(race)
                if len(upcoming) >= limit:
                    break
    
    return upcoming


def get_recent_results(series_id: int = None, limit: int = 3) -> list:
    """Get recently completed races with results."""
    schedule = fetch_schedule(series_id=series_id)
    
    completed = []
    for race in reversed(schedule):
        if race.get("winner_id") and race.get("winner_id") > 0:
            # Fetch actual results
            result = fetch_race_results(race["series_id"], race["race_id"])
            if result:
                completed.append({
                    "race": race,
                    "results": result.get("results", [])[:10]  # Top 10
                })
                if len(completed) >= limit:
                    break
    
    return completed


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            # Parse series parameter
            series_param = query.get('series', [None])[0]
            series_id = SERIES_MAP.get(series_param.lower() if series_param else None)
            
            # Parse year
            year_param = query.get('year', [None])[0]
            year = int(year_param) if year_param else None
            
            # Get specific race results
            race_id = query.get('race', [None])[0]
            if race_id and series_param:
                series_id = SERIES_MAP.get(series_param.lower(), 1)
                result = fetch_race_results(series_id, int(race_id))
                if result:
                    self._send_json(result)
                else:
                    self._send_json({"error": "Race not found"}, 404)
                return
            
            # Get upcoming races
            if 'upcoming' in query:
                limit = int(query.get('limit', [5])[0])
                races = get_upcoming_races(series_id=series_id, limit=limit)
                self._send_json({
                    "series": SERIES_NAMES.get(series_id, "All Series") if series_id else "All Series",
                    "upcoming": races
                })
                return
            
            # Get recent results
            if 'results' in query:
                limit = int(query.get('limit', [3])[0])
                results = get_recent_results(series_id=series_id, limit=limit)
                self._send_json({
                    "series": SERIES_NAMES.get(series_id, "All Series") if series_id else "All Series",
                    "recent": results
                })
                return
            
            # Default: return schedule
            schedule = fetch_schedule(year=year, series_id=series_id)
            self._send_json({
                "series": SERIES_NAMES.get(series_id, "All Series") if series_id else "All Series",
                "season": year or datetime.now().year,
                "events": schedule
            })
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=300')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
