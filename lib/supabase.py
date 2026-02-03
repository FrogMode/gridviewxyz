"""
Supabase client setup for GridView historical database.

Usage:
    from lib.supabase import get_client, get_admin_client
    
    # For API routes (public, RLS-protected)
    client = get_client()
    
    # For backfill scripts (service role, bypasses RLS)
    admin = get_admin_client()
"""

import os
from functools import lru_cache
from typing import Optional

# Try to import supabase, provide helpful error if missing
try:
    from supabase import create_client, Client
except ImportError:
    raise ImportError(
        "supabase-py not installed. Run: pip install supabase"
    )


def _get_env(key: str, required: bool = True) -> Optional[str]:
    """Get environment variable with helpful error."""
    value = os.environ.get(key)
    if required and not value:
        raise EnvironmentError(
            f"Missing required environment variable: {key}\n"
            f"Add it to .env.local or set it in your environment."
        )
    return value


@lru_cache(maxsize=1)
def get_client() -> Client:
    """
    Get Supabase client for API routes.
    
    Uses the anon key - respects Row Level Security.
    Safe for client-side or public API routes.
    """
    url = _get_env("SUPABASE_URL")
    key = _get_env("SUPABASE_ANON_KEY")
    return create_client(url, key)


@lru_cache(maxsize=1)  
def get_admin_client() -> Client:
    """
    Get Supabase admin client for backfill/maintenance scripts.
    
    Uses the service role key - BYPASSES Row Level Security.
    Only use for server-side scripts, never expose to client.
    """
    url = _get_env("SUPABASE_URL")
    key = _get_env("SUPABASE_SERVICE_KEY")
    return create_client(url, key)


# Convenience function for common queries
def query_races(
    series: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Query races with optional filters.
    
    Args:
        series: Filter by series code (e.g., 'f1', 'nascar_cup')
        year: Filter by season year
        limit: Max results
        offset: Pagination offset
    
    Returns:
        List of race records with series, track, and winner info
    """
    client = get_client()
    
    query = client.table("races").select(
        """
        *,
        series:series_id (code, name, color),
        track:track_id (name, country, city),
        sessions!inner (
            type,
            results (
                position,
                driver:driver_id (full_name, code),
                team:team_id (name)
            )
        )
        """
    ).order("date", desc=True).range(offset, offset + limit - 1)
    
    if series:
        # Need to filter on joined table
        query = query.eq("series.code", series)
    
    if year:
        query = query.eq("season", year)
    
    response = query.execute()
    return response.data


def query_driver_stats(driver_id: str, series: Optional[str] = None):
    """
    Get career statistics for a driver.
    
    Args:
        driver_id: UUID of the driver
        series: Optional series code to filter stats
    
    Returns:
        Dict with career stats and season-by-season breakdown
    """
    client = get_client()
    
    # Get driver info
    driver = client.table("drivers").select("*").eq("id", driver_id).single().execute()
    
    # Get all results
    results_query = client.table("results").select(
        """
        *,
        session:session_id (
            type,
            race:race_id (
                season,
                round,
                name,
                series:series_id (code, name)
            )
        )
        """
    ).eq("driver_id", driver_id)
    
    if series:
        # This requires a more complex query through the joins
        pass  # TODO: Add series filter
    
    results = results_query.execute()
    
    # Calculate stats
    races = [r for r in results.data if r.get("session", {}).get("type") == "race"]
    
    stats = {
        "driver": driver.data,
        "career_stats": {
            "races_entered": len(races),
            "wins": sum(1 for r in races if r.get("position") == 1),
            "podiums": sum(1 for r in races if r.get("position") and r["position"] <= 3),
            "poles": sum(1 for r in races if r.get("grid_position") == 1),
            "points": sum(r.get("points", 0) for r in races),
            "dnfs": sum(1 for r in races if r.get("status") == "dnf"),
        }
    }
    
    return stats


def insert_race_result(
    session_id: str,
    driver_id: str,
    team_id: Optional[str],
    position: int,
    **kwargs
):
    """
    Insert a race result. Uses admin client (service role).
    
    Args:
        session_id: UUID of the session
        driver_id: UUID of the driver
        team_id: UUID of the team (optional)
        position: Finishing position
        **kwargs: Additional result fields (points, time_ms, status, etc.)
    """
    admin = get_admin_client()
    
    data = {
        "session_id": session_id,
        "driver_id": driver_id,
        "team_id": team_id,
        "position": position,
        **kwargs
    }
    
    response = admin.table("results").upsert(
        data,
        on_conflict="session_id,driver_id"
    ).execute()
    
    return response.data


# Example usage in API routes
if __name__ == "__main__":
    # Test connection
    try:
        client = get_client()
        result = client.table("series").select("*").execute()
        print(f"✅ Connected! Found {len(result.data)} series.")
        for s in result.data:
            print(f"  - {s['code']}: {s['name']}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
