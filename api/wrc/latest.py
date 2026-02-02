"""WRC Latest Results API endpoint."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
from html.parser import HTMLParser

class WRCResultsParser(HTMLParser):
    """Simple parser to extract results from ewrc-results.com."""
    def __init__(self):
        super().__init__()
        self.results = []
        self.in_table = False
        self.current_row = []
        self.in_cell = False
        
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            attrs_dict = dict(attrs)
            if "final-results" in attrs_dict.get("class", ""):
                self.in_table = True
        elif tag == "tr" and self.in_table:
            self.current_row = []
        elif tag == "td" and self.in_table:
            self.in_cell = True
            
    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        elif tag == "tr" and self.current_row:
            if len(self.current_row) >= 3:
                self.results.append({
                    "position": self.current_row[0].strip(),
                    "driver": self.current_row[1].strip() if len(self.current_row) > 1 else "",
                    "time": self.current_row[-1].strip() if self.current_row else "",
                })
            self.current_row = []
        elif tag == "td":
            self.in_cell = False
            
    def handle_data(self, data):
        if self.in_cell:
            self.current_row.append(data)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # For now, return static sample data
            # Full scraping would need more robust parsing
            sample_results = {
                "series": "wrc",
                "event": {
                    "name": "Rally Monte Carlo 2025",
                    "date": "2025-01-23",
                    "location": "Monte Carlo, Monaco"
                },
                "results": [
                    {"position": 1, "driver": "Sébastien Ogier", "team": "Toyota", "time": "3:04:23.5"},
                    {"position": 2, "driver": "Thierry Neuville", "team": "Hyundai", "time": "+18.7"},
                    {"position": 3, "driver": "Elfyn Evans", "team": "Toyota", "time": "+42.3"},
                    {"position": 4, "driver": "Ott Tänak", "team": "Hyundai", "time": "+1:12.8"},
                    {"position": 5, "driver": "Adrien Fourmaux", "team": "M-Sport Ford", "time": "+2:05.1"},
                ],
                "note": "Sample data - full scraper integration pending"
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(sample_results, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
