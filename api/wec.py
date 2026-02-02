"""WEC (World Endurance Championship) API via TheSportsDB."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
from datetime import datetime

SPORTSDB_LEAGUE_ID = "4413"  # WEC
SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"

def fetch_wec_season(year: int = None) -> list:
    """Fetch WEC events for a season."""
    if year is None:
        year = datetime.now().year
    
    url = f"{SPORTSDB_BASE}/eventsseason.php?id={SPORTSDB_LEAGUE_ID}&s={year}"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    
    events = data.get("events") or []
    results = []
    
    for event in events:
        results.append({
            "id": event.get("idEvent"),
            "name": event.get("strEvent"),
            "date": event.get("dateEvent"),
            "venue": event.get("strVenue"),
            "city": event.get("strCity"),
            "country": event.get("strCountry"),
            "round": event.get("intRound"),
            "poster": event.get("strPoster"),
            "results_text": event.get("strResult"),
            "description": event.get("strDescriptionEN", "")[:300] if event.get("strDescriptionEN") else None
        })
    
    return sorted(results, key=lambda x: x.get("date") or "")

def parse_results_text(text: str) -> list:
    """Parse the strResult field into structured data."""
    if not text:
        return []
    
    results = []
    lines = text.strip().split('\n')
    current_class = None
    position = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if it's a class header (e.g., "HYPERCAR", "LMGT3")
        if line.isupper() and not any(char.isdigit() for char in line):
            current_class = line
            position = 0
            continue
        
        # Try to parse a result line
        # Format: "1 TEAM NAME #XX Driver1, Driver2, Driver3"
        if line[0].isdigit():
            position += 1
            parts = line.split(' ', 1)
            if len(parts) >= 2:
                results.append({
                    "position": position,
                    "class": current_class,
                    "entry": parts[1] if len(parts) > 1 else line
                })
        else:
            # Might be a continuation or different format
            position += 1
            results.append({
                "position": position,
                "class": current_class,
                "entry": line
            })
    
    return results

def get_available_years() -> list:
    """Return available WEC seasons."""
    current_year = datetime.now().year
    # WEC modern era data typically available from 2012+
    return list(range(current_year, 2011, -1))

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            # Return available years
            if 'years' in query:
                response = {
                    "years": get_available_years(),
                    "default": datetime.now().year
                }
                self._send_json(response)
                return
            
            year = query.get('year', [None])[0]
            if year:
                year = int(year)
            
            event_id = query.get('event', [None])[0]
            
            if event_id:
                # Get specific event details (could expand this)
                events = fetch_wec_season(year or datetime.now().year)
                event = next((e for e in events if str(e.get("id")) == event_id), None)
                if event and event.get("results_text"):
                    event["results_parsed"] = parse_results_text(event["results_text"])
                response = {"event": event}
            else:
                # Get season calendar
                events = fetch_wec_season(year)
                response = {
                    "season": year or datetime.now().year,
                    "series": "WEC",
                    "events": events
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
        self.send_header('Cache-Control', 'public, max-age=300')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
