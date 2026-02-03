"""IMSA 2025 Schedule API - hardcoded from official IMSA.com data."""
from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime

# 2025 IMSA WeatherTech SportsCar Championship Schedule
SCHEDULE_2025 = [
    {
        "round": 0,
        "name": "Roar Before The Rolex 24",
        "venue": "Daytona International Speedway",
        "location": "Daytona Beach, FL",
        "date": "2025-01-17",
        "end_date": "2025-01-19",
        "duration": "Test Session",
        "track_length": "3.56 miles",
        "corners": 12,
        "is_test": True
    },
    {
        "round": 1,
        "name": "Rolex 24 At Daytona",
        "venue": "Daytona International Speedway",
        "location": "Daytona Beach, FL",
        "date": "2025-01-25",
        "end_date": "2025-01-26",
        "duration": "24 Hours",
        "track_length": "3.56 miles",
        "corners": 12,
        "is_endurance": True
    },
    {
        "round": 2,
        "name": "Mobil 1 Twelve Hours of Sebring",
        "venue": "Sebring International Raceway",
        "location": "Sebring, FL",
        "date": "2025-03-15",
        "end_date": "2025-03-15",
        "duration": "12 Hours",
        "track_length": "3.74 miles",
        "corners": 17,
        "is_endurance": True
    },
    {
        "round": 3,
        "name": "Acura Grand Prix of Long Beach",
        "venue": "Long Beach Street Circuit",
        "location": "Long Beach, CA",
        "date": "2025-04-12",
        "end_date": "2025-04-12",
        "duration": "100 Minutes",
        "track_length": "1.968 miles",
        "corners": 11
    },
    {
        "round": 4,
        "name": "TireRack.com Monterey SportsCar Championship",
        "venue": "WeatherTech Raceway Laguna Seca",
        "location": "Monterey, CA",
        "date": "2025-05-11",
        "end_date": "2025-05-11",
        "duration": "2 Hours 40 Minutes",
        "track_length": "2.238 miles",
        "corners": 11
    },
    {
        "round": 5,
        "name": "Detroit Grand Prix",
        "venue": "Detroit Street Circuit",
        "location": "Detroit, MI",
        "date": "2025-05-31",
        "end_date": "2025-05-31",
        "duration": "100 Minutes",
        "track_length": "1.7 miles",
        "corners": 9
    },
    {
        "round": 6,
        "name": "Sahlen's Six Hours of The Glen",
        "venue": "Watkins Glen International",
        "location": "Watkins Glen, NY",
        "date": "2025-06-22",
        "end_date": "2025-06-22",
        "duration": "6 Hours",
        "track_length": "3.4 miles",
        "corners": 11,
        "is_endurance": True
    },
    {
        "round": 7,
        "name": "Chevrolet Grand Prix",
        "venue": "Canadian Tire Motorsport Park",
        "location": "Bowmanville, ON, Canada",
        "date": "2025-07-13",
        "end_date": "2025-07-13",
        "duration": "2 Hours 40 Minutes",
        "track_length": "2.459 miles",
        "corners": 10
    },
    {
        "round": 8,
        "name": "Motul SportsCar Grand Prix",
        "venue": "Road America",
        "location": "Elkhart Lake, WI",
        "date": "2025-08-03",
        "end_date": "2025-08-03",
        "duration": "2 Hours 40 Minutes",
        "track_length": "4.0 miles",
        "corners": 14
    },
    {
        "round": 9,
        "name": "Michelin GT Challenge at VIR",
        "venue": "VIRginia International Raceway",
        "location": "Alton, VA",
        "date": "2025-08-24",
        "end_date": "2025-08-24",
        "duration": "2 Hours 40 Minutes",
        "track_length": "3.27 miles",
        "corners": 18
    },
    {
        "round": 10,
        "name": "TireRack.com Battle on the Bricks",
        "venue": "Indianapolis Motor Speedway",
        "location": "Indianapolis, IN",
        "date": "2025-09-21",
        "end_date": "2025-09-21",
        "duration": "6 Hours",
        "track_length": "2.439 miles",
        "corners": 14,
        "is_endurance": True
    },
    {
        "round": 11,
        "name": "Petit Le Mans",
        "venue": "Michelin Raceway Road Atlanta",
        "location": "Braselton, GA",
        "date": "2025-10-11",
        "end_date": "2025-10-11",
        "duration": "10 Hours",
        "track_length": "2.54 miles",
        "corners": 12,
        "is_endurance": True
    }
]

def get_schedule(upcoming_only: bool = False, include_tests: bool = False) -> list:
    """Get schedule, optionally filtering to upcoming events."""
    events = SCHEDULE_2025.copy()
    
    if not include_tests:
        events = [e for e in events if not e.get("is_test")]
    
    if upcoming_only:
        today = datetime.now().strftime("%Y-%m-%d")
        events = [e for e in events if e["date"] >= today]
    
    return events

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            upcoming = 'upcoming' in query
            include_tests = 'tests' in query
            
            events = get_schedule(upcoming_only=upcoming, include_tests=include_tests)
            
            response = {
                "series": "IMSA WeatherTech SportsCar Championship",
                "season": 2025,
                "events": events,
                "count": len(events)
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
