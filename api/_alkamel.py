"""
Alkamelsystems Scraper Base Module

Al Kamel Systems powers timing and results for many racing series:
- IMSA (imsa.results.alkamelcloud.com) - PUBLIC ACCESS ✓
- FIA WEC (fiawec.results.alkamelcloud.com) - Premium/Backoffice (paywalled)
- ELMS (elms.results.alkamelcloud.com) - Premium/Backoffice (paywalled)
- Asian Le Mans (alms.results.alkamelcloud.com) - Premium/Backoffice (paywalled)

Live timing is at: livetiming.alkamelsystems.com (Meteor.js SPA, requires WebSocket)

This module provides shared scraping utilities for Alkamelsystems results pages.
"""
import json
import re
import urllib.request
from html.parser import HTMLParser
from typing import List, Dict, Optional, Any


class AlkamelLinkParser(HTMLParser):
    """Parse JSON links from Alkamelsystems results page."""
    def __init__(self):
        super().__init__()
        self.links: List[str] = []
    
    def handle_starttag(self, tag: str, attrs: list):
        if tag == 'a':
            attrs_dict = dict(attrs)
            href = attrs_dict.get('href', '')
            if href.endswith('.JSON'):
                self.links.append(href)


class AlkamelScraper:
    """Base scraper for Alkamelsystems results pages."""
    
    def __init__(self, base_url: str, series_name: str = "Unknown"):
        """
        Initialize the scraper.
        
        Args:
            base_url: The base URL for the series (e.g., "https://imsa.results.alkamelcloud.com")
            series_name: Human-readable series name
        """
        self.base_url = base_url.rstrip('/')
        self.series_name = series_name
        self.user_agent = "GridView/1.0"
    
    def _fetch_html(self, path: str = "/") -> str:
        """Fetch HTML from the results page."""
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    
    def _fetch_json(self, url: str) -> Dict[str, Any]:
        """Fetch and parse a JSON file."""
        if not url.startswith('http'):
            url = f"{self.base_url}/{url}"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    
    def get_available_links(self) -> List[str]:
        """Scrape main page for available JSON links."""
        html = self._fetch_html()
        parser = AlkamelLinkParser()
        parser.feed(html)
        return parser.links
    
    def parse_link(self, link: str) -> Optional[Dict[str, Any]]:
        """
        Parse an Alkamelsystems results link to extract metadata.
        
        Link format: Results/{year_code}_{year}/{event_num}_{venue}/{series}/{session}/{doc}.JSON
        
        Returns dict with: year, venue, series, session, doc_type, full_url
        """
        # Pattern: Results/{year_code}_{year}/{event_num}_{venue}/{series}/{session}/{doc}.JSON
        match = re.search(
            r'Results/(\d+)_(\d+)/(\d+)_([^/]+)/([^/]+)/([^/]+)/([^/]+\.JSON)',
            link
        )
        if not match:
            return None
        
        return {
            "year_code": match.group(1),
            "year": int(match.group(2)),
            "event_num": match.group(3),
            "venue": match.group(4).replace('%20', ' '),
            "series": match.group(5).replace('%20', ' '),
            "session_raw": match.group(6).replace('%20', ' '),
            "doc_name": match.group(7),
            "full_url": f"{self.base_url}/{link}"
        }
    
    def get_events(self) -> List[Dict[str, Any]]:
        """
        Get all available events from the results page.
        
        Returns list of events with their sessions and documents.
        """
        links = self.get_available_links()
        events = {}
        
        for link in links:
            parsed = self.parse_link(link)
            if not parsed:
                continue
            
            # Create event key
            event_key = f"{parsed['year']}_{parsed['venue']}_{parsed['series']}"
            
            if event_key not in events:
                events[event_key] = {
                    "year": parsed["year"],
                    "venue": parsed["venue"],
                    "series": parsed["series"],
                    "sessions": {}
                }
            
            # Parse session name
            session_match = re.match(r'(\d+)_(.+)', parsed["session_raw"])
            if session_match:
                session_name = session_match.group(2)
            else:
                session_name = parsed["session_raw"]
            
            if session_name not in events[event_key]["sessions"]:
                events[event_key]["sessions"][session_name] = []
            
            events[event_key]["sessions"][session_name].append({
                "doc": parsed["doc_name"],
                "url": parsed["full_url"]
            })
        
        return list(events.values())
    
    def fetch_results(self, url: str) -> Dict[str, Any]:
        """Fetch a specific results JSON file."""
        return self._fetch_json(url)
    
    def format_classification(self, data: Dict[str, Any], limit: int = 30) -> List[Dict[str, Any]]:
        """
        Format classification data for API response.
        
        Args:
            data: Raw JSON data from results file
            limit: Maximum number of entries to return
            
        Returns:
            List of formatted result entries
        """
        if not data or "classification" not in data:
            return []
        
        results = []
        for entry in data.get("classification", [])[:limit]:
            drivers = entry.get("drivers", [])
            driver_names = ", ".join([
                f"{d.get('firstname', '')} {d.get('surname', '')}".strip() 
                for d in drivers[:3]
            ])
            
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
    
    def get_latest_race_results(self) -> Optional[Dict[str, Any]]:
        """Get the most recent race results."""
        events = self.get_events()
        
        for event in reversed(events):  # Most recent first
            sessions = event.get("sessions", {})
            for session_name, docs in sessions.items():
                if "Race" in session_name:
                    for doc in docs:
                        if "03_Results" in doc["doc"] or doc["doc"].startswith("03_"):
                            try:
                                return self.fetch_results(doc["url"])
                            except Exception:
                                continue
        return None


# Known Alkamelsystems series URLs (for reference)
ALKAMEL_SERIES = {
    "imsa": {
        "url": "https://imsa.results.alkamelcloud.com",
        "name": "IMSA WeatherTech SportsCar Championship",
        "public": True,
        "live_timing": "http://livetiming.alkamelsystems.com/imsa"
    },
    "fiawec": {
        "url": "https://fiawec.results.alkamelcloud.com",
        "name": "FIA World Endurance Championship",
        "public": False,  # Requires premium/backoffice access
        "live_timing": "http://livetiming.alkamelsystems.com/fiawec"
    },
    "elms": {
        "url": "https://elms.results.alkamelcloud.com",
        "name": "European Le Mans Series",
        "public": False,  # Requires premium/backoffice access
        "live_timing": "http://livetiming.alkamelsystems.com/elms"
    },
    "alms": {
        "url": "https://alms.results.alkamelcloud.com",
        "name": "Asian Le Mans Series",
        "public": False,  # Requires premium/backoffice access
        "live_timing": None  # Not confirmed
    }
}
