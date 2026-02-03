"""IndyCar API - provides schedule and links to official IndyCar data.

IndyCar doesn't have a publicly documented API. This endpoint provides:
- Static schedule data (updated periodically)
- Links to official IndyCar pages for results and standings

Future improvements could include scraping indycar.com/schedule or
using their leaderboard websocket during live sessions.
"""
from http.server import BaseHTTPRequestHandler
import json
from datetime import datetime

# 2025 IndyCar Schedule (manually maintained)
# Source: https://www.indycar.com/Schedule
INDYCAR_2025_SCHEDULE = [
    {
        "round": 1,
        "name": "Firestone Grand Prix of St. Petersburg",
        "track": "Streets of St. Petersburg",
        "location": "St. Petersburg, Florida",
        "date": "2025-03-02",
        "type": "street",
        "tv": "NBC",
        "links": {
            "tickets": "https://gpstpete.com/buy-tickets/ticket-options",
            "event": "https://www.indycar.com/Schedule/2025/St-Petersburg"
        }
    },
    {
        "round": 2,
        "name": "Good Ranchers 250",
        "track": "Phoenix Raceway",
        "location": "Avondale, Arizona",
        "date": "2025-03-08",
        "type": "oval",
        "tv": "NBC",
        "links": {
            "tickets": "https://www.phoenixraceway.com/",
            "event": "https://www.indycar.com/Schedule/2025/Phoenix"
        }
    },
    {
        "round": 3,
        "name": "Java House Grand Prix of Arlington",
        "track": "Streets of Arlington",
        "location": "Arlington, Texas",
        "date": "2025-03-15",
        "type": "street",
        "tv": "NBC",
        "links": {
            "tickets": "https://www.gparlington.com/",
            "event": "https://www.indycar.com/Schedule/2025/Arlington"
        }
    },
    {
        "round": 4,
        "name": "Acura Grand Prix of Long Beach",
        "track": "Streets of Long Beach",
        "location": "Long Beach, California",
        "date": "2025-04-13",
        "type": "street",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Long-Beach"
        }
    },
    {
        "round": 5,
        "name": "Honda Indy Grand Prix of Alabama",
        "track": "Barber Motorsports Park",
        "location": "Birmingham, Alabama",
        "date": "2025-04-27",
        "type": "road",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Alabama"
        }
    },
    {
        "round": 6,
        "name": "Children's of Alabama Indy Grand Prix",
        "track": "Barber Motorsports Park",
        "location": "Birmingham, Alabama",
        "date": "2025-04-28",
        "type": "road",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Alabama"
        }
    },
    {
        "round": 7,
        "name": "Indy 500 Open Test",
        "track": "Indianapolis Motor Speedway",
        "location": "Indianapolis, Indiana",
        "date": "2025-05-01",
        "type": "test",
        "tv": "Peacock",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025"
        }
    },
    {
        "round": 8,
        "name": "GMR Grand Prix",
        "track": "Indianapolis Motor Speedway Road Course",
        "location": "Indianapolis, Indiana",
        "date": "2025-05-10",
        "type": "road",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Indianapolis-GP"
        }
    },
    {
        "round": 9,
        "name": "109th Indianapolis 500",
        "track": "Indianapolis Motor Speedway",
        "location": "Indianapolis, Indiana",
        "date": "2025-05-25",
        "type": "oval",
        "tv": "NBC",
        "featured": True,
        "links": {
            "tickets": "https://www.indianapolismotorspeedway.com/",
            "event": "https://www.indycar.com/Schedule/2025/Indy500"
        }
    },
    {
        "round": 10,
        "name": "Chevrolet Detroit Grand Prix",
        "track": "Streets of Detroit",
        "location": "Detroit, Michigan",
        "date": "2025-06-01",
        "type": "street",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Detroit"
        }
    },
    {
        "round": 11,
        "name": "Road America",
        "track": "Road America",
        "location": "Elkhart Lake, Wisconsin",
        "date": "2025-06-22",
        "type": "road",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Road-America"
        }
    },
    {
        "round": 12,
        "name": "Honda Indy 200 at Mid-Ohio",
        "track": "Mid-Ohio Sports Car Course",
        "location": "Lexington, Ohio",
        "date": "2025-07-06",
        "type": "road",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Mid-Ohio"
        }
    },
    {
        "round": 13,
        "name": "Hy-Vee INDYCAR Race Weekend - Race 1",
        "track": "Iowa Speedway",
        "location": "Newton, Iowa",
        "date": "2025-07-12",
        "type": "oval",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Iowa"
        }
    },
    {
        "round": 14,
        "name": "Hy-Vee INDYCAR Race Weekend - Race 2",
        "track": "Iowa Speedway",
        "location": "Newton, Iowa",
        "date": "2025-07-13",
        "type": "oval",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Iowa"
        }
    },
    {
        "round": 15,
        "name": "Honda Indy Toronto",
        "track": "Streets of Toronto",
        "location": "Toronto, Ontario, Canada",
        "date": "2025-07-20",
        "type": "street",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Toronto"
        }
    },
    {
        "round": 16,
        "name": "Gallagher Grand Prix",
        "track": "Indianapolis Motor Speedway Road Course",
        "location": "Indianapolis, Indiana",
        "date": "2025-08-02",
        "type": "road",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Indianapolis-GP-2"
        }
    },
    {
        "round": 17,
        "name": "Bommarito Automotive Group 500",
        "track": "World Wide Technology Raceway",
        "location": "Madison, Illinois",
        "date": "2025-08-24",
        "type": "oval",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Gateway"
        }
    },
    {
        "round": 18,
        "name": "Grand Prix of Portland",
        "track": "Portland International Raceway",
        "location": "Portland, Oregon",
        "date": "2025-08-31",
        "type": "road",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Portland"
        }
    },
    {
        "round": 19,
        "name": "Firestone Grand Prix of Monterey",
        "track": "WeatherTech Raceway Laguna Seca",
        "location": "Monterey, California",
        "date": "2025-09-07",
        "type": "road",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Laguna-Seca"
        }
    },
    {
        "round": 20,
        "name": "Big Machine Music City Grand Prix",
        "track": "Nashville Superspeedway",
        "location": "Nashville, Tennessee",
        "date": "2025-09-14",
        "type": "oval",
        "tv": "NBC",
        "links": {
            "event": "https://www.indycar.com/Schedule/2025/Nashville"
        }
    }
]


def get_schedule(year: int = None) -> list:
    """Get IndyCar schedule for a year."""
    if year is None:
        year = datetime.now().year
    
    if year == 2025:
        return INDYCAR_2025_SCHEDULE
    
    # For other years, return empty with a note
    return []


def get_upcoming_races(limit: int = 5) -> list:
    """Get upcoming IndyCar races."""
    today = datetime.now().strftime("%Y-%m-%d")
    schedule = get_schedule()
    
    upcoming = []
    for race in schedule:
        if race.get("date") and race["date"] >= today:
            if race.get("type") != "test":  # Skip test sessions
                upcoming.append(race)
                if len(upcoming) >= limit:
                    break
    
    return upcoming


def get_featured_event() -> dict:
    """Get the next featured event (Indianapolis 500)."""
    today = datetime.now().strftime("%Y-%m-%d")
    schedule = get_schedule()
    
    for race in schedule:
        if race.get("featured") and race.get("date", "") >= today:
            return race
    
    return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            year = query.get('year', [None])[0]
            if year:
                year = int(year)
            
            # Get upcoming races
            if 'upcoming' in query:
                limit = int(query.get('limit', [5])[0])
                races = get_upcoming_races(limit=limit)
                self._send_json({
                    "series": "IndyCar Series",
                    "upcoming": races,
                    "note": "Results available at indycar.com/Results"
                })
                return
            
            # Get featured event
            if 'featured' in query:
                event = get_featured_event()
                self._send_json({
                    "series": "IndyCar Series",
                    "featured": event
                })
                return
            
            # Default: return full schedule
            schedule = get_schedule(year)
            
            if not schedule and year != 2025:
                self._send_json({
                    "series": "IndyCar Series",
                    "season": year or datetime.now().year,
                    "events": [],
                    "note": f"Schedule for {year} not available. Only 2025 is currently supported.",
                    "official_schedule": "https://www.indycar.com/Schedule"
                })
                return
            
            response = {
                "series": "IndyCar Series",
                "season": year or datetime.now().year,
                "events": schedule,
                "links": {
                    "results": "https://www.indycar.com/Results",
                    "standings": "https://www.indycar.com/Standings",
                    "schedule": "https://www.indycar.com/Schedule"
                }
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
        self.send_header('Cache-Control', 'public, max-age=3600')  # 1 hour cache for static data
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
