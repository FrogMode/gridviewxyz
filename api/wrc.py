from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Sample WRC data
        response = {
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
            "note": "Sample data - live scraper coming soon"
        }
        self.wfile.write(json.dumps(response, indent=2).encode())
        return
