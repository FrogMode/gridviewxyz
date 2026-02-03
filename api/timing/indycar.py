"""
IndyCar Live Timing API - Vercel Serverless Endpoint

Uses IndyCar's Azure Blob Storage endpoints for real-time timing data.
Public endpoints, no auth required.

Endpoints:
  GET /api/timing/indycar            - Get live timing data
  GET /api/timing/indycar?status=1   - Check if session is active
  GET /api/timing/indycar?series=nxt - Get INDY NXT timing

Data includes:
  - Driver positions and intervals
  - Lap times (latest and best)
  - Session info (status, lap number, event name)
  - Pit stop counts
  - Tire compound info
"""

from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, List, Any


# Session status colors/states
SESSION_STATUS = {
    "GREEN": "green",
    "YELLOW": "caution",
    "RED": "red",
    "WARM": "warm_up",
    "COLD": "cold",
    "CHECKERED": "checkered",
    "WHITE": "white_flag",
}


class IndyCarClient:
    """IndyCar Azure Blob Storage client for live timing data."""
    
    BASE_URL = "https://indycar.blob.core.windows.net/racecontrol"
    NTT_URL = "https://indycar.blob.core.windows.net/ntt-data/INDYCAR_DATA_POLLING"
    USER_AGENT = "GridView/1.0"
    
    ENDPOINTS = {
        "config": "tsconfig.json",
        "timing": "timingscoring-ris.json",
        "leaderboard": "trackactivityleaderboardfeed.json",
        "schedule": "schedulefeed.json",
        "drivers": "driversfeed.json",
        # INDY NXT endpoints
        "drivers_nxt": "driversfeed_nxt.json",
        "schedule_nxt": "schedulefeed_nxt.json",
        "leaderboard_nxt": "trackactivityleaderboardfeed_nxt.json",
    }
    
    def __init__(self, series: str = "indycar"):
        self.series = series.lower()  # "indycar" or "indynxt"
    
    def _fetch(self, endpoint: str, cache_bust: bool = True) -> Any:
        """Fetch JSON from Azure Blob Storage."""
        url = f"{self.BASE_URL}/{endpoint}"
        
        if cache_bust:
            url += f"?{int(time.time())}"
        
        req = urllib.request.Request(url, headers={
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json",
        })
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    
    def get_config(self) -> Dict:
        """Get session configuration from tsconfig.json."""
        return self._fetch(self.ENDPOINTS["config"])
    
    def is_session_active(self) -> bool:
        """Check if a session is currently active."""
        try:
            config = self.get_config()
            return not config.get("no_track_activity", True)
        except Exception:
            return False
    
    def get_timing_data(self) -> Optional[Dict]:
        """Get live timing/scoring data."""
        try:
            return self._fetch(self.ENDPOINTS["timing"])
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
    
    def get_leaderboard(self) -> Optional[Dict]:
        """Get leaderboard data (alternative source)."""
        endpoint = (self.ENDPOINTS["leaderboard_nxt"] 
                   if self.series == "indynxt" 
                   else self.ENDPOINTS["leaderboard"])
        try:
            return self._fetch(endpoint)
        except Exception:
            return None
    
    def get_ntt_data(self) -> Optional[Dict]:
        """Get NTT pit stop prediction data."""
        try:
            url = f"{self.NTT_URL}/data_polling_blob.json?{int(time.time())}"
            req = urllib.request.Request(url, headers={
                "User-Agent": self.USER_AGENT,
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None
    
    def get_live_timing(self) -> Dict:
        """
        Get comprehensive live timing data.
        
        Returns:
            {
                "session": {...},
                "is_live": bool,
                "entries": [
                    {
                        "position": 1,
                        "driver_number": "10",
                        "driver_name": "Alex Palou",
                        "team": "Chip Ganassi Racing",
                        "interval": "+0.123",
                        "gap_to_leader": "",
                        "last_lap": "1:01.234",
                        "best_lap": "1:00.987",
                        "pit_stops": 2,
                        "tire_compound": "Primary",
                        ...
                    }
                ]
            }
        """
        # Check if session is active
        is_live = self.is_session_active()
        
        # Try timing data first
        timing = self.get_timing_data()
        
        if timing:
            return self._parse_timing_ris(timing, is_live)
        
        # Fall back to leaderboard
        leaderboard = self.get_leaderboard()
        
        if leaderboard:
            return self._parse_leaderboard(leaderboard, is_live)
        
        # No data available
        return {
            "session": None,
            "is_live": False,
            "entries": [],
            "message": "No active session" if not is_live else "Unable to fetch timing data"
        }
    
    def _parse_timing_ris(self, data: Dict, is_live: bool) -> Dict:
        """Parse timingscoring-ris.json format."""
        timing = data.get("timing_results", {})
        heartbeat = timing.get("heartbeat", {})
        raw_entries = timing.get("entries", [])
        
        # Get session status
        status_raw = heartbeat.get("SessionStatus", "COLD")
        session_status = SESSION_STATUS.get(status_raw.upper(), status_raw.lower())
        
        # Parse entries
        entries = []
        for entry in raw_entries:
            position = entry.get("Position", 0)
            
            # Calculate gap/interval
            gap = entry.get("Gap", "")
            interval = entry.get("Interval", "")
            
            # Format as proper interval strings
            gap_str = f"+{gap}" if gap and not gap.startswith("+") and not gap.startswith("-") else gap
            interval_str = f"+{interval}" if interval and not interval.startswith("+") and not interval.startswith("-") else interval
            
            if position == 1:
                gap_str = ""
                interval_str = ""
            
            entries.append({
                "position": position,
                "driver_number": str(entry.get("Number", "")),
                "driver_name": entry.get("Driver", ""),
                "team": entry.get("Team", ""),
                "interval": interval_str,
                "gap_to_leader": gap_str,
                "last_lap": entry.get("LastLap", ""),
                "best_lap": entry.get("BestLap", ""),
                "laps": entry.get("LapsComplete", 0),
                "laps_led": entry.get("LapsLed", 0),
                "pit_stops": entry.get("PitStops", 0),
                "tire_compound": entry.get("TireCompound", ""),
                "status": entry.get("Status", ""),
            })
        
        # Sort by position
        entries.sort(key=lambda x: x["position"] if x["position"] > 0 else 999)
        
        return {
            "session": {
                "status": session_status,
                "status_raw": status_raw,
                "type": heartbeat.get("SessionType", ""),
                "lap_number": heartbeat.get("LapNumber", 0),
                "laps_remaining": heartbeat.get("LapsRemaining", 0),
                "time_remaining": heartbeat.get("TimeRemaining", ""),
                "elapsed_time": heartbeat.get("ElapsedTime", ""),
                "event_name": heartbeat.get("EventName", ""),
                "track_name": heartbeat.get("TrackName", ""),
            },
            "is_live": is_live,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entries": entries,
        }
    
    def _parse_leaderboard(self, data: Dict, is_live: bool) -> Dict:
        """Parse trackactivityleaderboardfeed.json format."""
        session = data.get("session", {})
        raw_entries = data.get("entries", [])
        
        # Get session status
        status_raw = session.get("status", "COLD")
        session_status = SESSION_STATUS.get(status_raw.upper(), status_raw.lower())
        
        # Parse entries
        entries = []
        for entry in raw_entries:
            position = entry.get("position", 0)
            
            gap = entry.get("gap", "")
            interval = entry.get("interval", "")
            
            gap_str = f"+{gap}" if gap and not gap.startswith(("+", "-")) else gap
            interval_str = f"+{interval}" if interval and not interval.startswith(("+", "-")) else interval
            
            if position == 1:
                gap_str = ""
                interval_str = ""
            
            entries.append({
                "position": position,
                "driver_number": str(entry.get("carNumber", "")),
                "driver_name": entry.get("driverName", ""),
                "team": entry.get("teamName", ""),
                "interval": interval_str,
                "gap_to_leader": gap_str,
                "last_lap": entry.get("lastLapTime", ""),
                "best_lap": entry.get("bestLapTime", ""),
                "laps": entry.get("lapsComplete", 0),
                "laps_led": entry.get("lapsLed", 0),
                "pit_stops": entry.get("pitStops", 0),
                "tire_compound": entry.get("tireCompound", ""),
                "status": entry.get("status", ""),
            })
        
        entries.sort(key=lambda x: x["position"] if x["position"] > 0 else 999)
        
        return {
            "session": {
                "status": session_status,
                "status_raw": status_raw,
                "type": session.get("sessionType", ""),
                "lap_number": session.get("lapNumber", 0),
                "laps_remaining": session.get("lapsRemaining", 0),
                "time_remaining": session.get("timeRemaining", ""),
                "elapsed_time": session.get("elapsedTime", ""),
                "event_name": session.get("eventName", ""),
                "track_name": session.get("trackName", ""),
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
            
            # Determine series (indycar or indynxt)
            series = query.get("series", ["indycar"])[0].lower()
            if series in ("nxt", "indynxt", "indy-nxt"):
                series = "indynxt"
            else:
                series = "indycar"
            
            client = IndyCarClient(series=series)
            
            # Just check status
            if "status" in query:
                is_live = client.is_session_active()
                
                # Try to get basic session info
                session_info = None
                if is_live:
                    try:
                        timing = client.get_timing_data()
                        if timing:
                            heartbeat = timing.get("timing_results", {}).get("heartbeat", {})
                            session_info = {
                                "event": heartbeat.get("EventName"),
                                "track": heartbeat.get("TrackName"),
                                "status": heartbeat.get("SessionStatus"),
                            }
                    except Exception:
                        pass
                
                self._send_json({
                    "series": "indycar" if series == "indycar" else "indynxt",
                    "is_live": is_live,
                    "session": session_info,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return
            
            # Get live timing data
            timing_data = client.get_live_timing()
            
            # Optionally include NTT data
            if query.get("ntt"):
                ntt_data = client.get_ntt_data()
                if ntt_data:
                    timing_data["ntt_predictions"] = ntt_data
            
            self._send_json({
                "series": "indycar" if series == "indycar" else "indynxt",
                "source": "azure-blob",
                **timing_data
            })
            
        except urllib.error.HTTPError as e:
            self._send_error(e.code, f"IndyCar data error: {e.reason}")
        except urllib.error.URLError as e:
            self._send_error(503, f"Cannot reach IndyCar data: {e.reason}")
        except Exception as e:
            self._send_error(500, str(e))
    
    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=3")  # 3 second cache for live data
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
    client = IndyCarClient()
    
    print("Checking session status...")
    is_live = client.is_session_active()
    print(f"Session active: {is_live}")
    
    print("\nGetting live timing data...")
    data = client.get_live_timing()
    
    if data.get("session"):
        print(f"\nSession: {data['session'].get('event_name', 'Unknown')}")
        print(f"Track: {data['session'].get('track_name', 'Unknown')}")
        print(f"Status: {data['session'].get('status', 'Unknown')}")
        print(f"Lap: {data['session'].get('lap_number', 0)}")
        
        if data["entries"]:
            print(f"\nTop 10:")
            for entry in data["entries"][:10]:
                print(f"  {entry['position']:2d}. #{entry['driver_number']:3s} {entry['driver_name']:25s} "
                      f"{entry['gap_to_leader']:>10s} {entry['last_lap']}")
    else:
        print(f"\n{data.get('message', 'No data available')}")
