"""F1 Calendar API endpoint."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request

def fetch_f1_calendar(year: int = 2025) -> list:
    """Fetch F1 calendar from OpenF1 API."""
    url = f"https://api.openf1.org/v1/meetings?year={year}"
    req = urllib.request.Request(url, headers={"User-Agent": "MotorsportAggregator/1.0"})
    
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    
    return [
        {
            "round": m.get("meeting_key"),
            "name": m.get("meeting_name"),
            "location": m.get("location"),
            "country": m.get("country_name"),
            "circuit": m.get("circuit_short_name"),
            "date": m.get("date_start"),
        }
        for m in data
    ]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            calendar = fetch_f1_calendar(2025)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            response = {
                "series": "f1",
                "season": 2025,
                "events": calendar
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
