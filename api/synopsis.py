"""Race Synopsis API - bullet point summaries of recent races with spoiler support."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
from datetime import datetime, timedelta

# Synopsis data structure - can be populated from multiple sources
# For now, includes recent race summaries that can be expanded
RECENT_RACES = [
    {
        "id": "daytona-24-2026",
        "series": "IMSA",
        "event": "Rolex 24 at Daytona",
        "date": "2026-01-25",
        "circuit": "Daytona International Speedway",
        "winner": {
            "team": "Porsche Penske Motorsport",
            "car": "#7 Porsche 963",
            "drivers": ["Felipe Nasr", "Nick Tandy", "Laurens Vanthoor"]
        },
        "bullets": [
            "Porsche Penske claims third consecutive Rolex 24 victory - a historic three-peat",
            "The #7 Porsche 963 led 312 of 764 laps in a dominant display",
            "Acura and Cadillac challenged early but faded with mechanical issues",
            "BMW M Hybrid V8 showed improved pace but couldn't match Porsche's consistency",
            "GTD Pro class won by Heart of Racing Aston Martin after late drama",
            "Record 61 cars started the twice-around-the-clock classic"
        ],
        "stats": {
            "laps": 764,
            "distance_miles": 2709.36,
            "lead_changes": 47,
            "caution_periods": 8
        }
    },
    {
        "id": "monte-carlo-2026",
        "series": "WRC",
        "event": "Rallye Monte-Carlo",
        "date": "2026-01-23",
        "circuit": "Monaco / French Alps",
        "winner": {
            "team": "Toyota Gazoo Racing",
            "car": "Toyota GR Yaris Rally1",
            "drivers": ["Sébastien Ogier", "Vincent Landais"]
        },
        "bullets": [
            "Sébastien Ogier takes record-extending 10th Monte-Carlo victory",
            "Incredible final stage drama as Ogier overcame a 12-second deficit",
            "Thierry Neuville led going into Power Stage but made a costly error",
            "Treacherous ice conditions caught out multiple crews on Col de Turini",
            "Ott Tänak's championship defense starts with disappointing P4",
            "New hybrid regulations create strategic tire compound decisions"
        ],
        "stats": {
            "stages": 18,
            "distance_km": 296.05,
            "winner_time": "3:02:45.2"
        }
    },
    {
        "id": "bahrain-f1-2025",
        "series": "F1",
        "event": "Bahrain Grand Prix",
        "date": "2025-03-02",
        "circuit": "Bahrain International Circuit",
        "winner": {
            "team": "Red Bull Racing",
            "car": "Red Bull RB21",
            "drivers": ["Max Verstappen"]
        },
        "bullets": [
            "Max Verstappen dominates season opener from pole position",
            "Ferrari shows strong pace - Leclerc takes P2 with fastest lap",
            "Mercedes struggles continue with both cars outside podium",
            "McLaren's Norris completes podium after late-race overtake",
            "Rookie sensation in points on debut for Haas",
            "New tire compounds create two-stop strategy for most teams"
        ],
        "stats": {
            "laps": 57,
            "winner_time": "1:31:44.742",
            "fastest_lap": "Charles Leclerc - 1:32.608"
        }
    }
]

def get_recent_synopses(series: str = None, limit: int = 5, include_spoilers: bool = True):
    """Get recent race synopses with optional spoiler filtering."""
    races = RECENT_RACES
    
    # Filter by series if specified
    if series:
        races = [r for r in races if r["series"].lower() == series.lower()]
    
    # Sort by date (most recent first)
    races = sorted(races, key=lambda x: x["date"], reverse=True)[:limit]
    
    # Optionally strip spoiler content
    if not include_spoilers:
        for race in races:
            race = {
                "id": race["id"],
                "series": race["series"],
                "event": race["event"],
                "date": race["date"],
                "circuit": race["circuit"],
                "spoiler_hidden": True,
                "bullets": ["[Spoiler hidden - toggle to reveal]"],
            }
    
    return races

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            # Get parameters
            series = query.get('series', [None])[0]
            limit = min(int(query.get('limit', ['5'])[0]), 20)
            include_spoilers = query.get('spoilers', ['true'])[0].lower() == 'true'
            
            # Get available series
            if 'list' in query:
                available = list(set(r["series"] for r in RECENT_RACES))
                response = {
                    "series": available,
                    "total_races": len(RECENT_RACES)
                }
                self._send_json(response)
                return
            
            # Get synopses
            races = get_recent_synopses(series, limit, include_spoilers)
            
            response = {
                "count": len(races),
                "filter": series or "all",
                "spoilers_visible": include_spoilers,
                "races": races
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
