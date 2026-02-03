"""
GridView Historical Races API

GET /api/history/races
  Query params:
    - series: Filter by series code (f1, nascar_cup, etc.)
    - year: Filter by season year
    - track: Filter by track name (partial match)
    - country: Filter by country code
    - from: Races after this date (YYYY-MM-DD)
    - to: Races before this date (YYYY-MM-DD)
    - status: scheduled, completed, cancelled
    - limit: Max results (default 50, max 100)
    - offset: Pagination offset
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import urlparse, parse_qs

# Supabase setup
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")

# Lazy import supabase to handle missing dependency gracefully
_client = None

def get_client():
    global _client
    if _client is None:
        try:
            from supabase import create_client
            _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except ImportError:
            raise ImportError("supabase not installed. Run: pip install supabase")
    return _client


def query_races(
    series: str = None,
    year: int = None,
    track: str = None,
    country: str = None,
    from_date: str = None,
    to_date: str = None,
    status: str = None,
    limit: int = 50,
    offset: int = 0
) -> dict:
    """Query historical races with filters."""
    client = get_client()
    
    # Build query with joins
    query = client.table("races").select(
        """
        id,
        season,
        round,
        name,
        official_name,
        date,
        scheduled_laps,
        status,
        series:series_id (
            code,
            name,
            color
        ),
        track:track_id (
            name,
            country,
            city,
            track_type
        )
        """,
        count="exact"  # Get total count for pagination
    )
    
    # Apply filters
    if series:
        # Need to filter after join - Supabase doesn't support nested filters well
        # We'll filter in memory for now (TODO: use RPC for complex queries)
        pass
    
    if year:
        query = query.eq("season", year)
    
    if from_date:
        query = query.gte("date", from_date)
    
    if to_date:
        query = query.lte("date", to_date)
    
    if status:
        query = query.eq("status", status)
    
    # Order and paginate
    query = query.order("date", desc=True).range(offset, offset + limit - 1)
    
    response = query.execute()
    
    # Transform data
    races = []
    for race in response.data:
        # Filter by series code if specified (post-query filter)
        if series and race.get("series", {}).get("code") != series:
            continue
        
        # Filter by track/country if specified
        if track and track.lower() not in (race.get("track", {}).get("name") or "").lower():
            continue
        if country and race.get("track", {}).get("country") != country:
            continue
        
        races.append({
            "id": race["id"],
            "series": race.get("series"),
            "season": race["season"],
            "round": race["round"],
            "name": race["name"],
            "official_name": race.get("official_name"),
            "date": race["date"],
            "track": race.get("track"),
            "laps": race.get("scheduled_laps"),
            "status": race["status"]
        })
    
    return {
        "data": races[:limit],  # Apply limit after filtering
        "pagination": {
            "total": response.count or len(races),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < (response.count or len(races))
        }
    }


def get_race_with_results(race_id: str) -> dict:
    """Get a single race with full results."""
    client = get_client()
    
    # Get race info
    race_response = client.table("races").select(
        """
        *,
        series:series_id (code, name, color),
        track:track_id (name, country, city, length_km, track_type)
        """
    ).eq("id", race_id).single().execute()
    
    race = race_response.data
    if not race:
        return None
    
    # Get sessions and results
    sessions_response = client.table("sessions").select(
        """
        id,
        type,
        name,
        status,
        results (
            position,
            position_text,
            grid_position,
            positions_gained,
            points,
            laps_completed,
            time_text,
            status,
            status_detail,
            car_number,
            fastest_lap_rank,
            fastest_lap_time_ms,
            driver:driver_id (
                id,
                full_name,
                code,
                nationality
            ),
            team:team_id (
                id,
                name,
                primary_color
            )
        )
        """
    ).eq("race_id", race_id).order("type").execute()
    
    # Find race session and winner
    race_session = None
    for session in sessions_response.data:
        if session["type"] == "race":
            race_session = session
            break
    
    winner = None
    if race_session and race_session.get("results"):
        for result in race_session["results"]:
            if result["position"] == 1:
                winner = {
                    "driver": result["driver"],
                    "team": result["team"]
                }
                break
    
    return {
        "race": {
            "id": race["id"],
            "series": race.get("series"),
            "season": race["season"],
            "round": race["round"],
            "name": race["name"],
            "official_name": race.get("official_name"),
            "date": race["date"],
            "track": race.get("track"),
            "laps": race.get("scheduled_laps"),
            "status": race["status"]
        },
        "winner": winner,
        "sessions": sessions_response.data
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            path_parts = parsed.path.strip("/").split("/")
            
            # Check if requesting specific race: /api/history/races/{id}
            if len(path_parts) >= 4 and path_parts[3]:
                race_id = path_parts[3]
                result = get_race_with_results(race_id)
                if result:
                    self._send_json(result)
                else:
                    self._send_json({"error": "Race not found"}, 404)
                return
            
            # List races with filters
            params = {
                "series": query.get("series", [None])[0],
                "year": int(query.get("year", [0])[0]) if query.get("year") else None,
                "track": query.get("track", [None])[0],
                "country": query.get("country", [None])[0],
                "from_date": query.get("from", [None])[0],
                "to_date": query.get("to", [None])[0],
                "status": query.get("status", [None])[0],
                "limit": min(int(query.get("limit", [50])[0]), 100),
                "offset": int(query.get("offset", [0])[0])
            }
            
            result = query_races(**{k: v for k, v in params.items() if v is not None})
            self._send_json(result)
            
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
