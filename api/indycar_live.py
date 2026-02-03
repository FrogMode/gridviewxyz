"""IndyCar Live Timing API - Real-time data from Azure Blob Storage.

DISCOVERED ENDPOINTS:
- tsconfig.json - Session status and configuration
- schedulefeed.json - Full season schedule with broadcasts
- driversfeed.json - Driver info, stats, and car liveries
- timingscoring-ris.json - Live timing and scoring (during sessions)
- trackactivityleaderboardfeed.json - Current leaderboard

All data is served from Azure Blob Storage with no authentication required.
"""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
from datetime import datetime
from typing import Optional, Dict, Any, List
import time

INDYCAR_BLOB_BASE = "https://indycar.blob.core.windows.net/racecontrol"
NTT_DATA_BASE = "https://indycar.blob.core.windows.net/ntt-data/INDYCAR_DATA_POLLING"

# Simple cache
_cache: Dict[str, tuple] = {}
_cache_ttl = {
    "tsconfig.json": 30,          # 30s - session status
    "schedulefeed.json": 3600,    # 1h - schedule rarely changes
    "driversfeed.json": 3600,     # 1h - driver data
    "timingscoring-ris.json": 3,  # 3s - live timing
    "trackactivityleaderboardfeed.json": 3,  # 3s - live leaderboard
}


def _fetch_json(endpoint: str, base: str = INDYCAR_BLOB_BASE, cache_ttl: int = None) -> Dict[str, Any]:
    """Fetch JSON from IndyCar blob storage with caching."""
    cache_key = f"{base}/{endpoint}"
    now = time.time()
    
    if cache_key in _cache:
        data, timestamp = _cache[cache_key]
        ttl = cache_ttl or _cache_ttl.get(endpoint, 300)
        if now - timestamp < ttl:
            return data
    
    # Add cache-busting parameter
    url = f"{base}/{endpoint}?t={int(now)}"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read()
        # Handle JSONP callback wrapper if present
        text = content.decode('utf-8', errors='ignore')
        if text.startswith('driverCallback(') or text.startswith('driverFILCallback('):
            # Strip JSONP wrapper
            text = text.split('(', 1)[1].rsplit(')', 1)[0]
        data = json.loads(text)
    
    _cache[cache_key] = (data, now)
    return data


def get_session_status() -> Dict[str, Any]:
    """Get current session status and configuration."""
    config = _fetch_json("tsconfig.json")
    return {
        "session_active": not config.get("no_track_activity", True),
        "timed_race": config.get("timed_race", False),
        "rain_delay": config.get("rain_delay", False),
        "show_track_map": config.get("show_static_track_map", False),
        "track_map_url": config.get("track_map_url"),
        "ways_to_watch": config.get("ways_to_watch", [])
    }


def get_schedule() -> List[Dict[str, Any]]:
    """Get full IndyCar schedule from live feed."""
    try:
        data = _fetch_json("schedulefeed.json")
        races = data.get("schedule", {}).get("race", [])
        
        results = []
        for race in races:
            # Safely get nested TV channel
            tv_data = race.get("tv") or {}
            listing = tv_data.get("listing") or {}
            tv_channel = listing.get("channel")
            
            # Safely get past winners
            past_winners_data = race.get("past_winners") or {}
            past_winners = past_winners_data.get("past_winner") or []
            
            results.append({
                "event_id": race.get("eventid"),
                "name": race.get("name"),
                "city": race.get("city"),
                "state": race.get("state"),
                "country": race.get("country", "USA"),
                "track_name": race.get("track_name") or race.get("name"),
                "track_length_miles": race.get("track_length"),
                "laps": race.get("laps"),
                "green_flag": race.get("green_flag"),
                "is_complete": race.get("is_complete") == "1",
                "ticket_url": race.get("ticket_url"),
                "link_url": race.get("link_url"),
                "tv": tv_channel,
                "winner": race.get("racewinner"),
                "past_winners": past_winners
            })
        
        return results
    except Exception as e:
        # Log error and fallback to empty list
        print(f"[IndyCar Live] Schedule fetch error: {e}")
        return []


def get_drivers() -> List[Dict[str, Any]]:
    """Get current driver roster with stats."""
    try:
        data = _fetch_json("driversfeed.json")
        drivers = data.get("drivers", {}).get("driver", [])
        
        results = []
        for driver in drivers:
            results.append({
                "driver_id": driver.get("driverid"),
                "name": driver.get("name"),
                "firstname": driver.get("firstname"),
                "lastname": driver.get("lastname"),
                "number": driver.get("number"),
                "team": driver.get("team"),
                "engine": driver.get("engine"),
                "rookie": driver.get("rookie") == "1",
                "hometown": driver.get("hometown"),
                "residence": driver.get("residence"),
                "birthdate": driver.get("birthdate"),
                "headshot": driver.get("headshot"),
                "car_image": driver.get("carillustration"),
                "flag": driver.get("flag"),
                "radio_frequency": driver.get("radiofrequency"),
                "stats": driver.get("stats", {}),
                "career_stats": driver.get("career_stats", {})
            })
        
        return results
    except Exception:
        return []


def get_live_timing() -> Optional[Dict[str, Any]]:
    """Get live timing and scoring during active sessions."""
    # First check if session is active
    status = get_session_status()
    if not status.get("session_active"):
        return {"status": "no_active_session", "message": "No session currently active"}
    
    try:
        data = _fetch_json("timingscoring-ris.json")
        timing = data.get("timing_results", {})
        heartbeat = timing.get("heartbeat", {})
        entries = timing.get("entries", [])
        
        results = []
        for entry in entries:
            results.append({
                "position": entry.get("Position"),
                "number": entry.get("Number"),
                "driver": entry.get("Driver"),
                "team": entry.get("Team"),
                "engine": entry.get("Engine"),
                "last_lap": entry.get("LastLap"),
                "best_lap": entry.get("BestLap"),
                "gap": entry.get("Gap"),
                "diff": entry.get("Diff"),
                "laps": entry.get("Laps"),
                "pit_stops": entry.get("PitStops"),
                "status": entry.get("Status"),
                "on_track": entry.get("OnTrack"),
            })
        
        return {
            "status": "live",
            "session_status": heartbeat.get("SessionStatus"),
            "session_name": heartbeat.get("SessionName"),
            "event_name": heartbeat.get("EventName"),
            "lap_number": heartbeat.get("LapNumber"),
            "time_remaining": heartbeat.get("TimeRemaining"),
            "flag_status": heartbeat.get("FlagStatus"),
            "results": results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_leaderboard() -> Optional[Dict[str, Any]]:
    """Get current track activity leaderboard."""
    try:
        data = _fetch_json("trackactivityleaderboardfeed.json")
        activity = data.get("trackactivity", {})
        event = activity.get("event", {})
        
        if not event:
            return {"status": "no_activity", "message": "No track activity"}
        
        entries = event.get("entries", [])
        results = []
        for entry in entries:
            results.append({
                "position": entry.get("position"),
                "number": entry.get("number"),
                "driver": entry.get("driver"),
                "team": entry.get("team"),
                "best_time": entry.get("bestTime"),
                "best_speed": entry.get("bestSpeed"),
                "laps": entry.get("laps"),
                "gap": entry.get("gap"),
            })
        
        return {
            "status": "active",
            "event_name": event.get("eventName"),
            "session_name": event.get("sessionName"),
            "track_name": event.get("trackName"),
            "session_status": event.get("sessionStatus"),
            "leaderboard": results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            # Get session status
            if 'status' in query:
                response = get_session_status()
                self._send_json(response)
                return
            
            # Get live timing (during sessions)
            if 'live' in query:
                response = get_live_timing()
                self._send_json(response)
                return
            
            # Get current leaderboard
            if 'leaderboard' in query:
                response = get_leaderboard()
                self._send_json(response)
                return
            
            # Get drivers
            if 'drivers' in query:
                drivers = get_drivers()
                self._send_json({"drivers": drivers, "count": len(drivers)})
                return
            
            # Get schedule (from live feed)
            if 'schedule' in query or 'upcoming' in query:
                schedule = get_schedule()
                
                # Filter upcoming if requested
                if 'upcoming' in query:
                    today = datetime.now().strftime("%Y-%m-%d")
                    limit = int(query.get('limit', [8])[0])
                    upcoming = []
                    for race in schedule:
                        green_flag = race.get("green_flag", "")
                        if green_flag and green_flag[:10] >= today and not race.get("is_complete"):
                            upcoming.append(race)
                            if len(upcoming) >= limit:
                                break
                    self._send_json({"upcoming": upcoming, "count": len(upcoming)})
                else:
                    self._send_json({"schedule": schedule, "count": len(schedule)})
                return
            
            # Default: return summary
            status = get_session_status()
            self._send_json({
                "series": "NTT INDYCAR Series",
                "session_active": status.get("session_active"),
                "endpoints": {
                    "status": "/api/indycar_live?status",
                    "schedule": "/api/indycar_live?schedule",
                    "upcoming": "/api/indycar_live?upcoming",
                    "drivers": "/api/indycar_live?drivers",
                    "live": "/api/indycar_live?live",
                    "leaderboard": "/api/indycar_live?leaderboard"
                },
                "data_source": "Azure Blob Storage (public)",
                "note": "Live timing endpoints active during sessions only"
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
        # Shorter cache for live data
        cache_time = 5 if 'live' in str(data) or 'leaderboard' in str(data) else 300
        self.send_header('Cache-Control', f'public, max-age={cache_time}')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
