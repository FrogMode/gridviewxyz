"""
GridView Live Race Predictions API

Real-time win probability estimates and strategic insights during live races.
Supports F1 (via OpenF1 API) and IndyCar (via Azure Blob Storage).

Endpoints:
    GET /api/predictions?series=f1       - F1 race predictions
    GET /api/predictions?series=indycar  - IndyCar race predictions
    GET /api/predictions?series=f1&top=5 - Top 5 only
"""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import time
import math

# =============================================================================
# Configuration & Constants
# =============================================================================

OPENF1_BASE = "https://api.openf1.org/v1"
INDYCAR_BLOB_BASE = "https://indycar.blob.core.windows.net/racecontrol"

# Track configurations (overtake difficulty 0.0=easy, 1.0=impossible)
TRACK_CONFIGS = {
    # F1 Circuits
    "monaco": {"overtake_difficulty": 0.95, "pit_loss": 22.0, "sc_prob": 0.60},
    "monza": {"overtake_difficulty": 0.30, "pit_loss": 25.0, "sc_prob": 0.25},
    "spa": {"overtake_difficulty": 0.35, "pit_loss": 24.0, "sc_prob": 0.35},
    "silverstone": {"overtake_difficulty": 0.40, "pit_loss": 23.0, "sc_prob": 0.30},
    "bahrain": {"overtake_difficulty": 0.35, "pit_loss": 24.0, "sc_prob": 0.25},
    "jeddah": {"overtake_difficulty": 0.45, "pit_loss": 26.0, "sc_prob": 0.55},
    "melbourne": {"overtake_difficulty": 0.50, "pit_loss": 24.0, "sc_prob": 0.45},
    "suzuka": {"overtake_difficulty": 0.55, "pit_loss": 24.0, "sc_prob": 0.35},
    "singapore": {"overtake_difficulty": 0.60, "pit_loss": 30.0, "sc_prob": 0.70},
    "austin": {"overtake_difficulty": 0.40, "pit_loss": 23.0, "sc_prob": 0.30},
    "interlagos": {"overtake_difficulty": 0.35, "pit_loss": 22.0, "sc_prob": 0.35},
    "las vegas": {"overtake_difficulty": 0.30, "pit_loss": 25.0, "sc_prob": 0.40},
    "abu dhabi": {"overtake_difficulty": 0.45, "pit_loss": 24.0, "sc_prob": 0.20},
    # IndyCar Circuits
    "indianapolis": {"overtake_difficulty": 0.15, "pit_loss": 35.0, "sc_prob": 0.75},
    "st. petersburg": {"overtake_difficulty": 0.55, "pit_loss": 32.0, "sc_prob": 0.50},
    "long beach": {"overtake_difficulty": 0.65, "pit_loss": 33.0, "sc_prob": 0.55},
    "road america": {"overtake_difficulty": 0.40, "pit_loss": 30.0, "sc_prob": 0.30},
    "mid-ohio": {"overtake_difficulty": 0.55, "pit_loss": 28.0, "sc_prob": 0.40},
    "laguna seca": {"overtake_difficulty": 0.50, "pit_loss": 28.0, "sc_prob": 0.35},
    "default": {"overtake_difficulty": 0.45, "pit_loss": 25.0, "sc_prob": 0.35},
}

# Tire life estimates (laps)
TIRE_LIFE = {
    # F1
    "SOFT": 15, "MEDIUM": 25, "HARD": 40,
    # IndyCar
    "PRIMARY": 30, "ALTERNATE": 35, "RED": 25,
    # Fallback
    "UNKNOWN": 25
}

# =============================================================================
# Data Models
# =============================================================================

@dataclass
class DriverState:
    """Current state of a driver during the race."""
    driver_id: str
    driver_name: str
    team: str
    position: int
    gap_to_leader: float  # seconds
    gap_to_ahead: float   # seconds
    last_lap_time: float  # seconds
    best_lap_time: float  # seconds
    lap_times: List[float]  # recent laps
    tire_compound: str
    tire_age: int  # laps on current tires
    pit_stops: int
    is_on_track: bool
    status: str  # RUNNING, DNF, PIT


@dataclass
class RaceState:
    """Current race state snapshot."""
    series: str
    session_name: str
    session_key: str
    current_lap: int
    total_laps: int
    flag_status: str  # GREEN, YELLOW, RED, SC, VSC
    last_updated: str
    drivers: List[DriverState]


@dataclass
class Prediction:
    """Win probability prediction for a driver."""
    position: int
    driver_id: str
    driver_name: str
    team: str
    win_probability: float
    podium_probability: float
    points_probability: float
    confidence_interval: Tuple[float, float]
    key_factors: List[str]
    stats: Dict[str, Any]


# =============================================================================
# Data Fetching
# =============================================================================

_cache: Dict[str, Tuple[Any, float]] = {}


def _fetch_json(url: str, cache_ttl: int = 10) -> Dict:
    """Fetch JSON with caching."""
    now = time.time()
    if url in _cache:
        data, timestamp = _cache[url]
        if now - timestamp < cache_ttl:
            return data
    
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            _cache[url] = (data, now)
            return data
    except Exception:
        # Return cached data if available, even if stale
        if url in _cache:
            return _cache[url][0]
        raise


def fetch_f1_race_state() -> Optional[RaceState]:
    """Fetch current F1 race state from OpenF1."""
    try:
        # Get latest session
        sessions = _fetch_json(f"{OPENF1_BASE}/sessions?session_type=Race&year=2026")
        if not sessions:
            sessions = _fetch_json(f"{OPENF1_BASE}/sessions?session_type=Race&year=2025")
        if not sessions:
            return None
        
        latest = sessions[-1]
        session_key = latest.get("session_key")
        
        # Get driver positions/intervals
        intervals = _fetch_json(f"{OPENF1_BASE}/intervals?session_key={session_key}")
        drivers_info = _fetch_json(f"{OPENF1_BASE}/drivers?session_key={session_key}")
        laps = _fetch_json(f"{OPENF1_BASE}/laps?session_key={session_key}")
        
        # Build driver map
        driver_map = {d["driver_number"]: d for d in drivers_info}
        
        # Get latest intervals per driver
        latest_intervals = {}
        for interval in intervals:
            driver_num = interval.get("driver_number")
            latest_intervals[driver_num] = interval
        
        # Get lap data
        lap_data = {}
        for lap in laps:
            driver_num = lap.get("driver_number")
            if driver_num not in lap_data:
                lap_data[driver_num] = []
            if lap.get("lap_duration"):
                lap_data[driver_num].append(lap)
        
        # Build driver states
        drivers = []
        positions = sorted(latest_intervals.items(), key=lambda x: x[1].get("position", 99))
        
        for driver_num, interval in positions:
            info = driver_map.get(driver_num, {})
            driver_laps = lap_data.get(driver_num, [])
            
            # Get recent lap times
            recent_laps = [l.get("lap_duration", 0) for l in driver_laps[-10:] if l.get("lap_duration")]
            
            drivers.append(DriverState(
                driver_id=str(driver_num),
                driver_name=info.get("full_name", f"Driver {driver_num}"),
                team=info.get("team_name", "Unknown"),
                position=interval.get("position", 99),
                gap_to_leader=interval.get("gap_to_leader") or 0.0,
                gap_to_ahead=interval.get("interval") or 0.0,
                last_lap_time=recent_laps[-1] if recent_laps else 0.0,
                best_lap_time=min(recent_laps) if recent_laps else 0.0,
                lap_times=recent_laps[-5:],
                tire_compound="UNKNOWN",  # Would need stint data
                tire_age=0,
                pit_stops=0,
                is_on_track=True,
                status="RUNNING"
            ))
        
        # Get current lap
        current_lap = max((l.get("lap_number", 0) for l in laps), default=0)
        total_laps = latest.get("total_laps", 57)  # Default GP length
        
        return RaceState(
            series="f1",
            session_name=latest.get("session_name", "Race"),
            session_key=str(session_key),
            current_lap=current_lap,
            total_laps=total_laps,
            flag_status="GREEN",  # Would need race control data
            last_updated=datetime.utcnow().isoformat() + "Z",
            drivers=drivers
        )
    except Exception as e:
        print(f"[Predictions] F1 fetch error: {e}")
        return None


def fetch_indycar_race_state() -> Optional[RaceState]:
    """Fetch current IndyCar race state from Azure Blob Storage."""
    try:
        # Check if session is active
        config = _fetch_json(f"{INDYCAR_BLOB_BASE}/tsconfig.json?t={int(time.time())}")
        if config.get("no_track_activity", True):
            return None
        
        # Get live timing
        timing = _fetch_json(f"{INDYCAR_BLOB_BASE}/timingscoring-ris.json?t={int(time.time())}")
        timing_results = timing.get("timing_results", {})
        heartbeat = timing_results.get("heartbeat", {})
        entries = timing_results.get("entries", [])
        
        # Build driver states
        drivers = []
        for entry in entries:
            # Parse gap to leader
            gap_str = entry.get("Gap", "")
            gap_to_leader = 0.0
            if gap_str and gap_str != "--":
                try:
                    if ":" in gap_str:
                        parts = gap_str.split(":")
                        gap_to_leader = float(parts[0]) * 60 + float(parts[1])
                    else:
                        gap_to_leader = float(gap_str.replace("+", "").replace("s", ""))
                except ValueError:
                    gap_to_leader = 0.0
            
            # Parse lap times
            last_lap_str = entry.get("LastLap", "")
            last_lap = 0.0
            if last_lap_str and ":" in last_lap_str:
                try:
                    parts = last_lap_str.split(":")
                    last_lap = float(parts[0]) * 60 + float(parts[1])
                except ValueError:
                    pass
            
            best_lap_str = entry.get("BestLap", "")
            best_lap = 0.0
            if best_lap_str and ":" in best_lap_str:
                try:
                    parts = best_lap_str.split(":")
                    best_lap = float(parts[0]) * 60 + float(parts[1])
                except ValueError:
                    pass
            
            drivers.append(DriverState(
                driver_id=entry.get("Number", "0"),
                driver_name=entry.get("Driver", "Unknown"),
                team=entry.get("Team", "Unknown"),
                position=int(entry.get("Position", 99)),
                gap_to_leader=gap_to_leader,
                gap_to_ahead=0.0,  # Would need to calculate
                last_lap_time=last_lap,
                best_lap_time=best_lap,
                lap_times=[],  # Would need history
                tire_compound=entry.get("Tire", "PRIMARY"),
                tire_age=0,
                pit_stops=int(entry.get("PitStops", 0)),
                is_on_track=entry.get("OnTrack", "1") == "1",
                status=entry.get("Status", "RUNNING")
            ))
        
        # Sort by position
        drivers.sort(key=lambda d: d.position)
        
        # Calculate gaps to car ahead
        for i, driver in enumerate(drivers):
            if i > 0:
                driver.gap_to_ahead = driver.gap_to_leader - drivers[i-1].gap_to_leader
        
        return RaceState(
            series="indycar",
            session_name=heartbeat.get("EventName", "Race"),
            session_key=heartbeat.get("SessionId", "unknown"),
            current_lap=int(heartbeat.get("LapNumber", 0)),
            total_laps=int(heartbeat.get("TotalLaps", 200)),
            flag_status=heartbeat.get("SessionStatus", "GREEN"),
            last_updated=datetime.utcnow().isoformat() + "Z",
            drivers=drivers
        )
    except Exception as e:
        print(f"[Predictions] IndyCar fetch error: {e}")
        return None


# =============================================================================
# Prediction Models
# =============================================================================

def position_baseline(position: int, laps_remaining: int, total_drivers: int) -> float:
    """
    Baseline win probability from track position.
    
    Historical analysis:
    - P1 wins ~65% with 20+ laps remaining, ~85% with <10 laps
    - P2 wins ~15-20%
    - P3+ has <8% combined
    """
    race_progress = 1.0 - (laps_remaining / max(1, laps_remaining + 10))
    
    # Weights shift toward leader as race progresses
    if race_progress < 0.5:
        weights = [0.55, 0.20, 0.10, 0.06, 0.04, 0.02, 0.015, 0.01]
    elif race_progress < 0.75:
        weights = [0.65, 0.18, 0.08, 0.04, 0.02, 0.015, 0.01, 0.005]
    elif race_progress < 0.9:
        weights = [0.75, 0.14, 0.06, 0.02, 0.015, 0.01, 0.005, 0.002]
    else:
        weights = [0.88, 0.08, 0.025, 0.01, 0.003, 0.001, 0.0005, 0.0003]
    
    # Extend weights for all drivers
    while len(weights) < total_drivers:
        weights.append(weights[-1] * 0.5)
    
    if position <= len(weights):
        return weights[position - 1]
    return 0.001


def pace_adjustment(
    driver: DriverState,
    leader: DriverState,
    laps_remaining: int,
    track_config: Dict
) -> Tuple[float, Optional[str]]:
    """
    Adjust probability based on pace advantage.
    Returns (adjustment, explanation).
    """
    if not driver.lap_times or not leader.lap_times:
        return 0.0, None
    
    # Calculate rolling pace (average of last N laps)
    driver_pace = sum(driver.lap_times[-3:]) / len(driver.lap_times[-3:]) if driver.lap_times else 0
    leader_pace = sum(leader.lap_times[-3:]) / len(leader.lap_times[-3:]) if leader.lap_times else 0
    
    if driver_pace == 0 or leader_pace == 0:
        return 0.0, None
    
    pace_delta = leader_pace - driver_pace  # Positive = driver is faster
    
    # How many laps to catch?
    if pace_delta > 0 and driver.gap_to_leader > 0:
        laps_to_catch = driver.gap_to_leader / pace_delta
        can_catch = laps_to_catch < laps_remaining * 0.9
    else:
        can_catch = False
    
    overtake_factor = 1.0 - (track_config.get("overtake_difficulty", 0.5) * 0.6)
    
    if pace_delta > 0.8:  # Very fast
        adj = 0.15 * overtake_factor if can_catch else 0.03
        return adj, f"+{pace_delta:.2f}s/lap faster than leader"
    elif pace_delta > 0.4:
        adj = 0.08 * overtake_factor if can_catch else 0.02
        return adj, f"+{pace_delta:.2f}s/lap faster"
    elif pace_delta > 0.1:
        adj = 0.03 * overtake_factor if can_catch else 0.01
        return adj, f"Slightly faster pace (+{pace_delta:.2f}s)"
    elif pace_delta < -0.4:
        return -0.08, f"Slower pace ({pace_delta:.2f}s/lap)"
    elif pace_delta < -0.1:
        return -0.03, f"Slightly slower ({pace_delta:.2f}s/lap)"
    
    return 0.0, None


def strategy_adjustment(
    driver: DriverState,
    all_drivers: List[DriverState],
    laps_remaining: int
) -> Tuple[float, Optional[str]]:
    """
    Adjust for strategic factors (pit stops, tire age).
    """
    # Leader advantage from track position
    if driver.position == 1:
        if laps_remaining < 10:
            return 0.05, "Track position advantage in closing laps"
        return 0.02, "Controlling race from front"
    
    # Fresh tires advantage
    leader = all_drivers[0] if all_drivers else None
    if leader and driver.tire_age < leader.tire_age - 10:
        return 0.05, f"Fresher tires than leader ({driver.tire_age} vs {leader.tire_age} laps)"
    
    # Undercut potential
    if driver.position > 1 and driver.pit_stops < leader.pit_stops if leader else False:
        return 0.03, "Pit stop in hand - undercut potential"
    
    # Worn tires disadvantage
    tire_limit = TIRE_LIFE.get(driver.tire_compound, 25)
    if driver.tire_age > tire_limit * 0.8:
        return -0.03, f"Tires past optimal window ({driver.tire_age} laps)"
    
    return 0.0, None


def safety_car_adjustment(driver: DriverState, flag_status: str, laps_remaining: int) -> Tuple[float, Optional[str]]:
    """
    Adjust probabilities during caution periods.
    """
    if flag_status not in ["SC", "VSC", "YELLOW", "CAUTION"]:
        return 0.0, None
    
    if driver.position == 1:
        return -0.08, "Safety car compresses field"
    elif driver.position <= 3:
        return 0.04, "SC restart opportunity"
    elif driver.position <= 10:
        return 0.02, "Field bunched under caution"
    
    return 0.01, None


def gap_factor(driver: DriverState, laps_remaining: int, track_config: Dict) -> Tuple[float, Optional[str]]:
    """
    Factor in current gaps.
    """
    if driver.position == 1:
        pit_loss = track_config.get("pit_loss", 25.0)
        if driver.gap_to_ahead > pit_loss:
            return 0.03, f"Free pit stop window ({driver.gap_to_ahead:.1f}s to P2)"
        return 0.0, None
    
    if driver.gap_to_ahead < 1.0:
        return 0.02, f"Within striking distance ({driver.gap_to_ahead:.1f}s to P{driver.position-1})"
    
    return 0.0, None


# =============================================================================
# Main Prediction Logic
# =============================================================================

def compute_predictions(race_state: RaceState) -> List[Prediction]:
    """
    Compute win probabilities for all drivers.
    """
    if not race_state.drivers:
        return []
    
    laps_remaining = max(0, race_state.total_laps - race_state.current_lap)
    race_progress = race_state.current_lap / max(1, race_state.total_laps)
    
    # Get track config
    session_lower = race_state.session_name.lower()
    track_config = TRACK_CONFIGS.get("default")
    for track_name, config in TRACK_CONFIGS.items():
        if track_name in session_lower:
            track_config = config
            break
    
    leader = race_state.drivers[0] if race_state.drivers else None
    total_drivers = len(race_state.drivers)
    
    raw_predictions = []
    
    for driver in race_state.drivers:
        key_factors = []
        
        # Base probability
        base_prob = position_baseline(driver.position, laps_remaining, total_drivers)
        key_factors.append(f"Position: P{driver.position}")
        
        # Pace adjustment
        pace_adj, pace_reason = pace_adjustment(driver, leader, laps_remaining, track_config) if leader else (0.0, None)
        if pace_reason:
            key_factors.append(pace_reason)
        
        # Strategy adjustment
        strat_adj, strat_reason = strategy_adjustment(driver, race_state.drivers, laps_remaining)
        if strat_reason:
            key_factors.append(strat_reason)
        
        # Safety car
        sc_adj, sc_reason = safety_car_adjustment(driver, race_state.flag_status, laps_remaining)
        if sc_reason:
            key_factors.append(sc_reason)
        
        # Gap factor
        gap_adj, gap_reason = gap_factor(driver, laps_remaining, track_config)
        if gap_reason:
            key_factors.append(gap_reason)
        
        # Combine
        raw_prob = base_prob + pace_adj + strat_adj + sc_adj + gap_adj
        raw_prob = max(0.001, min(0.99, raw_prob))
        
        # Confidence interval (wider early, narrower late)
        ci_width = 0.25 * (1.0 - race_progress) + 0.05
        ci_lower = max(0.0, raw_prob - ci_width / 2)
        ci_upper = min(1.0, raw_prob + ci_width / 2)
        
        raw_predictions.append({
            "driver": driver,
            "raw_prob": raw_prob,
            "ci": (ci_lower, ci_upper),
            "key_factors": key_factors
        })
    
    # Normalize probabilities to sum to 1.0
    total_prob = sum(p["raw_prob"] for p in raw_predictions)
    
    predictions = []
    for p in raw_predictions:
        driver = p["driver"]
        norm_prob = p["raw_prob"] / total_prob if total_prob > 0 else 0.0
        
        # Podium probability (rough estimate)
        podium_prob = min(0.99, norm_prob * (4.0 - driver.position * 0.5)) if driver.position <= 10 else norm_prob * 0.1
        podium_prob = max(0.01, min(0.99, podium_prob))
        
        # Points probability (top 10)
        points_prob = 0.99 if driver.position <= 8 else 0.85 if driver.position <= 12 else 0.50 if driver.position <= 15 else 0.20
        
        predictions.append(Prediction(
            position=driver.position,
            driver_id=driver.driver_id,
            driver_name=driver.driver_name,
            team=driver.team,
            win_probability=round(norm_prob, 4),
            podium_probability=round(podium_prob, 4),
            points_probability=round(points_prob, 4),
            confidence_interval=(round(p["ci"][0], 4), round(p["ci"][1], 4)),
            key_factors=p["key_factors"],
            stats={
                "gap_to_leader": round(driver.gap_to_leader, 3),
                "gap_to_ahead": round(driver.gap_to_ahead, 3),
                "last_lap": round(driver.last_lap_time, 3),
                "best_lap": round(driver.best_lap_time, 3),
                "tire_compound": driver.tire_compound,
                "tire_age": driver.tire_age,
                "pit_stops": driver.pit_stops
            }
        ))
    
    predictions.sort(key=lambda p: p.position)
    return predictions


# =============================================================================
# Demo/Simulation Mode
# =============================================================================

def generate_demo_state(series: str) -> RaceState:
    """Generate realistic demo race state for testing."""
    if series == "f1":
        return RaceState(
            series="f1",
            session_name="Monaco Grand Prix",
            session_key="demo_f1",
            current_lap=45,
            total_laps=78,
            flag_status="GREEN",
            last_updated=datetime.utcnow().isoformat() + "Z",
            drivers=[
                DriverState("1", "Max Verstappen", "Red Bull Racing", 1, 0.0, 0.0, 74.892, 73.456, [74.9, 74.8, 75.1, 74.7, 74.9], "MEDIUM", 15, 1, True, "RUNNING"),
                DriverState("16", "Charles Leclerc", "Scuderia Ferrari", 2, 3.2, 3.2, 75.123, 73.678, [75.2, 75.1, 75.3, 75.0, 75.2], "MEDIUM", 15, 1, True, "RUNNING"),
                DriverState("4", "Lando Norris", "McLaren", 3, 5.8, 2.6, 75.456, 73.890, [75.5, 75.4, 75.6, 75.3, 75.5], "HARD", 8, 2, True, "RUNNING"),
                DriverState("55", "Carlos Sainz", "Scuderia Ferrari", 4, 8.4, 2.6, 75.234, 73.901, [75.3, 75.2, 75.4, 75.1, 75.3], "HARD", 8, 2, True, "RUNNING"),
                DriverState("81", "Oscar Piastri", "McLaren", 5, 12.1, 3.7, 75.567, 74.012, [75.6, 75.5, 75.7, 75.4, 75.6], "HARD", 8, 2, True, "RUNNING"),
                DriverState("63", "George Russell", "Mercedes", 6, 15.3, 3.2, 75.789, 74.234, [75.8, 75.7, 75.9, 75.6, 75.8], "MEDIUM", 18, 1, True, "RUNNING"),
                DriverState("44", "Lewis Hamilton", "Scuderia Ferrari", 7, 18.9, 3.6, 75.890, 74.345, [75.9, 75.8, 76.0, 75.7, 75.9], "MEDIUM", 18, 1, True, "RUNNING"),
                DriverState("11", "Sergio Perez", "Red Bull Racing", 8, 22.5, 3.6, 76.012, 74.567, [76.0, 75.9, 76.1, 75.8, 76.0], "HARD", 12, 2, True, "RUNNING"),
            ]
        )
    else:  # indycar
        return RaceState(
            series="indycar",
            session_name="Indianapolis 500",
            session_key="demo_indy",
            current_lap=150,
            total_laps=200,
            flag_status="GREEN",
            last_updated=datetime.utcnow().isoformat() + "Z",
            drivers=[
                DriverState("10", "Alex Palou", "Chip Ganassi Racing", 1, 0.0, 0.0, 41.234, 40.567, [41.2, 41.3, 41.1, 41.2, 41.3], "PRIMARY", 20, 4, True, "RUNNING"),
                DriverState("9", "Scott Dixon", "Chip Ganassi Racing", 2, 1.8, 1.8, 41.456, 40.678, [41.5, 41.4, 41.6, 41.5, 41.4], "PRIMARY", 20, 4, True, "RUNNING"),
                DriverState("2", "Josef Newgarden", "Team Penske", 3, 3.2, 1.4, 41.567, 40.789, [41.6, 41.5, 41.7, 41.6, 41.5], "PRIMARY", 22, 4, True, "RUNNING"),
                DriverState("5", "Pato O'Ward", "Arrow McLaren", 4, 5.1, 1.9, 41.678, 40.890, [41.7, 41.6, 41.8, 41.7, 41.6], "ALTERNATE", 15, 5, True, "RUNNING"),
                DriverState("12", "Will Power", "Team Penske", 5, 7.3, 2.2, 41.789, 40.901, [41.8, 41.7, 41.9, 41.8, 41.7], "ALTERNATE", 15, 5, True, "RUNNING"),
                DriverState("3", "Scott McLaughlin", "Team Penske", 6, 9.8, 2.5, 41.890, 41.012, [41.9, 41.8, 42.0, 41.9, 41.8], "PRIMARY", 24, 4, True, "RUNNING"),
            ]
        )


# =============================================================================
# HTTP Handler
# =============================================================================

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            series = query.get("series", ["f1"])[0].lower()
            top_n = int(query.get("top", [0])[0])
            demo_mode = "demo" in query
            
            # Fetch race state
            if demo_mode:
                race_state = generate_demo_state(series)
            elif series == "f1":
                race_state = fetch_f1_race_state()
            elif series == "indycar":
                race_state = fetch_indycar_race_state()
            else:
                self._send_json({"error": f"Unknown series: {series}"}, 400)
                return
            
            if not race_state:
                self._send_json({
                    "series": series,
                    "status": "no_active_session",
                    "message": f"No active {series.upper()} race session. Use ?demo for test data.",
                    "endpoints": {
                        "f1": "/api/predictions?series=f1",
                        "indycar": "/api/predictions?series=indycar",
                        "demo_f1": "/api/predictions?series=f1&demo",
                        "demo_indycar": "/api/predictions?series=indycar&demo"
                    }
                })
                return
            
            # Compute predictions
            predictions = compute_predictions(race_state)
            
            # Filter to top N if requested
            if top_n > 0:
                predictions = predictions[:top_n]
            
            # Calculate data quality
            data_quality = 0.9 if demo_mode else 0.85
            if race_state.drivers and all(d.lap_times for d in race_state.drivers):
                data_quality = 0.95
            
            # Confidence level based on race progress
            race_progress = race_state.current_lap / max(1, race_state.total_laps)
            if race_progress > 0.75:
                confidence_level = "high"
            elif race_progress > 0.5:
                confidence_level = "medium"
            else:
                confidence_level = "low"
            
            response = {
                "series": series,
                "session": {
                    "key": race_state.session_key,
                    "name": race_state.session_name,
                    "status": "demo" if demo_mode else "live"
                },
                "race_state": {
                    "current_lap": race_state.current_lap,
                    "total_laps": race_state.total_laps,
                    "race_progress": round(race_state.current_lap / max(1, race_state.total_laps), 3),
                    "flag_status": race_state.flag_status,
                    "last_updated": race_state.last_updated
                },
                "predictions": [asdict(p) for p in predictions],
                "model_info": {
                    "version": "1.0.0",
                    "confidence_level": confidence_level,
                    "data_quality": data_quality
                }
            }
            
            self._send_json(response)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._send_json({"error": str(e)}, 500)
    
    def _send_json(self, data: Dict, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=5')  # Short cache for live data
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())


# =============================================================================
# CLI Testing
# =============================================================================

if __name__ == "__main__":
    # Test with demo data
    print("=== F1 Demo Predictions ===")
    race_state = generate_demo_state("f1")
    predictions = compute_predictions(race_state)
    
    for p in predictions[:5]:
        print(f"P{p.position} {p.driver_name}: {p.win_probability:.1%} ({p.confidence_interval[0]:.1%}-{p.confidence_interval[1]:.1%})")
        for factor in p.key_factors:
            print(f"    • {factor}")
        print()
    
    print("\n=== IndyCar Demo Predictions ===")
    race_state = generate_demo_state("indycar")
    predictions = compute_predictions(race_state)
    
    for p in predictions[:5]:
        print(f"P{p.position} {p.driver_name}: {p.win_probability:.1%} ({p.confidence_interval[0]:.1%}-{p.confidence_interval[1]:.1%})")
        for factor in p.key_factors:
            print(f"    • {factor}")
        print()
