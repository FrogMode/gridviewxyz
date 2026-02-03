"""Live Telemetry API - F1 via OpenF1, expandable to other series."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
from datetime import datetime

OPENF1_BASE = "https://api.openf1.org/v1"

def fetch_f1_sessions(year: int = None) -> list:
    """Get available F1 sessions."""
    if year is None:
        year = datetime.now().year
    
    url = f"{OPENF1_BASE}/sessions?year={year}"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        sessions = json.loads(resp.read())
    
    # Return simplified session list, sorted by date (most recent first)
    result = [{
        "session_key": s.get("session_key"),
        "meeting_key": s.get("meeting_key"),
        "name": s.get("session_name"),
        "meeting": s.get("location") or s.get("circuit_short_name") or "Unknown",
        "location": s.get("location"),
        "country": s.get("country_name"),
        "circuit": s.get("circuit_short_name"),
        "date": s.get("date_start"),
        "type": s.get("session_type")
    } for s in sessions]
    
    # Sort by date, most recent first
    result.sort(key=lambda x: x.get("date") or "", reverse=True)
    return result

def fetch_f1_meetings(year: int = None) -> list:
    """Get F1 meetings (Grand Prix events) grouped with their sessions."""
    if year is None:
        year = datetime.now().year
    
    url = f"{OPENF1_BASE}/sessions?year={year}"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        sessions = json.loads(resp.read())
    
    # Group by meeting
    meetings = {}
    for s in sessions:
        meeting_key = s.get("meeting_key")
        if meeting_key not in meetings:
            meetings[meeting_key] = {
                "meeting_key": meeting_key,
                "name": s.get("location") or s.get("circuit_short_name") or "Unknown",
                "country": s.get("country_name"),
                "circuit": s.get("circuit_short_name"),
                "date": s.get("date_start", "")[:10],  # Just the date part
                "sessions": []
            }
        meetings[meeting_key]["sessions"].append({
            "session_key": s.get("session_key"),
            "name": s.get("session_name"),
            "type": s.get("session_type"),
            "date": s.get("date_start")
        })
    
    # Sort meetings by date (soonest/earliest first)
    result = list(meetings.values())
    result.sort(key=lambda x: x.get("date") or "")
    
    # Sort sessions within each meeting by date
    for m in result:
        m["sessions"].sort(key=lambda x: x.get("date") or "")
    
    return result

def fetch_f1_drivers(session_key) -> list:
    """Get drivers for a session."""
    url = f"{OPENF1_BASE}/drivers?session_key={session_key}"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        drivers = json.loads(resp.read())
    
    # Deduplicate by driver number (API sometimes returns duplicates)
    seen = set()
    unique_drivers = []
    for d in drivers:
        num = d.get("driver_number")
        if num and num not in seen:
            seen.add(num)
            unique_drivers.append({
                "number": num,
                "code": d.get("name_acronym"),
                "name": f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                "team": d.get("team_name"),
                "team_color": d.get("team_colour")
            })
    
    return sorted(unique_drivers, key=lambda x: x.get("number", 99))

def fetch_f1_car_data(session_key: int = None, driver_number: int = None, limit: int = 100) -> list:
    """Get car telemetry data."""
    params = []
    if session_key:
        params.append(f"session_key={session_key}")
    else:
        params.append("session_key=latest")
    
    if driver_number:
        params.append(f"driver_number={driver_number}")
    
    url = f"{OPENF1_BASE}/car_data?{'&'.join(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    
    # Return latest entries
    return data[-limit:] if len(data) > limit else data

def fetch_f1_position(session_key: int = None, driver_number: int = None) -> list:
    """Get position data."""
    params = []
    if session_key:
        params.append(f"session_key={session_key}")
    else:
        params.append("session_key=latest")
    
    if driver_number:
        params.append(f"driver_number={driver_number}")
    
    url = f"{OPENF1_BASE}/position?{'&'.join(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def fetch_f1_intervals(session_key: int = None) -> list:
    """Get interval/gap data."""
    params = f"session_key={session_key}" if session_key else "session_key=latest"
    url = f"{OPENF1_BASE}/intervals?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            series = query.get('series', ['f1'])[0].lower()
            action = query.get('action', ['sessions'])[0]
            
            # Currently only F1 supported
            if series != 'f1':
                self._send_json({
                    "error": f"Series '{series}' telemetry not yet supported",
                    "supported": ["f1"],
                    "coming_soon": ["imsa", "wec"]
                })
                return
            
            session_key = query.get('session', [None])[0]
            if session_key:
                session_key = int(session_key)
            
            driver = query.get('driver', [None])[0]
            if driver:
                driver = int(driver)
            
            year = query.get('year', [None])[0]
            if year:
                year = int(year)
            
            if action == 'sessions':
                # List available sessions
                sessions = fetch_f1_sessions(year)
                response = {
                    "series": "f1",
                    "year": year or datetime.now().year,
                    "sessions": sessions
                }
            
            elif action == 'meetings':
                # List meetings (Grand Prix) with their sessions grouped
                meetings = fetch_f1_meetings(year)
                response = {
                    "series": "f1",
                    "year": year or datetime.now().year,
                    "meetings": meetings
                }
            
            elif action == 'drivers':
                # List drivers for session
                drivers = fetch_f1_drivers(session_key or "latest")
                response = {
                    "series": "f1",
                    "session_key": session_key,
                    "drivers": drivers
                }
            
            elif action == 'telemetry':
                # Get car telemetry
                limit = int(query.get('limit', ['100'])[0])
                data = fetch_f1_car_data(session_key, driver, limit)
                response = {
                    "series": "f1",
                    "session_key": session_key,
                    "driver": driver,
                    "count": len(data),
                    "telemetry": data
                }
            
            elif action == 'positions':
                # Get position data
                data = fetch_f1_position(session_key, driver)
                # Get latest position per driver
                latest = {}
                for p in data:
                    dn = p.get("driver_number")
                    latest[dn] = p
                response = {
                    "series": "f1",
                    "session_key": session_key,
                    "positions": sorted(latest.values(), key=lambda x: x.get("position", 99))
                }
            
            elif action == 'intervals':
                # Get gaps
                data = fetch_f1_intervals(session_key)
                # Get latest per driver
                latest = {}
                for i in data:
                    dn = i.get("driver_number")
                    latest[dn] = i
                response = {
                    "series": "f1", 
                    "session_key": session_key,
                    "intervals": list(latest.values())
                }
            
            else:
                response = {
                    "error": f"Unknown action: {action}",
                    "available": ["sessions", "drivers", "telemetry", "positions", "intervals"]
                }
            
            self._send_json(response)
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=5')  # Short cache for live data
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
