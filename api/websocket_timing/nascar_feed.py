"""
NASCAR Live Feed Client

NASCAR uses JSON polling, not WebSockets.
This module provides a consistent interface for accessing NASCAR live timing data.

Endpoints:
- https://cf.nascar.com/live/feeds/series_{id}/{race_id}/live_feed.json
- https://cf.nascar.com/cacher/{year}/race_list_basic.json

Series IDs:
- 1 = NASCAR Cup Series
- 2 = NASCAR Xfinity Series  
- 3 = NASCAR Craftsman Truck Series

Data includes:
- Real-time positions, lap times, speeds
- Pit stop information
- Flag status (green/yellow/red/white/checkered)
- Stage information
- Gap/interval data
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


# Flag state mappings (from reverse engineering)
FLAG_STATES = {
    1: "green",
    2: "yellow",
    3: "red",
    4: "checkered",
    5: "white",
    6: "warm_up",
    8: "pre_race",
    9: "caution",  # Also yellow
}


@dataclass
class NASCARVehicle:
    """Represents a vehicle/driver in NASCAR timing."""
    position: int
    car_number: str
    driver_name: str
    manufacturer: str
    laps_completed: int
    laps_led: int
    last_lap_time: float
    last_lap_speed: float
    best_lap_time: float
    best_lap_speed: float
    status: int  # 1=running, 3=out
    delta: float
    pit_stops: int
    is_on_track: bool
    average_speed: float
    sponsor_name: str


@dataclass  
class NASCARRaceState:
    """Current state of a NASCAR race."""
    race_id: int
    race_name: str
    track_name: str
    track_length: float
    series_id: int
    lap_number: int
    laps_in_race: int
    laps_to_go: int
    flag_state: str
    flag_state_code: int
    elapsed_time: float
    caution_laps: int
    caution_segments: int
    lead_changes: int
    leaders: int
    stage: Dict[str, Any]
    vehicles: List[NASCARVehicle]
    timestamp: datetime


class NASCARLiveFeed:
    """
    NASCAR Live Feed Client
    
    Polls NASCAR's JSON feed for live timing data.
    
    Usage:
        feed = NASCARLiveFeed()
        
        # One-time fetch
        state = feed.fetch_live_data(series_id=1, race_id=4792)
        
        # Continuous polling
        feed.on_update = lambda state: print(f"Lap {state.lap_number}")
        feed.start_polling(series_id=1, race_id=4792, interval=2.0)
    """
    
    BASE_URL = "https://cf.nascar.com"
    
    # Series configuration
    SERIES = {
        1: {"name": "NASCAR Cup Series", "code": "cup"},
        2: {"name": "NASCAR Xfinity Series", "code": "xfinity"},
        3: {"name": "NASCAR Craftsman Truck Series", "code": "truck"},
    }
    
    def __init__(self, user_agent: str = "GridView/1.0"):
        self.user_agent = user_agent
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None
        self._last_state: Optional[NASCARRaceState] = None
        
        # Callbacks
        self.on_update: Optional[Callable[[NASCARRaceState], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        self.on_flag_change: Optional[Callable[[str, str], None]] = None  # old_flag, new_flag
        self.on_lead_change: Optional[Callable[[str, str], None]] = None  # old_leader, new_leader
    
    def _fetch_json(self, url: str) -> Dict:
        """Fetch and parse JSON from URL."""
        req = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        })
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    
    def get_schedule(self, year: int = None, series_id: int = 1) -> List[Dict]:
        """
        Get race schedule for a series.
        
        Args:
            year: Season year (defaults to current)
            series_id: Series ID (1=Cup, 2=Xfinity, 3=Truck)
            
        Returns:
            List of race dictionaries
        """
        if year is None:
            year = datetime.now().year
        
        url = f"{self.BASE_URL}/cacher/{year}/{series_id}/race_list_basic.json"
        
        try:
            data = self._fetch_json(url)
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Failed to fetch schedule: {e}")
            return []
    
    def get_current_race_id(self, series_id: int = 1) -> Optional[int]:
        """
        Get the current or most recent race ID.
        
        Returns:
            Race ID or None if not found
        """
        schedule = self.get_schedule(series_id=series_id)
        now = datetime.now()
        
        # Find current or most recent race
        for race in reversed(schedule):
            race_date_str = race.get("race_date", "")
            if race_date_str:
                try:
                    race_date = datetime.fromisoformat(race_date_str.replace('Z', '+00:00'))
                    if race_date.replace(tzinfo=None) <= now:
                        return race.get("race_id")
                except:
                    pass
        
        return schedule[-1].get("race_id") if schedule else None
    
    def fetch_live_data(self, series_id: int, race_id: int) -> Optional[NASCARRaceState]:
        """
        Fetch current live timing data.
        
        Args:
            series_id: Series ID (1=Cup, 2=Xfinity, 3=Truck)
            race_id: Race ID from schedule
            
        Returns:
            NASCARRaceState or None if unavailable
        """
        url = f"{self.BASE_URL}/live/feeds/series_{series_id}/{race_id}/live_feed.json"
        
        try:
            data = self._fetch_json(url)
            return self._parse_race_state(data)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.debug(f"No live feed available for race {race_id}")
            else:
                logger.error(f"HTTP error fetching live feed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching live feed: {e}")
            return None
    
    def _parse_race_state(self, data: Dict) -> NASCARRaceState:
        """Parse raw JSON into NASCARRaceState."""
        vehicles = []
        
        for v in data.get("vehicles", []):
            driver_info = v.get("driver", {})
            
            vehicle = NASCARVehicle(
                position=v.get("running_position", 0),
                car_number=v.get("vehicle_number", ""),
                driver_name=driver_info.get("full_name", "Unknown"),
                manufacturer=v.get("vehicle_manufacturer", ""),
                laps_completed=v.get("laps_completed", 0),
                laps_led=sum(
                    (led.get("end_lap", 0) - led.get("start_lap", 0) + 1)
                    for led in v.get("laps_led", [])
                ),
                last_lap_time=v.get("last_lap_time", 0),
                last_lap_speed=v.get("last_lap_speed", 0),
                best_lap_time=v.get("best_lap_time", 0),
                best_lap_speed=v.get("best_lap_speed", 0),
                status=v.get("status", 0),
                delta=v.get("delta", 0),
                pit_stops=len(v.get("pit_stops", [])) - 1,  # First entry is empty
                is_on_track=v.get("is_on_track", False),
                average_speed=v.get("average_speed", 0),
                sponsor_name=v.get("sponsor_name", ""),
            )
            vehicles.append(vehicle)
        
        # Sort by position
        vehicles.sort(key=lambda v: v.position)
        
        flag_code = data.get("flag_state", 0)
        flag_state = FLAG_STATES.get(flag_code, f"unknown_{flag_code}")
        
        return NASCARRaceState(
            race_id=data.get("race_id", 0),
            race_name=data.get("run_name", ""),
            track_name=data.get("track_name", ""),
            track_length=data.get("track_length", 0),
            series_id=data.get("series_id", 0),
            lap_number=data.get("lap_number", 0),
            laps_in_race=data.get("laps_in_race", 0),
            laps_to_go=data.get("laps_to_go", 0),
            flag_state=flag_state,
            flag_state_code=flag_code,
            elapsed_time=data.get("elapsed_time", 0),
            caution_laps=data.get("number_of_caution_laps", 0),
            caution_segments=data.get("number_of_caution_segments", 0),
            lead_changes=data.get("number_of_lead_changes", 0),
            leaders=data.get("number_of_leaders", 0),
            stage=data.get("stage", {}),
            vehicles=vehicles,
            timestamp=datetime.now(),
        )
    
    def start_polling(self, series_id: int, race_id: int, interval: float = 2.0):
        """
        Start continuous polling for live data.
        
        Args:
            series_id: Series ID
            race_id: Race ID  
            interval: Seconds between polls
        """
        if self._polling:
            logger.warning("Already polling")
            return
        
        self._polling = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            args=(series_id, race_id, interval),
            daemon=True
        )
        self._poll_thread.start()
        logger.info(f"Started polling race {race_id} every {interval}s")
    
    def _poll_loop(self, series_id: int, race_id: int, interval: float):
        """Internal polling loop."""
        while self._polling:
            try:
                state = self.fetch_live_data(series_id, race_id)
                
                if state:
                    # Detect changes
                    if self._last_state:
                        # Flag change
                        if (state.flag_state != self._last_state.flag_state and 
                            self.on_flag_change):
                            self.on_flag_change(self._last_state.flag_state, state.flag_state)
                        
                        # Lead change
                        if state.vehicles and self._last_state.vehicles:
                            old_leader = self._last_state.vehicles[0].car_number
                            new_leader = state.vehicles[0].car_number
                            if old_leader != new_leader and self.on_lead_change:
                                self.on_lead_change(old_leader, new_leader)
                    
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
    def last_state(self) -> Optional[NASCARRaceState]:
        """Get last fetched state."""
        return self._last_state


def get_live_standings(series_id: int = 1) -> Optional[List[Dict]]:
    """
    Convenience function to get current standings.
    
    Returns:
        List of driver standings or None
    """
    feed = NASCARLiveFeed()
    race_id = feed.get_current_race_id(series_id)
    
    if not race_id:
        return None
    
    state = feed.fetch_live_data(series_id, race_id)
    
    if not state:
        return None
    
    return [
        {
            "position": v.position,
            "number": v.car_number,
            "driver": v.driver_name,
            "manufacturer": v.manufacturer,
            "laps": v.laps_completed,
            "led": v.laps_led,
            "last_lap": v.last_lap_time,
            "best_lap": v.best_lap_time,
            "status": "running" if v.status == 1 else "out",
        }
        for v in state.vehicles
    ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    feed = NASCARLiveFeed()
    
    # Get current race
    race_id = feed.get_current_race_id(series_id=1)
    print(f"Current race ID: {race_id}")
    
    if race_id:
        # Fetch live data
        state = feed.fetch_live_data(series_id=1, race_id=race_id)
        
        if state:
            print(f"\n{state.race_name} at {state.track_name}")
            print(f"Lap {state.lap_number}/{state.laps_in_race} - {state.flag_state.upper()}")
            print(f"Lead changes: {state.lead_changes} | Caution laps: {state.caution_laps}")
            print(f"\nTop 10:")
            for v in state.vehicles[:10]:
                print(f"  {v.position:2d}. #{v.car_number:3s} {v.driver_name:25s} "
                      f"{v.laps_completed:3d} laps  {v.last_lap_speed:.1f} mph")
        else:
            print("No live feed available")
