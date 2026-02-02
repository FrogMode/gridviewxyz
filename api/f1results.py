"""F1 2024 Season Results API endpoint."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request

def fetch_f1_sessions(year: int = 2024) -> list:
    """Fetch F1 race sessions from OpenF1 API."""
    url = f"https://api.openf1.org/v1/sessions?year={year}&session_type=Race"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def fetch_race_results(session_key: int) -> list:
    """Fetch results for a specific race session."""
    # Get final positions
    url = f"https://api.openf1.org/v1/position?session_key={session_key}"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        positions = json.loads(resp.read())
    
    # Get driver info
    url2 = f"https://api.openf1.org/v1/drivers?session_key={session_key}"
    req2 = urllib.request.Request(url2, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req2, timeout=15) as resp:
        drivers = json.loads(resp.read())
    
    # Map driver numbers to info
    driver_map = {}
    for d in drivers:
        num = d.get("driver_number")
        if num:
            driver_map[num] = {
                "name": f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                "code": d.get("name_acronym"),
                "team": d.get("team_name"),
                "team_color": d.get("team_colour")
            }
    
    # Get latest position for each driver
    final_positions = {}
    for pos in positions:
        driver_num = pos.get("driver_number")
        if driver_num:
            final_positions[driver_num] = pos.get("position")
    
    # Build results
    results = []
    for driver_num, position in sorted(final_positions.items(), key=lambda x: x[1] or 99):
        driver_info = driver_map.get(driver_num, {})
        results.append({
            "position": position,
            "driver_number": driver_num,
            "driver": driver_info.get("name", f"Driver {driver_num}"),
            "code": driver_info.get("code", "???"),
            "team": driver_info.get("team", "Unknown"),
            "team_color": driver_info.get("team_color", "ffffff")
        })
    
    return results[:20]  # Top 20

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Parse query params
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            session_key = query.get('session', [None])[0]
            
            if session_key:
                # Get specific race results
                results = fetch_race_results(int(session_key))
                response = {
                    "session_key": session_key,
                    "results": results
                }
            else:
                # Get all 2024 races
                sessions = fetch_f1_sessions(2024)
                races = []
                for s in sessions:
                    races.append({
                        "session_key": s.get("session_key"),
                        "name": s.get("meeting_name") or s.get("session_name"),
                        "location": s.get("location"),
                        "country": s.get("country_name"),
                        "date": s.get("date_start"),
                        "circuit": s.get("circuit_short_name")
                    })
                response = {
                    "season": 2024,
                    "races": races
                }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
        return
