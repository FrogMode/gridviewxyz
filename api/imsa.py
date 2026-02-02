"""IMSA Results API - scrapes Alkamelsystems JSON endpoints."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import re
from html.parser import HTMLParser

ALKAMEL_BASE = "https://imsa.results.alkamelcloud.com"

class LinkParser(HTMLParser):
    """Parse JSON links from Alkamelsystems results page."""
    def __init__(self):
        super().__init__()
        self.links = []
    
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            attrs_dict = dict(attrs)
            href = attrs_dict.get('href', '')
            if href.endswith('.JSON'):
                self.links.append(href)

def fetch_available_events() -> list:
    """Scrape main page for available events and their JSON links."""
    url = f"{ALKAMEL_BASE}/"
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    
    parser = LinkParser()
    parser.feed(html)
    
    # Parse links to extract events
    events = {}
    for link in parser.links:
        # Pattern: Results/{year_code}_{year}/{event_num}_{venue}/{series}/{session}/...
        match = re.search(r'Results/(\d+)_(\d+)/(\d+)_([^/]+)/([^/]+)/([^/]+)/([^/]+\.JSON)', link)
        if match:
            year = match.group(2)
            venue = match.group(4).replace('%20', ' ')
            series = match.group(5).replace('%20', ' ')
            session_part = match.group(6).replace('%20', ' ')
            doc_name = match.group(7)
            
            # Create event key
            event_key = f"{year}_{venue}_{series}"
            if event_key not in events:
                events[event_key] = {
                    "year": int(year),
                    "venue": venue,
                    "series": series,
                    "sessions": {}
                }
            
            # Parse session
            session_match = re.match(r'(\d+)_(.+)', session_part)
            if session_match:
                session_name = session_match.group(2)
                if session_name not in events[event_key]["sessions"]:
                    events[event_key]["sessions"][session_name] = []
                events[event_key]["sessions"][session_name].append({
                    "doc": doc_name,
                    "url": f"{ALKAMEL_BASE}/{link}"
                })
    
    return list(events.values())

def fetch_results_json(url: str) -> dict:
    """Fetch a specific results JSON file."""
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def get_latest_race_results() -> dict:
    """Get the most recent race results."""
    events = fetch_available_events()
    
    # Find races (not practice/qualifying)
    for event in reversed(events):  # Most recent first
        sessions = event.get("sessions", {})
        for session_name, docs in sessions.items():
            if "Race" in session_name:
                # Find the main results document
                for doc in docs:
                    if "03_Results" in doc["doc"] or doc["doc"].startswith("03_"):
                        try:
                            return fetch_results_json(doc["url"])
                        except:
                            continue
    return None

def format_classification(data: dict) -> list:
    """Format classification data for API response."""
    if not data or "classification" not in data:
        return []
    
    results = []
    for entry in data.get("classification", [])[:30]:  # Top 30
        drivers = entry.get("drivers", [])
        driver_names = ", ".join([f"{d.get('firstname', '')} {d.get('surname', '')}".strip() 
                                   for d in drivers[:3]])  # First 3 drivers
        
        results.append({
            "position": entry.get("position"),
            "number": entry.get("number"),
            "class": entry.get("class"),
            "team": entry.get("team"),
            "vehicle": entry.get("vehicle"),
            "manufacturer": entry.get("manufacturer"),
            "drivers": driver_names,
            "laps": entry.get("laps"),
            "time": entry.get("time"),
            "gap": entry.get("gap_first"),
            "status": entry.get("status")
        })
    
    return results

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            # List available events
            if 'events' in query:
                events = fetch_available_events()
                # Simplify for listing
                event_list = [{
                    "year": e["year"],
                    "venue": e["venue"],
                    "series": e["series"],
                    "sessions": list(e["sessions"].keys())
                } for e in events]
                response = {"events": event_list}
                self._send_json(response)
                return
            
            # Fetch specific URL
            url = query.get('url', [None])[0]
            if url:
                data = fetch_results_json(url)
                response = {
                    "session": data.get("session"),
                    "fastest_lap": data.get("fastest_lap"),
                    "classification": format_classification(data)
                }
                self._send_json(response)
                return
            
            # Default: get latest race results
            data = get_latest_race_results()
            if data:
                session_info = data.get("session", {})
                response = {
                    "event": session_info.get("event_name"),
                    "session": session_info.get("session_name"),
                    "circuit": session_info.get("circuit", {}).get("name"),
                    "date": session_info.get("session_date"),
                    "fastest_lap": data.get("fastest_lap"),
                    "results": format_classification(data)
                }
            else:
                response = {"error": "No race results found"}
            
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
