"""
F1 Live Timing API - Vercel Serverless Endpoint

Uses OpenF1 API (https://openf1.org) for real-time F1 timing data.
No auth required for public data.

Endpoints:
  GET /api/timing/f1                - Get live timing data
  GET /api/timing/f1?session=latest - Get latest session
  GET /api/timing/f1?status=1       - Check if session is active

Data includes:
  - Driver positions and intervals
  - Lap times (latest and best)
  - Session info (type, status, track)
  - Gap to leader calculations
"""

from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, List, Any


class OpenF1Client:
    """OpenF1 API client for live F1 timing data."""
    
    BASE_URL = "https://api.openf1.org/v1"
    USER_AGENT = "GridView/1.0"
    
    def __init__(self):
        self._driver_cache: Dict[int, Dict] = {}
    
    def _fetch(self, endpoint: str, params: dict = None) -> Any:
        """Fetch JSON data from OpenF1 API."""
        url = f"{self.BASE_URL}/{endpoint}"
        
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            if query:
                url += f"?{query}"
        
        req = urllib.request.Request(url, headers={
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json",
        })
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    
    def get_current_session(self) -> Optional[Dict]:
        """Get the current/latest session info."""
        try:
            data = self._fetch("sessions", {"session_key": "latest"})
            return data[0] if data else None
        except Exception:
            return None
    
    def get_session_by_key(self, session_key: int) -> Optional[Dict]:
        """Get session by key."""
        try:
            data = self._fetch("sessions", {"session_key": session_key})
            return data[0] if data else None
        except Exception:
            return None
    
    def get_drivers(self, session_key: str = "latest") -> List[Dict]:
        """Get driver info for session."""
        try:
            return self._fetch("drivers", {"session_key": session_key})
        except Exception:
            return []
    
    def get_position_data(self, session_key: str = "latest") -> List[Dict]:
        """Get latest position data for all drivers."""
        try:
            # Get positions from most recent data
            data = self._fetch("position", {"session_key": session_key})
            
            # Group by driver and get latest position
            positions = {}
            for entry in data:
                driver_num = entry.get("driver_number")
                if driver_num:
                    positions[driver_num] = entry
            
            return sorted(positions.values(), key=lambda x: x.get("position", 999))
        except Exception:
            return []
    
    def get_intervals(self, session_key: str = "latest") -> Dict[int, Dict]:
        """Get interval data for drivers."""
        try:
            data = self._fetch("intervals", {"session_key": session_key})
            
            # Group by driver, keep latest
            intervals = {}
            for entry in data:
                driver_num = entry.get("driver_number")
                if driver_num:
                    intervals[driver_num] = entry
            
            return intervals
        except Exception:
            return {}
    
    def get_laps(self, session_key: str = "latest", driver_number: int = None) -> List[Dict]:
        """Get lap data."""
        params = {"session_key": session_key}
        if driver_number:
            params["driver_number"] = driver_number
        
        try:
            return self._fetch("laps", params)
        except Exception:
            return []
    
    def get_latest_lap_times(self, session_key: str = "latest") -> Dict[int, Dict]:
        """Get latest lap times for each driver."""
        try:
            laps = self.get_laps(session_key)
            
            # Group by driver, keep latest lap
            latest = {}
            for lap in laps:
                driver_num = lap.get("driver_number")
                if driver_num:
                    if driver_num not in latest or lap.get("lap_number", 0) > latest[driver_num].get("lap_number", 0):
                        latest[driver_num] = lap
            
            return latest
        except Exception:
            return {}
    
    def is_session_live(self, session: Dict) -> bool:
        """Check if a session is currently live."""
        if not session:
            return False
        
        # Check date_start and date_end
        start = session.get("date_start")
        end = session.get("date_end")
        
        if not start:
            return False
        
        now = datetime.now(timezone.utc)
        
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            
            # Session has started
            if start_dt > now:
                return False
            
            # If no end time, assume live for 3 hours after start
            if not end:
                from datetime import timedelta
                return now < start_dt + timedelta(hours=3)
            
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            return now <= end_dt
            
        except Exception:
            return False
    
    def get_live_timing(self, session_key: str = "latest") -> Dict:
        """
        Get comprehensive live timing data.
        
        Returns:
            {
                "session": {...},
                "is_live": bool,
                "entries": [
                    {
                        "position": 1,
                        "driver_number": "1",
                        "driver_code": "VER",
                        "driver_name": "Max Verstappen",
                        "team": "Red Bull Racing",
                        "interval": "+0.000",
                        "gap_to_leader": "",
                        "last_lap": "1:32.456",
                        "best_lap": "1:31.234",
                        "laps": 45,
                        ...
                    }
                ]
            }
        """
        # Get session info
        session = self.get_current_session() if session_key == "latest" else self.get_session_by_key(int(session_key))
        
        if not session:
            return {
                "session": None,
                "is_live": False,
                "entries": [],
                "error": "No session found"
            }
        
        actual_key = session.get("session_key", session_key)
        is_live = self.is_session_live(session)
        
        # Get all data
        drivers = {d["driver_number"]: d for d in self.get_drivers(actual_key)}
        positions = self.get_position_data(actual_key)
        intervals = self.get_intervals(actual_key)
        lap_times = self.get_latest_lap_times(actual_key)
        
        # Build entries
        entries = []
        leader_time = None
        
        for pos_data in positions:
            driver_num = pos_data.get("driver_number")
            if not driver_num:
                continue
            
            driver = drivers.get(driver_num, {})
            interval = intervals.get(driver_num, {})
            lap = lap_times.get(driver_num, {})
            
            position = pos_data.get("position", 0)
            
            # Format lap times
            last_lap_duration = lap.get("lap_duration")
            if last_lap_duration:
                mins, secs = divmod(last_lap_duration, 60)
                last_lap = f"{int(mins)}:{secs:06.3f}"
            else:
                last_lap = ""
            
            # Calculate intervals
            gap_to_leader = interval.get("gap_to_leader")
            interval_val = interval.get("interval")
            
            if position == 1:
                gap_str = ""
                interval_str = ""
            else:
                gap_str = f"+{gap_to_leader:.3f}" if gap_to_leader else ""
                interval_str = f"+{interval_val:.3f}" if interval_val else ""
            
            entries.append({
                "position": position,
                "driver_number": str(driver_num),
                "driver_code": driver.get("name_acronym", ""),
                "driver_name": driver.get("full_name", f"Driver #{driver_num}"),
                "team": driver.get("team_name", ""),
                "team_color": driver.get("team_colour", ""),
                "interval": interval_str,
                "gap_to_leader": gap_str,
                "last_lap": last_lap,
                "best_lap": "",  # Would need additional API call
                "laps": lap.get("lap_number", 0),
                "pit_stops": lap.get("pit_stop_count", 0) if "pit_stop_count" in lap else None,
            })
        
        # Sort by position
        entries.sort(key=lambda x: x["position"] if x["position"] > 0 else 999)
        
        return {
            "session": {
                "key": session.get("session_key"),
                "name": session.get("session_name", ""),
                "type": session.get("session_type", ""),
                "meeting_name": session.get("meeting_name", ""),
                "circuit": session.get("circuit_short_name", ""),
                "country": session.get("country_name", ""),
                "date_start": session.get("date_start"),
                "date_end": session.get("date_end"),
            },
            "is_live": is_live,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entries": entries,
        }


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler."""
    
    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            
            client = OpenF1Client()
            
            # Just check status
            if "status" in query:
                session = client.get_current_session()
                is_live = client.is_session_live(session) if session else False
                
                self._send_json({
                    "series": "f1",
                    "is_live": is_live,
                    "session": {
                        "name": session.get("session_name") if session else None,
                        "meeting": session.get("meeting_name") if session else None,
                    } if session else None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return
            
            # Get session key
            session_key = query.get("session", ["latest"])[0]
            
            # Get live timing data
            timing_data = client.get_live_timing(session_key)
            
            self._send_json({
                "series": "f1",
                "source": "openf1",
                **timing_data
            })
            
        except urllib.error.HTTPError as e:
            self._send_error(e.code, f"OpenF1 API error: {e.reason}")
        except urllib.error.URLError as e:
            self._send_error(503, f"Cannot reach OpenF1 API: {e.reason}")
        except Exception as e:
            self._send_error(500, str(e))
    
    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=5")  # 5 second cache for live data
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def _send_error(self, status: int, message: str):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({
            "error": message,
            "status": status
        }).encode())


if __name__ == "__main__":
    # Test locally
    client = OpenF1Client()
    
    print("Getting live timing data...")
    data = client.get_live_timing()
    
    print(f"\nSession: {data['session']}")
    print(f"Is Live: {data['is_live']}")
    print(f"\nTop 10:")
    
    for entry in data['entries'][:10]:
        print(f"  {entry['position']:2d}. #{entry['driver_number']:2s} {entry['driver_code']:3s} "
              f"{entry['driver_name']:25s} {entry['gap_to_leader']:>10s} {entry['last_lap']}")
