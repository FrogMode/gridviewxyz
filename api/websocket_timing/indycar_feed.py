"""
IndyCar Live Feed Client

IndyCar uses Azure Blob Storage with JSON polling (not WebSockets).
This module provides a consistent interface for accessing IndyCar live timing data.

Endpoints (Azure Blob Storage):
- https://indycar.blob.core.windows.net/racecontrol/tsconfig.json - Session status
- https://indycar.blob.core.windows.net/racecontrol/timingscoring-ris.json - Live timing
- https://indycar.blob.core.windows.net/racecontrol/trackactivityleaderboardfeed.json - Leaderboard
- https://indycar.blob.core.windows.net/racecontrol/schedulefeed.json - Schedule
- https://indycar.blob.core.windows.net/racecontrol/driversfeed.json - Driver info
- https://indycar.blob.core.windows.net/ntt-data/INDYCAR_DATA_POLLING/data_polling_blob.json - NTT data

INDY NXT endpoints use _nxt suffix.

Session Status Values:
- GREEN: Green flag racing
- YELLOW: Caution/yellow flag
- RED: Red flag (stopped)
- WARM: Warm-up laps
- COLD: Cold track (not in session)
- CHECKERED: Race finished
"""

import json
import time
import threading
import urllib.request
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Session status colors
SESSION_STATUS = {
    "GREEN": "green",
    "YELLOW": "caution",
    "RED": "red",
    "WARM": "warm_up",
    "COLD": "cold",
    "CHECKERED": "checkered",
    "WHITE": "white_flag",
}


@dataclass
class IndyCarEntry:
    """Represents a driver/car entry in IndyCar timing."""
    position: int
    car_number: str
    driver_name: str
    team: str
    last_lap: str
    best_lap: str
    gap: str
    interval: str
    pit_stops: int
    status: str
    tire_compound: str
    laps_completed: int
    laps_led: int


@dataclass
class IndyCarSessionState:
    """Current state of an IndyCar session."""
    session_status: str
    session_type: str
    lap_number: int
    laps_remaining: int
    time_remaining: str
    elapsed_time: str
    event_name: str
    track_name: str
    entries: List[IndyCarEntry]
    timestamp: datetime


@dataclass
class IndyCarConfig:
    """Session configuration from tsconfig.json."""
    no_track_activity: bool
    timed_race: bool
    rain_delay: bool
    show_quick_insights: bool
    alt_tire_color: str
    doubleheader_race: bool


class IndyCarLiveFeed:
    """
    IndyCar Live Feed Client
    
    Polls IndyCar's Azure Blob Storage for live timing data.
    
    Usage:
        feed = IndyCarLiveFeed()
        
        # Check if session is active
        if feed.is_session_active():
            state = feed.fetch_timing_data()
            print(f"Lap {state.lap_number} - {state.session_status}")
        
        # Continuous polling
        feed.on_update = lambda state: print(f"Leader: {state.entries[0].driver_name}")
        feed.start_polling(interval=1.0)
    """
    
    BASE_URL = "https://indycar.blob.core.windows.net/racecontrol"
    NTT_URL = "https://indycar.blob.core.windows.net/ntt-data/INDYCAR_DATA_POLLING"
    
    ENDPOINTS = {
        "config": "tsconfig.json",
        "timing": "timingscoring-ris.json",
        "leaderboard": "trackactivityleaderboardfeed.json",
        "schedule": "schedulefeed.json",
        "drivers": "driversfeed.json",
        # INDY NXT
        "drivers_nxt": "driversfeed_nxt.json",
        "schedule_nxt": "schedulefeed_nxt.json",
        "leaderboard_nxt": "trackactivityleaderboardfeed_nxt.json",
    }
    
    def __init__(self, user_agent: str = "GridView/1.0", series: str = "indycar"):
        self.user_agent = user_agent
        self.series = series.lower()  # "indycar" or "indynxt"
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None
        self._last_state: Optional[IndyCarSessionState] = None
        self._config: Optional[IndyCarConfig] = None
        
        # Callbacks
        self.on_update: Optional[Callable[[IndyCarSessionState], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        self.on_status_change: Optional[Callable[[str, str], None]] = None
        self.on_position_change: Optional[Callable[[str, int, int], None]] = None  # driver, old, new
    
    def _fetch_json(self, endpoint: str, cache_bust: bool = True) -> Dict:
        """Fetch and parse JSON from Azure Blob."""
        url = f"{self.BASE_URL}/{endpoint}"
        
        if cache_bust:
            url += f"?{int(time.time())}"
        
        req = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        })
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    
    def fetch_config(self) -> IndyCarConfig:
        """
        Fetch session configuration.
        
        Returns:
            IndyCarConfig with session settings
        """
        data = self._fetch_json(self.ENDPOINTS["config"])
        
        self._config = IndyCarConfig(
            no_track_activity=data.get("no_track_activity", True),
            timed_race=data.get("timed_race", False),
            rain_delay=data.get("rain_delay", False),
            show_quick_insights=data.get("show_quick_insights", False),
            alt_tire_color=data.get("alt_tire_color", ""),
            doubleheader_race=data.get("doubleheader_race", False),
        )
        
        return self._config
    
    def is_session_active(self) -> bool:
        """
        Check if a session is currently active.
        
        Returns:
            True if track activity is happening
        """
        try:
            config = self.fetch_config()
            return not config.no_track_activity
        except Exception as e:
            logger.debug(f"Failed to check session status: {e}")
            return False
    
    def fetch_schedule(self) -> List[Dict]:
        """
        Fetch season schedule.
        
        Returns:
            List of race event dictionaries
        """
        endpoint = self.ENDPOINTS["schedule_nxt"] if self.series == "indynxt" else self.ENDPOINTS["schedule"]
        
        try:
            data = self._fetch_json(endpoint, cache_bust=False)
            return data.get("schedule", {}).get("race", [])
        except Exception as e:
            logger.error(f"Failed to fetch schedule: {e}")
            return []
    
    def fetch_drivers(self) -> List[Dict]:
        """
        Fetch driver information.
        
        Returns:
            List of driver dictionaries
        """
        endpoint = self.ENDPOINTS["drivers_nxt"] if self.series == "indynxt" else self.ENDPOINTS["drivers"]
        
        try:
            data = self._fetch_json(endpoint, cache_bust=False)
            return data.get("drivers", [])
        except Exception as e:
            logger.error(f"Failed to fetch drivers: {e}")
            return []
    
    def fetch_timing_data(self) -> Optional[IndyCarSessionState]:
        """
        Fetch current live timing data.
        
        Returns:
            IndyCarSessionState or None if no active session
        """
        try:
            data = self._fetch_json(self.ENDPOINTS["timing"])
            return self._parse_timing_data(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.debug("No timing data available")
            else:
                logger.error(f"HTTP error fetching timing: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching timing: {e}")
            return None
    
    def fetch_leaderboard(self) -> Optional[IndyCarSessionState]:
        """
        Fetch leaderboard data (alternative to timing).
        
        Returns:
            IndyCarSessionState or None
        """
        endpoint = (self.ENDPOINTS["leaderboard_nxt"] 
                   if self.series == "indynxt" 
                   else self.ENDPOINTS["leaderboard"])
        
        try:
            data = self._fetch_json(endpoint)
            return self._parse_leaderboard(data)
        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}")
            return None
    
    def _parse_timing_data(self, data: Dict) -> IndyCarSessionState:
        """Parse timing-ris.json format."""
        timing = data.get("timing_results", {})
        heartbeat = timing.get("heartbeat", {})
        
        entries = []
        for entry in timing.get("entries", []):
            entries.append(IndyCarEntry(
                position=entry.get("Position", 0),
                car_number=str(entry.get("Number", "")),
                driver_name=entry.get("Driver", ""),
                team=entry.get("Team", ""),
                last_lap=entry.get("LastLap", ""),
                best_lap=entry.get("BestLap", ""),
                gap=entry.get("Gap", ""),
                interval=entry.get("Interval", ""),
                pit_stops=entry.get("PitStops", 0),
                status=entry.get("Status", ""),
                tire_compound=entry.get("TireCompound", ""),
                laps_completed=entry.get("LapsComplete", 0),
                laps_led=entry.get("LapsLed", 0),
            ))
        
        # Sort by position
        entries.sort(key=lambda e: e.position if e.position > 0 else 999)
        
        status_raw = heartbeat.get("SessionStatus", "COLD")
        session_status = SESSION_STATUS.get(status_raw, status_raw.lower())
        
        return IndyCarSessionState(
            session_status=session_status,
            session_type=heartbeat.get("SessionType", ""),
            lap_number=heartbeat.get("LapNumber", 0),
            laps_remaining=heartbeat.get("LapsRemaining", 0),
            time_remaining=heartbeat.get("TimeRemaining", ""),
            elapsed_time=heartbeat.get("ElapsedTime", ""),
            event_name=heartbeat.get("EventName", ""),
            track_name=heartbeat.get("TrackName", ""),
            entries=entries,
            timestamp=datetime.now(),
        )
    
    def _parse_leaderboard(self, data: Dict) -> IndyCarSessionState:
        """Parse trackactivityleaderboardfeed.json format."""
        session = data.get("session", {})
        
        entries = []
        for entry in data.get("entries", []):
            entries.append(IndyCarEntry(
                position=entry.get("position", 0),
                car_number=str(entry.get("carNumber", "")),
                driver_name=entry.get("driverName", ""),
                team=entry.get("teamName", ""),
                last_lap=entry.get("lastLapTime", ""),
                best_lap=entry.get("bestLapTime", ""),
                gap=entry.get("gap", ""),
                interval=entry.get("interval", ""),
                pit_stops=entry.get("pitStops", 0),
                status=entry.get("status", ""),
                tire_compound=entry.get("tireCompound", ""),
                laps_completed=entry.get("lapsComplete", 0),
                laps_led=entry.get("lapsLed", 0),
            ))
        
        entries.sort(key=lambda e: e.position if e.position > 0 else 999)
        
        status_raw = session.get("status", "COLD")
        session_status = SESSION_STATUS.get(status_raw, status_raw.lower())
        
        return IndyCarSessionState(
            session_status=session_status,
            session_type=session.get("sessionType", ""),
            lap_number=session.get("lapNumber", 0),
            laps_remaining=session.get("lapsRemaining", 0),
            time_remaining=session.get("timeRemaining", ""),
            elapsed_time=session.get("elapsedTime", ""),
            event_name=session.get("eventName", ""),
            track_name=session.get("trackName", ""),
            entries=entries,
            timestamp=datetime.now(),
        )
    
    def fetch_ntt_data(self) -> Optional[Dict]:
        """
        Fetch NTT pit stop prediction data.
        
        Returns:
            Dictionary with NTT analytics or None
        """
        try:
            url = f"{self.NTT_URL}/data_polling_blob.json?{int(time.time())}"
            req = urllib.request.Request(url, headers={
                "User-Agent": self.user_agent,
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            logger.debug(f"No NTT data available: {e}")
            return None
    
    def start_polling(self, interval: float = 1.0):
        """
        Start continuous polling for live data.
        
        Args:
            interval: Seconds between polls (minimum 1.0 recommended)
        """
        if self._polling:
            logger.warning("Already polling")
            return
        
        self._polling = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            args=(interval,),
            daemon=True
        )
        self._poll_thread.start()
        logger.info(f"Started polling IndyCar timing every {interval}s")
    
    def _poll_loop(self, interval: float):
        """Internal polling loop."""
        while self._polling:
            try:
                # Check if session is active
                if not self.is_session_active():
                    time.sleep(interval * 5)  # Check less frequently when inactive
                    continue
                
                state = self.fetch_timing_data()
                
                if not state:
                    state = self.fetch_leaderboard()
                
                if state:
                    # Detect status change
                    if (self._last_state and 
                        state.session_status != self._last_state.session_status and
                        self.on_status_change):
                        self.on_status_change(
                            self._last_state.session_status,
                            state.session_status
                        )
                    
                    # Detect position changes
                    if self._last_state and self.on_position_change:
                        old_positions = {
                            e.car_number: e.position 
                            for e in self._last_state.entries
                        }
                        for entry in state.entries:
                            old_pos = old_positions.get(entry.car_number)
                            if old_pos and old_pos != entry.position:
                                self.on_position_change(
                                    entry.driver_name,
                                    old_pos,
                                    entry.position
                                )
                    
                    self._last_state = state
                    
                    if self.on_update:
                        self.on_update(state)
                        
            except Exception as e:
                logger.error(f"Polling error: {e}")
                if self.on_error:
                    self.on_error(e)
            
            time.sleep(interval)
    
    def stop_polling(self):
        """Stop continuous polling."""
        self._polling = False
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
            self._poll_thread = None
        logger.info("Stopped polling")
    
    @property
    def is_polling(self) -> bool:
        """Check if currently polling."""
        return self._polling
    
    @property
    def last_state(self) -> Optional[IndyCarSessionState]:
        """Get last fetched state."""
        return self._last_state


def get_live_standings() -> Optional[List[Dict]]:
    """
    Convenience function to get current IndyCar standings.
    
    Returns:
        List of driver standings or None if no active session
    """
    feed = IndyCarLiveFeed()
    
    if not feed.is_session_active():
        return None
    
    state = feed.fetch_timing_data()
    
    if not state:
        state = feed.fetch_leaderboard()
    
    if not state:
        return None
    
    return [
        {
            "position": e.position,
            "number": e.car_number,
            "driver": e.driver_name,
            "team": e.team,
            "gap": e.gap,
            "last_lap": e.last_lap,
            "best_lap": e.best_lap,
            "pit_stops": e.pit_stops,
            "status": e.status,
        }
        for e in state.entries
    ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    feed = IndyCarLiveFeed()
    
    # Check session status
    print(f"Session active: {feed.is_session_active()}")
    
    # Fetch config
    try:
        config = feed.fetch_config()
        print(f"\nConfig: no_track_activity={config.no_track_activity}, "
              f"rain_delay={config.rain_delay}")
    except Exception as e:
        print(f"Config error: {e}")
    
    # Fetch schedule
    schedule = feed.fetch_schedule()
    if schedule:
        print(f"\nNext 3 races:")
        from datetime import datetime
        now = datetime.now()
        upcoming = [r for r in schedule 
                   if r.get("green_flag", "9999") > now.isoformat()][:3]
        for race in upcoming:
            print(f"  - {race.get('name')} ({race.get('green_flag', 'TBD')[:10]})")
    
    # Try timing data
    state = feed.fetch_timing_data()
    if state:
        print(f"\n{state.event_name} - {state.session_status.upper()}")
        print(f"Lap {state.lap_number} | Time remaining: {state.time_remaining}")
        print(f"\nTop 5:")
        for e in state.entries[:5]:
            print(f"  {e.position:2d}. #{e.car_number:3s} {e.driver_name:25s} "
                  f"{e.gap:>8s} {e.last_lap}")
    else:
        print("\nNo active timing session")
