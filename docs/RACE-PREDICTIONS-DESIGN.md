# Live Race Prediction & Analysis System

> **GridView Race Predictions** — Real-time win probability estimates and strategic insights during live races.

---

## Executive Summary

This document outlines the design for a live race prediction system that computes win probabilities and provides analytical insights during active racing sessions. The system leverages real-time timing data from our existing integrations (OpenF1, IndyCar Azure, Alkamelsystems) and applies statistical models to estimate race outcomes.

**Key Capabilities:**
- Real-time win probability percentages for all drivers
- Confidence intervals that reflect prediction uncertainty
- Key factor explanations for each prediction
- Support for F1 and IndyCar initially, with extensibility for IMSA/WEC

---

## 1. Data Sources & Availability

### 1.1 Formula 1 (via OpenF1 API)

| Endpoint | Data | Update Rate | Prediction Value |
|----------|------|-------------|------------------|
| `/v1/laps` | Lap times, sector times, pit status | Per lap | ⭐⭐⭐⭐⭐ |
| `/v1/car_data` | Speed, throttle, brake, DRS, RPM | ~3.7 Hz | ⭐⭐⭐⭐ |
| `/v1/position` | Track position coordinates | ~3.7 Hz | ⭐⭐⭐ |
| `/v1/stints` | Tire compounds, stint lengths | On pit stops | ⭐⭐⭐⭐⭐ |
| `/v1/intervals` | Gap to leader, gap to car ahead | ~1 Hz | ⭐⭐⭐⭐⭐ |
| `/v1/pit` | Pit lane activity | On pit entry/exit | ⭐⭐⭐⭐ |
| `/v1/weather` | Track temp, air temp, rain chance | ~30s | ⭐⭐⭐ |
| `/v1/race_control` | Flags, VSC, SC, red flags | On event | ⭐⭐⭐⭐⭐ |

**Access:** Historical = free, Real-time = paid subscription required.

### 1.2 IndyCar (via Azure Blob Storage)

| Endpoint | Data | Update Rate | Prediction Value |
|----------|------|-------------|------------------|
| `timingscoring-ris.json` | Full timing & scoring | ~1s | ⭐⭐⭐⭐⭐ |
| `trackactivityleaderboardfeed.json` | Leaderboard | ~1s | ⭐⭐⭐⭐ |
| `ntt-data/data_polling_blob.json` | NTT pit predictions | During race | ⭐⭐⭐⭐ |
| `tsconfig.json` | Session status, flags | ~30s | ⭐⭐⭐ |

**Access:** Public, no authentication required.

### 1.3 IMSA (via Alkamelsystems)

| Source | Data | Availability | Prediction Value |
|--------|------|--------------|------------------|
| Results Archive | Historical results, lap times | Post-session | ⭐⭐⭐ |
| Live Timing | Real-time positions, gaps | During session | ⭐⭐⭐⭐ |

**Access:** Results = public, Live timing = requires WebSocket/Meteor scraping.

---

## 2. Prediction Model Architecture

### 2.1 Core Philosophy

We use an **ensemble approach** combining:
1. **Position-Based Baseline** — Current track position is the strongest predictor
2. **Pace Differential Model** — Raw speed advantage/disadvantage
3. **Strategy Projection** — Pit stop timing and tire age effects
4. **Historical Regression** — Circuit-specific performance patterns

### 2.2 Input Features

#### Primary Features (Real-time)
```python
class RaceState:
    """Current race state snapshot."""
    current_lap: int
    total_laps: int
    race_progress: float  # 0.0 to 1.0
    
    drivers: List[DriverState]
    
    flag_status: str  # GREEN, YELLOW, RED, SC, VSC
    weather: WeatherState  # rain_chance, track_temp, air_temp
    
class DriverState:
    """Individual driver state."""
    driver_id: str
    position: int
    gap_to_leader: float  # seconds
    gap_to_ahead: float   # seconds
    
    last_lap_time: float
    best_lap_time: float
    lap_times_history: List[float]  # last N laps
    
    tire_compound: str      # SOFT, MEDIUM, HARD (F1) / PRIMARY, ALTERNATE (IndyCar)
    tire_age_laps: int
    pit_stops_completed: int
    
    is_on_track: bool
    in_pit_lane: bool
    status: str  # RUNNING, DNF, DSQ
```

#### Derived Features (Computed)
```python
# Pace Metrics
rolling_pace_3lap: float      # Average of last 3 laps
rolling_pace_5lap: float      # Average of last 5 laps  
pace_vs_leader: float         # Relative pace (negative = faster)
pace_trend: float             # Improving/degrading (-1 to +1)
lap_time_consistency: float   # Standard deviation of lap times

# Strategic Metrics
expected_pit_window: Tuple[int, int]  # Estimated pit lap range
tire_degradation_rate: float          # Seconds lost per lap on current tires
undercut_vulnerability: bool          # At risk of losing position to undercut
overcut_potential: bool               # Can gain via late stop

# Position Metrics
track_position_value: float   # How hard to overtake at this circuit
air_gap_sufficient: bool      # Enough gap to pit and stay ahead
drs_range: bool               # Within 1s of car ahead (F1)
```

### 2.3 Model Components

#### Component 1: Position-Based Probability

The simplest but strongest signal — current position strongly predicts finish position.

```python
def position_baseline(position: int, laps_remaining: int, total_drivers: int) -> float:
    """
    Baseline win probability from track position.
    
    Historical analysis shows:
    - P1 wins ~65% of races when leading with 20+ laps remaining
    - P1 wins ~85% when leading with <10 laps remaining
    - P2 wins ~15-20% from second place
    - P3+ has <8% combined win probability
    """
    if laps_remaining > 20:
        weights = [0.65, 0.18, 0.08, 0.04, 0.02] + [0.01] * (total_drivers - 5)
    elif laps_remaining > 10:
        weights = [0.75, 0.14, 0.06, 0.03, 0.01] + [0.005] * (total_drivers - 5)
    else:
        weights = [0.85, 0.10, 0.03, 0.015, 0.005] + [0.001] * (total_drivers - 5)
    
    return weights[position - 1] if position <= len(weights) else 0.001
```

#### Component 2: Pace Differential Adjustment

Adjusts probability based on relative pace.

```python
def pace_adjustment(
    driver: DriverState, 
    leader: DriverState,
    gap_to_leader: float,
    laps_remaining: int,
    track_difficulty: float  # 0.0 (easy) to 1.0 (hard to overtake)
) -> float:
    """
    Adjust probability based on pace advantage.
    
    If a driver is significantly faster, they have higher win potential.
    If they're slower, lower potential even if well-positioned.
    """
    pace_delta = leader.rolling_pace_5lap - driver.rolling_pace_5lap  # + means driver is faster
    
    # Time needed to catch leader
    laps_to_catch = gap_to_leader / pace_delta if pace_delta > 0 else float('inf')
    
    # Can they theoretically catch up?
    can_catch = laps_to_catch < laps_remaining * 0.9  # 10% buffer
    
    # Overtaking difficulty factor
    overtake_factor = 1.0 - (track_difficulty * 0.5)  # Reduce win prob at hard circuits
    
    if pace_delta > 0.5:  # >0.5s/lap faster
        return 0.15 * overtake_factor if can_catch else 0.02
    elif pace_delta > 0.2:  # 0.2-0.5s/lap faster
        return 0.08 * overtake_factor if can_catch else 0.01
    elif pace_delta < -0.3:  # Slower than leader
        return -0.10  # Negative adjustment
    
    return 0.0
```

#### Component 3: Strategy Projection

Models remaining pit stops and their impact.

```python
def strategy_projection(
    driver: DriverState,
    competitors: List[DriverState],
    laps_remaining: int,
    pit_time_loss: float  # Track-specific pit lane time (~20-25s F1, ~30-40s IndyCar)
) -> Tuple[float, str]:
    """
    Project strategic scenarios and their probability impact.
    
    Returns adjustment factor and explanation.
    """
    expected_stops_driver = estimate_remaining_stops(driver, laps_remaining)
    
    # Check undercut vulnerability
    for competitor in competitors:
        if competitor.position == driver.position + 1:  # Car behind
            expected_stops_comp = estimate_remaining_stops(competitor, laps_remaining)
            
            if competitor.tire_age_laps < driver.tire_age_laps - 5:
                # Competitor on fresher tires, undercut risk
                return (-0.05, "Undercut vulnerable to P" + str(competitor.position))
    
    # Check overcut potential
    if driver.tire_compound == "HARD" and driver.position > 1:
        leader = competitors[0]
        if leader.tire_compound in ["SOFT", "MEDIUM"] and leader.tire_age_laps > 15:
            return (0.05, "Overcut potential as leader on worn tires")
    
    return (0.0, "Strategy neutral")

def estimate_remaining_stops(driver: DriverState, laps_remaining: int) -> int:
    """Estimate how many more pit stops a driver needs."""
    # Typical tire life varies by compound and circuit
    tire_life = {
        "SOFT": 15, "MEDIUM": 25, "HARD": 35,
        "PRIMARY": 30, "ALTERNATE": 35  # IndyCar
    }
    max_stint = tire_life.get(driver.tire_compound, 25)
    laps_on_current = driver.tire_age_laps
    remaining_on_current = max_stint - laps_on_current
    
    if remaining_on_current >= laps_remaining:
        return 0
    
    laps_after_stop = laps_remaining - remaining_on_current
    return 1 + (laps_after_stop // max_stint)
```

#### Component 4: Safety Car / Caution Model

Safety cars compress the field and change probabilities.

```python
def safety_car_adjustment(
    driver: DriverState,
    flag_status: str,
    gap_to_leader: float,
    laps_remaining: int
) -> float:
    """
    Adjust probabilities during or after safety car.
    
    Safety cars bunch up the field, giving trailing drivers a chance.
    """
    if flag_status not in ["SC", "VSC", "YELLOW"]:
        return 0.0
    
    if driver.position == 1:
        # Leader loses advantage under SC
        return -0.10
    elif driver.position <= 5:
        # Top 5 gain opportunity
        return 0.05 + (5 - driver.position) * 0.02
    else:
        # Slight boost for rest of field
        return 0.02
```

### 2.4 Ensemble Combination

```python
def compute_win_probability(
    driver: DriverState,
    race_state: RaceState,
    all_drivers: List[DriverState],
    track_config: TrackConfig
) -> PredictionResult:
    """
    Combine all model components into final probability.
    """
    laps_remaining = race_state.total_laps - race_state.current_lap
    
    # Base probability from position
    base_prob = position_baseline(
        driver.position, 
        laps_remaining, 
        len(all_drivers)
    )
    
    # Pace adjustment
    leader = all_drivers[0]
    pace_adj = pace_adjustment(
        driver, leader,
        driver.gap_to_leader,
        laps_remaining,
        track_config.overtake_difficulty
    )
    
    # Strategy projection
    strat_adj, strat_reason = strategy_projection(
        driver, all_drivers, laps_remaining, 
        track_config.pit_time_loss
    )
    
    # Safety car adjustment
    sc_adj = safety_car_adjustment(
        driver,
        race_state.flag_status,
        driver.gap_to_leader,
        laps_remaining
    )
    
    # Combine with weights
    raw_prob = base_prob + pace_adj + strat_adj + sc_adj
    
    # Normalize across all drivers
    # (done at caller level to ensure sum = 1.0)
    
    # Confidence interval based on race progress
    # Early race = wider interval, late race = narrower
    confidence_width = 0.25 * (1.0 - race_state.race_progress) + 0.05
    
    return PredictionResult(
        driver_id=driver.driver_id,
        win_probability=max(0.001, min(0.99, raw_prob)),
        confidence_interval=(
            max(0.0, raw_prob - confidence_width),
            min(1.0, raw_prob + confidence_width)
        ),
        key_factors=[
            f"Position: P{driver.position}",
            f"Pace: {pace_adj:+.1%} adjustment",
            strat_reason if strat_adj != 0 else None,
            "SC boost" if sc_adj > 0 else None
        ]
    )
```

---

## 3. Confidence Intervals

### 3.1 Sources of Uncertainty

1. **Race Progress** — Early race has high uncertainty, late race is more certain
2. **Data Quality** — Missing or delayed data increases uncertainty
3. **Strategic Unknowns** — Unrevealed pit strategies
4. **External Factors** — Weather changes, mechanical reliability

### 3.2 Interval Calculation

```python
def confidence_interval(
    base_probability: float,
    race_progress: float,  # 0.0 to 1.0
    data_staleness: float,  # seconds since last update
    has_pit_data: bool
) -> Tuple[float, float]:
    """
    Calculate 90% confidence interval for prediction.
    """
    # Base width decreases as race progresses
    progress_factor = 0.30 * (1.0 - race_progress)  # 30% → 0%
    
    # Stale data increases uncertainty
    staleness_factor = min(0.10, data_staleness / 60.0 * 0.05)  # +5% per minute stale
    
    # Missing pit data adds uncertainty
    pit_factor = 0.05 if not has_pit_data else 0.0
    
    total_width = progress_factor + staleness_factor + pit_factor + 0.05  # min 5%
    
    lower = max(0.0, base_probability - total_width / 2)
    upper = min(1.0, base_probability + total_width / 2)
    
    return (lower, upper)
```

### 3.3 Displaying Uncertainty

```json
{
  "driver": "Max Verstappen",
  "win_probability": 0.72,
  "confidence_interval": [0.58, 0.86],
  "confidence_level": "high",
  "uncertainty_factors": [
    "Race 70% complete - predictions stabilizing",
    "All pit data available"
  ]
}
```

---

## 4. Key Factors Explanation

Each prediction includes human-readable explanations:

### Factor Categories

| Category | Examples |
|----------|----------|
| **Position** | "Leading with 12 lap buffer", "P3 but closing on P2" |
| **Pace** | "Fastest on track (+0.4s/lap)", "Struggling with tire deg" |
| **Strategy** | "Fresher tires than leader", "Undercut window closing" |
| **Gaps** | "4.2s clear of P2", "Within DRS range of leader" |
| **External** | "SC bunched field", "Light rain expected lap 35" |

### Example Output

```json
{
  "predictions": [
    {
      "position": 1,
      "driver": "Max Verstappen",
      "team": "Red Bull Racing",
      "win_probability": 0.72,
      "confidence_interval": [0.58, 0.86],
      "key_factors": [
        "Leading race with 4.8s gap",
        "Consistent pace, +0.2s faster than P2",
        "Same pit stop strategy as P2",
        "Track position advantage at Monaco"
      ]
    },
    {
      "position": 2,
      "driver": "Charles Leclerc", 
      "team": "Scuderia Ferrari",
      "win_probability": 0.18,
      "confidence_interval": [0.08, 0.28],
      "key_factors": [
        "4.8s behind leader",
        "Pace deficit of 0.2s/lap",
        "Would need 24 laps to catch at current pace (15 remaining)",
        "Undercut possible if leader pits first"
      ]
    }
  ]
}
```

---

## 5. Circuit-Specific Configuration

### Track Profiles

```python
TRACK_CONFIGS = {
    "monaco": TrackConfig(
        overtake_difficulty=0.95,  # Nearly impossible
        pit_time_loss=22.0,
        typical_stint_soft=18,
        typical_stint_medium=28,
        typical_stint_hard=40,
        safety_car_probability=0.60,
        drs_effectiveness=0.1,  # Minimal
    ),
    "monza": TrackConfig(
        overtake_difficulty=0.40,
        pit_time_loss=25.0,
        typical_stint_soft=12,
        typical_stint_medium=22,
        typical_stint_hard=32,
        safety_car_probability=0.25,
        drs_effectiveness=0.9,  # Very effective
    ),
    "indianapolis": TrackConfig(  # IndyCar
        overtake_difficulty=0.20,  # Ovals have easy passing
        pit_time_loss=35.0,
        typical_stint_primary=30,
        typical_stint_alternate=35,
        safety_car_probability=0.70,  # High caution rate
        drs_effectiveness=None,  # No DRS
    ),
    # ... more circuits
}
```

---

## 6. API Design

### Endpoint: `GET /api/predictions`

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `series` | string | Yes | `f1`, `indycar`, `imsa` |
| `session` | string | No | Session key (default: `latest`) |
| `driver` | string | No | Filter to specific driver |
| `top` | int | No | Return only top N (default: all) |

#### Response Schema

```typescript
interface PredictionResponse {
  series: string;
  session: {
    key: string;
    name: string;
    status: "live" | "finished" | "not_started";
  };
  race_state: {
    current_lap: number;
    total_laps: number;
    race_progress: number;  // 0.0 to 1.0
    flag_status: string;
    last_updated: string;   // ISO timestamp
  };
  predictions: Prediction[];
  model_info: {
    version: string;
    confidence_level: "high" | "medium" | "low";
    data_quality: number;  // 0.0 to 1.0
  };
}

interface Prediction {
  position: number;
  driver_id: string;
  driver_name: string;
  team: string;
  
  win_probability: number;
  podium_probability: number;
  points_probability: number;
  
  confidence_interval: [number, number];
  
  key_factors: string[];
  
  stats: {
    gap_to_leader: number;
    last_lap: number;
    best_lap: number;
    tire_compound: string;
    tire_age: number;
    pit_stops: number;
  };
}
```

#### Example Request

```bash
curl "https://gridview.xyz/api/predictions?series=f1&top=10"
```

#### Example Response

```json
{
  "series": "f1",
  "session": {
    "key": "9500",
    "name": "Monaco Grand Prix",
    "status": "live"
  },
  "race_state": {
    "current_lap": 45,
    "total_laps": 78,
    "race_progress": 0.577,
    "flag_status": "GREEN",
    "last_updated": "2026-05-24T15:32:18Z"
  },
  "predictions": [
    {
      "position": 1,
      "driver_id": "1",
      "driver_name": "Max Verstappen",
      "team": "Red Bull Racing",
      "win_probability": 0.68,
      "podium_probability": 0.95,
      "points_probability": 0.99,
      "confidence_interval": [0.52, 0.84],
      "key_factors": [
        "Leading with 3.2s advantage",
        "Matching pace with P2",
        "1 pit stop remaining (same as P2)",
        "Monaco overtaking nearly impossible"
      ],
      "stats": {
        "gap_to_leader": 0.0,
        "last_lap": 74.892,
        "best_lap": 73.456,
        "tire_compound": "HARD",
        "tire_age": 12,
        "pit_stops": 1
      }
    }
  ],
  "model_info": {
    "version": "1.0.0",
    "confidence_level": "high",
    "data_quality": 0.95
  }
}
```

### Endpoint: `GET /api/predictions/history`

Returns prediction accuracy over time for model validation.

---

## 7. Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create `api/predictions.py` with basic endpoint
- [ ] Implement F1 data fetching via OpenF1 (historical first)
- [ ] Implement IndyCar data fetching via Azure blobs
- [ ] Build position-based baseline model

### Phase 2: Prediction Models (Week 2)
- [ ] Implement pace differential model
- [ ] Add strategy projection logic
- [ ] Implement safety car adjustments
- [ ] Build ensemble combiner

### Phase 3: Confidence & Explainability (Week 3)
- [ ] Add confidence interval calculations
- [ ] Implement key factor explanations
- [ ] Create track configuration database
- [ ] Add historical validation

### Phase 4: Real-time Integration (Week 4)
- [ ] Connect to live timing feeds
- [ ] Add caching layer for performance
- [ ] Implement WebSocket support for live updates
- [ ] Build dashboard widget

---

## 8. Future Enhancements

### Machine Learning Evolution
- Train on historical race data to learn circuit-specific patterns
- Use gradient boosting for feature weighting
- Neural network for complex interaction effects

### Additional Features
- **Podium probabilities** — P1-3 finish likelihood
- **Points projections** — Expected championship points
- **Head-to-head** — Specific battle predictions
- **Weather impact** — Rain probability integration
- **Reliability model** — DNF risk based on history

### Series Expansion
- WEC/IMSA multi-class predictions
- NASCAR with stage predictions
- MotoGP with crash risk modeling

---

## Appendix A: Historical Accuracy Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Winner prediction (pre-race) | 40% | Hard due to race incidents |
| Winner prediction (lap 1) | 55% | Position established |
| Winner prediction (50% race) | 70% | Strategy clearer |
| Winner prediction (75% race) | 85% | High confidence |
| Podium prediction accuracy | 60% | Top 3 finishers |
| Brier score | < 0.15 | Probability calibration |

---

## Appendix B: References

- OpenF1 API Documentation: https://openf1.org
- IndyCar Timing Infrastructure: See `TIMING-REVERSE-ENGINEERING.md`
- Alkamelsystems Scraper: See `api/_alkamel.py`
- F1 Historical Data: Ergast API (deprecated 2024), FastF1 library
