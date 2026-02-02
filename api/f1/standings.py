"""F1 Standings API endpoint."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request

def fetch_f1_drivers(year: int = 2025) -> list:
    """Fetch F1 driver info from OpenF1 API."""
    # Get the most recent session to get current drivers
    url = f"https://api.openf1.org/v1/drivers?session_key=latest"
    req = urllib.request.Request(url, headers={"User-Agent": "MotorsportAggregator/1.0"})
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    
    # Deduplicate by driver number
    seen = set()
    drivers = []
    for d in data:
        num = d.get("driver_number")
        if num and num not in seen:
            seen.add(num)
            drivers.append({
                "number": num,
                "code": d.get("name_acronym"),
                "name": f"{d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                "team": d.get("team_name"),
                "team_color": d.get("team_colour"),
            })
    
    return sorted(drivers, key=lambda x: x.get("number", 99))

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            drivers = fetch_f1_drivers(2025)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            response = {
                "series": "f1",
                "season": 2025,
                "drivers": drivers,
                "note": "Driver list from latest session. Championship standings require additional data source."
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
