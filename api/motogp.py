"""MotoGP API - fetches schedule and results from TheSportsDB.

TheSportsDB League ID: 4407
"""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
from datetime import datetime
import re

SPORTSDB_LEAGUE_ID = "4407"  # MotoGP
SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"

# Simple in-memory cache
_cache = {}
_cache_ttl = 600  # 10 minutes


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


def fetch_motogp_season(year: int = None) -> list:
    """Fetch MotoGP events for a season."""
    if year is None:
        year = datetime.now().year
    
    url = f"{SPORTSDB_BASE}/eventsseason.php?id={SPORTSDB_LEAGUE_ID}&s={year}"
    
    try:
        data = _cached_fetch(url)
    except Exception:
        return []
    
    events = data.get("events") or []
    results = []
    
    for event in events:
        # Parse results text if available
        results_text = event.get("strResult") or ""
        parsed_results = parse_results(results_text) if results_text else []
        parsed_standings = parse_standings(results_text) if results_text else []
        
        results.append({
            "id": event.get("idEvent"),
            "name": event.get("strEvent"),
            "date": event.get("dateEvent"),
            "time": event.get("strTime"),
            "timestamp": event.get("strTimestamp"),
            "venue": event.get("strVenue"),
            "city": event.get("strCity"),
            "country": event.get("strCountry"),
            "round": event.get("intRound"),
            "poster": event.get("strPoster"),
            "thumb": event.get("strThumb"),
            "description": (event.get("strDescriptionEN") or "")[:500],
            "video": event.get("strVideo"),
            "status": event.get("strStatus"),
            "results": parsed_results[:15] if parsed_results else None,
            "standings_after": parsed_standings[:10] if parsed_standings else None,
        })
    
    return sorted(results, key=lambda x: x.get("date") or "")


def parse_results(text: str) -> list:
    """Parse race results from strResult field."""
    if not text:
        return []
    
    results = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Skip headers and standings section
        if line.startswith("Not Classified") or line.startswith("-----"):
            break
        if "Standing" in line or line.startswith("Pos /"):
            continue
        
        # Try to parse result line: "1 /Marc Marquez /Ducati Lenovo Team /39:37.244"
        # or with gap: "2 /Alex Marques /BK8 Gresini Racing MotoGP /+1.732"
        match = re.match(r'^(\d+)\s*/\s*([^/]+)\s*/\s*([^/]+)\s*/\s*(.+)$', line)
        if match:
            results.append({
                "position": int(match.group(1)),
                "rider": match.group(2).strip(),
                "team": match.group(3).strip(),
                "time_gap": match.group(4).strip()
            })
    
    return results


def parse_standings(text: str) -> list:
    """Parse championship standings from strResult field."""
    if not text or "Standing" not in text:
        return []
    
    standings = []
    lines = text.strip().split('\n')
    in_standings = False
    
    for line in lines:
        line = line.strip()
        if "Standing" in line:
            in_standings = True
            continue
        
        if not in_standings:
            continue
        
        if not line or line.startswith("Pos /"):
            continue
        
        # Parse standings line: "1 /Marc Marques /Ducati Lenovo Team /37"
        match = re.match(r'^(\d+)\s*/\s*([^/]+)\s*/\s*([^/]+)\s*/\s*(\d+)$', line)
        if match:
            standings.append({
                "position": int(match.group(1)),
                "rider": match.group(2).strip(),
                "team": match.group(3).strip(),
                "points": int(match.group(4))
            })
    
    return standings


def get_upcoming_races(limit: int = 5) -> list:
    """Get upcoming MotoGP races."""
    events = fetch_motogp_season()
    today = datetime.now().strftime("%Y-%m-%d")
    
    upcoming = []
    for event in events:
        date = event.get("date")
        if date and date >= today:
            # Check if it's a race (not practice/qualifying)
            name = event.get("name", "").lower()
            if "gp" in name or "race" in name:
                upcoming.append(event)
                if len(upcoming) >= limit:
                    break
    
    return upcoming


def get_recent_results(limit: int = 3) -> list:
    """Get recent race results."""
    events = fetch_motogp_season()
    today = datetime.now().strftime("%Y-%m-%d")
    
    recent = []
    for event in reversed(events):
        date = event.get("date")
        name = event.get("name", "").lower()
        results = event.get("results")
        
        # Must be a past race with results
        if date and date < today and ("gp" in name or "race" in name) and results:
            recent.append(event)
            if len(recent) >= limit:
                break
    
    return recent


def get_available_years() -> list:
    """Return available MotoGP seasons."""
    current_year = datetime.now().year
    return list(range(current_year, 2018, -1))


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
            
            # Get upcoming races
            if 'upcoming' in query:
                limit = int(query.get('limit', [5])[0])
                races = get_upcoming_races(limit=limit)
                self._send_json({
                    "series": "MotoGP",
                    "upcoming": races
                })
                return
            
            # Get recent results
            if 'results' in query:
                limit = int(query.get('limit', [3])[0])
                results = get_recent_results(limit=limit)
                self._send_json({
                    "series": "MotoGP",
                    "recent": results
                })
                return
            
            # Get specific event
            event_id = query.get('event', [None])[0]
            if event_id:
                events = fetch_motogp_season(year or datetime.now().year)
                event = next((e for e in events if str(e.get("id")) == event_id), None)
                self._send_json({"event": event})
                return
            
            # Default: get season calendar
            events = fetch_motogp_season(year)
            # Filter to main races for cleaner calendar
            main_events = [e for e in events if "GP" in (e.get("name") or "") or "Race" in (e.get("name") or "")]
            
            response = {
                "season": year or datetime.now().year,
                "series": "MotoGP",
                "events": main_events if main_events else events
            }
            
            self._send_json(response)
            
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
