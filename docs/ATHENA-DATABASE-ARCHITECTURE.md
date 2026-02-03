# 🦉 Athena Report: Historical Database Architecture for GridView

**Date:** 2026-02-03  
**Analyst:** Athena (Research & Strategy)  
**Status:** Complete Architecture Proposal

---

## Executive Summary

This document outlines the architecture for GridView's historical motorsport database. The design prioritizes:
- **Multi-series support** (F1, NASCAR, IndyCar, IMSA, WEC, MotoGP, WRC)
- **Query flexibility** for results, standings progression, driver statistics
- **Scalability** from free tier to production
- **Data preservation** (especially critical with Ergast API sunset)

**Recommended Stack:** Supabase (Postgres + REST API + Auth ready for future features)

---

## 1. Database Selection

### Recommendation: Supabase

| Factor | Supabase | PlanetScale | Turso | Raw Postgres |
|--------|----------|-------------|-------|--------------|
| **Free Tier** | 500MB, 2 projects | 5GB, sleep after 7d | 8GB, 500M reads | Self-host only |
| **SQL Dialect** | Postgres (full) | MySQL | SQLite | Postgres |
| **REST API** | Built-in | None | None | Build yourself |
| **Realtime** | Built-in | No | No | Add yourself |
| **Auth** | Built-in | No | No | Add yourself |
| **Edge Functions** | Yes (Deno) | No | No | No |
| **Pricing Growth** | Predictable | Usage-based | Usage-based | Server costs |

**Why Supabase wins:**
1. **Postgres** — Full SQL power, JSONB for flexible data, excellent for analytical queries
2. **Built-in REST API** — Instant `/api/history/*` endpoints with PostgREST
3. **Row Level Security** — Ready for future user features (favorites, predictions)
4. **Free tier generous** — 500MB handles years of race data easily
5. **Vercel integration** — Seamless with GridView's current deployment

### Sizing Estimate

| Data Type | Records (10 years) | Avg Size | Total |
|-----------|-------------------|----------|-------|
| Races | ~2,500 | 500 bytes | 1.25 MB |
| Results | ~100,000 | 300 bytes | 30 MB |
| Lap Times | ~5,000,000 | 100 bytes | 500 MB |
| Standings | ~25,000 | 200 bytes | 5 MB |
| Drivers | ~3,000 | 500 bytes | 1.5 MB |
| Teams | ~500 | 400 bytes | 0.2 MB |

**Without lap times:** ~40 MB (fits easily in free tier)  
**With lap times:** ~540 MB (need Pro tier for full F1 lap data)

**Recommendation:** Start without lap times, add later for F1 premium features.

---

## 2. Schema Design

### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐
│     series      │       │     tracks      │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ code (f1,nascar)│       │ name            │
│ name            │       │ country         │
│ color           │       │ city            │
│ logo_url        │       │ length_km       │
└────────┬────────┘       │ track_type      │
         │                │ latitude        │
         │                │ longitude       │
         │                └────────┬────────┘
         │                         │
         ▼                         ▼
┌─────────────────────────────────────────────┐
│                   races                      │
├─────────────────────────────────────────────┤
│ id (PK)                                      │
│ series_id (FK) ──────────────────────────────┘
│ track_id (FK) ───────────────────────────────┘
│ season (year)                                │
│ round                                        │
│ name                                         │
│ date                                         │
│ official_name                                │
│ laps / distance                              │
│ status (scheduled/completed/cancelled)       │
│ external_ids (JSONB: {ergast, nascar, ...}) │
└────────┬────────────────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────────────────────────────┐
│                  sessions                    │
├─────────────────────────────────────────────┤
│ id (PK)                                      │
│ race_id (FK)                                 │
│ type (practice1/quali/sprint/race)           │
│ scheduled_start                              │
│ actual_start                                 │
│ status                                       │
└────────┬────────────────────────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────────────────────────────────┐
│                  results                     │
├─────────────────────────────────────────────┤
│ id (PK)                                      │
│ session_id (FK)                              │
│ driver_id (FK) ─────────────────────────────┐
│ team_id (FK) ───────────────────────────────┤
│ position                                     │
│ position_text (for DNF, DSQ, etc.)          │
│ grid_position                                │
│ points                                       │
│ laps_completed                               │
│ time_ms                                      │
│ gap_to_leader_ms                             │
│ status (finished/dnf/dsq/dns)               │
│ fastest_lap (boolean)                        │
│ fastest_lap_time_ms                          │
│ car_number                                   │
│ extra_data (JSONB for series-specific)      │
└─────────────────────────────────────────────┘
         │                         │
         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐
│     drivers     │       │      teams      │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ first_name      │       │ name            │
│ last_name       │       │ short_name      │
│ nationality     │       │ nationality     │
│ dob             │       │ founded_year    │
│ code (3-letter) │       │ color           │
│ permanent_number│       │ logo_url        │
│ photo_url       │       │ external_ids    │
│ external_ids    │       └─────────────────┘
└─────────────────┘

┌─────────────────────────────────────────────┐
│             standings_snapshots              │
├─────────────────────────────────────────────┤
│ id (PK)                                      │
│ series_id (FK)                               │
│ season                                       │
│ after_round                                  │
│ type (driver/constructor/team)               │
│ entity_id (driver_id or team_id)            │
│ position                                     │
│ points                                       │
│ wins                                         │
│ podiums                                      │
│ snapshot_date                                │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│               lap_times                      │
│         (optional, for detailed analysis)   │
├─────────────────────────────────────────────┤
│ id (PK)                                      │
│ session_id (FK)                              │
│ driver_id (FK)                               │
│ lap_number                                   │
│ time_ms                                      │
│ sector_1_ms                                  │
│ sector_2_ms                                  │
│ sector_3_ms                                  │
│ position                                     │
│ compound (tire type)                         │
│ pit_in_lap (boolean)                         │
│ pit_out_lap (boolean)                        │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│           driver_team_history               │
│        (tracks team changes over time)       │
├─────────────────────────────────────────────┤
│ id (PK)                                      │
│ driver_id (FK)                               │
│ team_id (FK)                                 │
│ series_id (FK)                               │
│ start_date                                   │
│ end_date (nullable for current)              │
└─────────────────────────────────────────────┘
```

### SQL Schema

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- SERIES
-- ============================================
CREATE TABLE series (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(20) UNIQUE NOT NULL,  -- 'f1', 'nascar_cup', 'indycar', etc.
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50),
    color VARCHAR(7),  -- Hex color for UI
    logo_url TEXT,
    priority INTEGER DEFAULT 100,  -- For display ordering
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed data
INSERT INTO series (code, name, short_name, color, priority) VALUES
    ('f1', 'Formula 1', 'F1', '#E10600', 1),
    ('nascar_cup', 'NASCAR Cup Series', 'NASCAR', '#FFCC00', 2),
    ('nascar_xfinity', 'NASCAR Xfinity Series', 'Xfinity', '#0052CC', 10),
    ('nascar_truck', 'NASCAR Craftsman Truck Series', 'Trucks', '#00A651', 11),
    ('indycar', 'NTT IndyCar Series', 'IndyCar', '#0072CE', 3),
    ('imsa_gtp', 'IMSA WeatherTech SportsCar Championship', 'IMSA', '#C8102E', 4),
    ('wec', 'FIA World Endurance Championship', 'WEC', '#001489', 5),
    ('motogp', 'MotoGP World Championship', 'MotoGP', '#FF5500', 6),
    ('wrc', 'FIA World Rally Championship', 'WRC', '#1E3A5F', 7),
    ('fe', 'ABB FIA Formula E World Championship', 'Formula E', '#14B8A6', 8);

-- ============================================
-- TRACKS
-- ============================================
CREATE TABLE tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    short_name VARCHAR(100),
    country VARCHAR(100),
    country_code CHAR(3),  -- ISO 3166-1 alpha-3
    city VARCHAR(100),
    length_km DECIMAL(6,3),
    track_type VARCHAR(50),  -- 'road', 'oval', 'street', 'rally'
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    timezone VARCHAR(50),
    external_ids JSONB DEFAULT '{}',  -- {"ergast": "spa", "nascar": "123"}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tracks_country ON tracks(country_code);
CREATE INDEX idx_tracks_external_ids ON tracks USING GIN(external_ids);

-- ============================================
-- RACES (Events/Rounds)
-- ============================================
CREATE TABLE races (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    series_id UUID NOT NULL REFERENCES series(id),
    track_id UUID REFERENCES tracks(id),
    season INTEGER NOT NULL,
    round INTEGER NOT NULL,
    name VARCHAR(200) NOT NULL,
    official_name VARCHAR(300),
    date DATE NOT NULL,
    scheduled_laps INTEGER,
    scheduled_distance_km DECIMAL(8,3),
    status VARCHAR(20) DEFAULT 'scheduled',  -- scheduled, completed, cancelled
    external_ids JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',  -- Series-specific data
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(series_id, season, round)
);

CREATE INDEX idx_races_series_season ON races(series_id, season);
CREATE INDEX idx_races_date ON races(date);
CREATE INDEX idx_races_track ON races(track_id);
CREATE INDEX idx_races_external_ids ON races USING GIN(external_ids);

-- ============================================
-- SESSIONS
-- ============================================
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    race_id UUID NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,  -- 'practice1', 'practice2', 'qualifying', 'sprint', 'race'
    name VARCHAR(100),
    scheduled_start TIMESTAMPTZ,
    actual_start TIMESTAMPTZ,
    scheduled_end TIMESTAMPTZ,
    actual_end TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'scheduled',
    weather JSONB,  -- {temp: 25, conditions: 'sunny', track_temp: 40}
    external_ids JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sessions_race ON sessions(race_id);
CREATE INDEX idx_sessions_type ON sessions(type);

-- ============================================
-- DRIVERS
-- ============================================
CREATE TABLE drivers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    full_name VARCHAR(200) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED,
    code VARCHAR(3),  -- 'VER', 'HAM', etc.
    permanent_number INTEGER,
    nationality VARCHAR(100),
    nationality_code CHAR(3),
    date_of_birth DATE,
    photo_url TEXT,
    wikipedia_url TEXT,
    external_ids JSONB DEFAULT '{}',  -- {"ergast": "max_verstappen", "openf1": 1}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_drivers_name ON drivers(last_name, first_name);
CREATE INDEX idx_drivers_code ON drivers(code);
CREATE INDEX idx_drivers_external_ids ON drivers USING GIN(external_ids);

-- ============================================
-- TEAMS (Constructors/Manufacturers)
-- ============================================
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    short_name VARCHAR(100),
    nationality VARCHAR(100),
    nationality_code CHAR(3),
    founded_year INTEGER,
    primary_color VARCHAR(7),
    secondary_color VARCHAR(7),
    logo_url TEXT,
    external_ids JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_teams_name ON teams(name);
CREATE INDEX idx_teams_external_ids ON teams USING GIN(external_ids);

-- ============================================
-- DRIVER-TEAM HISTORY
-- ============================================
CREATE TABLE driver_team_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    driver_id UUID NOT NULL REFERENCES drivers(id),
    team_id UUID NOT NULL REFERENCES teams(id),
    series_id UUID NOT NULL REFERENCES series(id),
    start_date DATE NOT NULL,
    end_date DATE,  -- NULL = current
    role VARCHAR(50) DEFAULT 'driver',  -- 'driver', 'reserve', 'test'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_dth_driver ON driver_team_history(driver_id);
CREATE INDEX idx_dth_team ON driver_team_history(team_id);
CREATE INDEX idx_dth_dates ON driver_team_history(start_date, end_date);

-- ============================================
-- RESULTS
-- ============================================
CREATE TABLE results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    driver_id UUID NOT NULL REFERENCES drivers(id),
    team_id UUID REFERENCES teams(id),
    
    -- Position data
    position INTEGER,
    position_text VARCHAR(10),  -- '1', 'DNF', 'DSQ', 'DNS', 'WD'
    grid_position INTEGER,
    positions_gained INTEGER GENERATED ALWAYS AS (
        CASE WHEN grid_position IS NOT NULL AND position IS NOT NULL 
             THEN grid_position - position 
             ELSE NULL 
        END
    ) STORED,
    
    -- Timing
    time_ms BIGINT,  -- Race time in milliseconds
    time_text VARCHAR(50),  -- Formatted time string
    gap_to_leader_ms BIGINT,
    gap_to_ahead_ms BIGINT,
    
    -- Race stats
    laps_completed INTEGER,
    points DECIMAL(6,2) DEFAULT 0,
    
    -- Status
    status VARCHAR(50) DEFAULT 'finished',  -- finished, dnf, dsq, dns
    status_detail VARCHAR(200),  -- 'Engine failure', 'Collision', etc.
    
    -- Car info
    car_number VARCHAR(10),
    
    -- Fastest lap
    fastest_lap_rank INTEGER,
    fastest_lap_time_ms BIGINT,
    fastest_lap_number INTEGER,
    avg_speed_kph DECIMAL(8,3),
    
    -- Series-specific extras (NASCAR stages, IMSA classes, etc.)
    extra_data JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(session_id, driver_id)
);

CREATE INDEX idx_results_session ON results(session_id);
CREATE INDEX idx_results_driver ON results(driver_id);
CREATE INDEX idx_results_team ON results(team_id);
CREATE INDEX idx_results_position ON results(position);

-- ============================================
-- STANDINGS SNAPSHOTS
-- ============================================
CREATE TABLE standings_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    series_id UUID NOT NULL REFERENCES series(id),
    season INTEGER NOT NULL,
    after_round INTEGER NOT NULL,
    type VARCHAR(20) NOT NULL,  -- 'driver', 'team', 'constructor', 'manufacturer'
    
    -- The entity (either driver or team)
    driver_id UUID REFERENCES drivers(id),
    team_id UUID REFERENCES teams(id),
    
    -- Standing data
    position INTEGER NOT NULL,
    points DECIMAL(8,2) NOT NULL DEFAULT 0,
    wins INTEGER DEFAULT 0,
    podiums INTEGER DEFAULT 0,
    poles INTEGER DEFAULT 0,
    fastest_laps INTEGER DEFAULT 0,
    dnfs INTEGER DEFAULT 0,
    
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Ensure either driver_id OR team_id is set, not both
    CONSTRAINT standings_entity_check CHECK (
        (type IN ('driver') AND driver_id IS NOT NULL AND team_id IS NULL) OR
        (type IN ('team', 'constructor', 'manufacturer') AND team_id IS NOT NULL)
    ),
    
    UNIQUE(series_id, season, after_round, type, driver_id, team_id)
);

CREATE INDEX idx_standings_series_season ON standings_snapshots(series_id, season);
CREATE INDEX idx_standings_driver ON standings_snapshots(driver_id) WHERE driver_id IS NOT NULL;
CREATE INDEX idx_standings_team ON standings_snapshots(team_id) WHERE team_id IS NOT NULL;

-- ============================================
-- LAP TIMES (Optional - high volume)
-- ============================================
CREATE TABLE lap_times (
    id BIGSERIAL PRIMARY KEY,  -- Use BIGSERIAL for high-volume table
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    driver_id UUID NOT NULL REFERENCES drivers(id),
    lap_number INTEGER NOT NULL,
    
    -- Timing
    time_ms INTEGER NOT NULL,
    sector_1_ms INTEGER,
    sector_2_ms INTEGER,
    sector_3_ms INTEGER,
    
    -- Context
    position INTEGER,
    gap_to_leader_ms INTEGER,
    compound VARCHAR(20),  -- 'soft', 'medium', 'hard', 'intermediate', 'wet'
    tyre_life INTEGER,  -- Laps on current set
    pit_in_lap BOOLEAN DEFAULT false,
    pit_out_lap BOOLEAN DEFAULT false,
    personal_best BOOLEAN DEFAULT false,
    overall_best BOOLEAN DEFAULT false,
    
    -- Don't need timestamps for lap data
    UNIQUE(session_id, driver_id, lap_number)
);

-- Partition by session for better performance (optional)
CREATE INDEX idx_laptimes_session_driver ON lap_times(session_id, driver_id);
CREATE INDEX idx_laptimes_session_lap ON lap_times(session_id, lap_number);

-- ============================================
-- HELPER VIEWS
-- ============================================

-- Race results with driver and team names
CREATE VIEW v_race_results AS
SELECT 
    r.id as result_id,
    ra.season,
    ra.round,
    ra.name as race_name,
    ra.date as race_date,
    s.code as series_code,
    s.name as series_name,
    t.name as track_name,
    t.country as track_country,
    se.type as session_type,
    d.full_name as driver_name,
    d.code as driver_code,
    d.nationality as driver_nationality,
    te.name as team_name,
    r.position,
    r.position_text,
    r.grid_position,
    r.positions_gained,
    r.points,
    r.laps_completed,
    r.time_text,
    r.status,
    r.status_detail,
    r.fastest_lap_rank,
    r.fastest_lap_time_ms,
    r.car_number
FROM results r
JOIN sessions se ON r.session_id = se.id
JOIN races ra ON se.race_id = ra.id
JOIN series s ON ra.series_id = s.id
LEFT JOIN tracks t ON ra.track_id = t.id
JOIN drivers d ON r.driver_id = d.id
LEFT JOIN teams te ON r.team_id = te.id;

-- Current championship standings
CREATE VIEW v_current_standings AS
SELECT DISTINCT ON (ss.series_id, ss.type, COALESCE(ss.driver_id, ss.team_id))
    ss.*,
    s.code as series_code,
    s.name as series_name,
    d.full_name as driver_name,
    d.code as driver_code,
    t.name as team_name
FROM standings_snapshots ss
JOIN series s ON ss.series_id = s.id
LEFT JOIN drivers d ON ss.driver_id = d.id
LEFT JOIN teams t ON ss.team_id = t.id
ORDER BY ss.series_id, ss.type, COALESCE(ss.driver_id, ss.team_id), ss.after_round DESC;

-- ============================================
-- RLS POLICIES (for future user features)
-- ============================================
-- Enable RLS on tables that might have user data in the future
-- For now, all data is public read

ALTER TABLE series ENABLE ROW LEVEL SECURITY;
ALTER TABLE tracks ENABLE ROW LEVEL SECURITY;
ALTER TABLE races ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE results ENABLE ROW LEVEL SECURITY;
ALTER TABLE drivers ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE standings_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE lap_times ENABLE ROW LEVEL SECURITY;

-- Public read access
CREATE POLICY "Public read access" ON series FOR SELECT USING (true);
CREATE POLICY "Public read access" ON tracks FOR SELECT USING (true);
CREATE POLICY "Public read access" ON races FOR SELECT USING (true);
CREATE POLICY "Public read access" ON sessions FOR SELECT USING (true);
CREATE POLICY "Public read access" ON results FOR SELECT USING (true);
CREATE POLICY "Public read access" ON drivers FOR SELECT USING (true);
CREATE POLICY "Public read access" ON teams FOR SELECT USING (true);
CREATE POLICY "Public read access" ON standings_snapshots FOR SELECT USING (true);
CREATE POLICY "Public read access" ON lap_times FOR SELECT USING (true);

-- ============================================
-- UPDATED_AT TRIGGER
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_series_updated_at BEFORE UPDATE ON series
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_tracks_updated_at BEFORE UPDATE ON tracks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_races_updated_at BEFORE UPDATE ON races
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_results_updated_at BEFORE UPDATE ON results
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_drivers_updated_at BEFORE UPDATE ON drivers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

---

## 3. Data Sources & Backfill Strategy

### 3.1 Formula 1

| Source | Data Type | Status | Notes |
|--------|-----------|--------|-------|
| **Ergast API** | Historical (1950-2024) | ⚠️ SUNSETTING 2024 | **PRIORITY: Archive immediately** |
| **OpenF1 API** | Live + Recent | ✅ Active | Free, real-time data from 2023+ |
| **Jolpica F1 API** | Historical | ✅ Active | Community Ergast replacement |
| **FastF1 Python** | Telemetry | ✅ Active | Lap times, telemetry, tire data |

**Backfill Priority:**
1. 🔴 **URGENT:** Download entire Ergast database NOW (shutting down)
2. 🟡 Use Jolpica to fill gaps and verify
3. 🟢 OpenF1 for 2023+ live data enrichment

**Ergast Archive Script:**
```python
# api/backfill/ergast_archive.py
import requests
import json
from datetime import datetime

ERGAST_BASE = "http://ergast.com/api/f1"

def archive_season(year: int):
    """Archive all data for a season."""
    endpoints = [
        f"/{year}.json?limit=1000",  # Season races
        f"/{year}/drivers.json?limit=1000",
        f"/{year}/constructors.json?limit=1000",
        f"/{year}/driverStandings.json?limit=1000",
        f"/{year}/constructorStandings.json?limit=1000",
    ]
    
    data = {"year": year, "archived_at": datetime.now().isoformat()}
    
    for endpoint in endpoints:
        resp = requests.get(f"{ERGAST_BASE}{endpoint}")
        key = endpoint.split("/")[-1].split(".")[0]
        data[key] = resp.json()
    
    # Get results for each race
    races = data.get(str(year), {}).get("MRData", {}).get("RaceTable", {}).get("Races", [])
    data["race_results"] = []
    
    for race in races:
        round_num = race["round"]
        resp = requests.get(f"{ERGAST_BASE}/{year}/{round_num}/results.json?limit=100")
        data["race_results"].append(resp.json())
        
        # Qualifying
        resp = requests.get(f"{ERGAST_BASE}/{year}/{round_num}/qualifying.json?limit=100")
        data.setdefault("qualifying", []).append(resp.json())
        
        # Lap times (limited)
        resp = requests.get(f"{ERGAST_BASE}/{year}/{round_num}/laps.json?limit=2000")
        data.setdefault("laps", []).append(resp.json())
    
    # Save to file
    with open(f"archive/ergast_f1_{year}.json", "w") as f:
        json.dump(data, f, indent=2)
    
    return data

# Archive 1950-2024
for year in range(1950, 2025):
    print(f"Archiving {year}...")
    archive_season(year)
```

### 3.2 NASCAR

| Source | Data Type | Status | Notes |
|--------|-----------|--------|-------|
| **cf.nascar.com** | Schedule + Live | ✅ Active | Already integrated in GridView |
| **Racing-Reference** | Historical | ✅ Active | Comprehensive back to 1949 |
| **NASCAR Media** | Official stats | 🔒 Auth required | For verified data |

**Backfill Approach:**
- Use existing NASCAR API for 2020+
- Scrape Racing-Reference for historical (with rate limiting)
- NASCAR has ~36 races/year × 40 drivers = ~1,440 results/year

### 3.3 IndyCar

| Source | Data Type | Status | Notes |
|--------|-----------|--------|-------|
| **IndyCar.com/Results** | Official results | ⚠️ Scraping only | No public API |
| **Timing71** | Live timing | ✅ Active | WebSocket during races |
| **ChampCar Stats** | Historical | ✅ Active | Fan-maintained archive |

**Backfill Approach:**
- Manual entry for key historical data (Indy 500 winners, champions)
- Scrape indycar.com/Results with polite delays
- ~17 races/year × 27 drivers

### 3.4 IMSA & WEC

| Source | Data Type | Status | Notes |
|--------|-----------|--------|-------|
| **Alkamelsystems** | Live + Results | ✅ Active | Already integrated |
| **fiawec.alkamelsystems.com** | WEC results | ✅ Active | Same format |
| **IMSA.com** | Schedule | ✅ Active | For metadata |

**Backfill Approach:**
- Alkamelsystems keeps ~2 years of results accessible
- Archive JSONs as they become available
- Multi-class handling: store class in `extra_data` JSONB

### 3.5 MotoGP

| Source | Data Type | Status | Notes |
|--------|-----------|--------|-------|
| **motogp.com API** | Official | 🔒 Undocumented | Reverse-engineered endpoints |
| **MotoGP Stats** | Historical | ✅ Active | Back to 1949 |

**Backfill Approach:**
- Their API is undocumented but functional
- `/api/results/` endpoints for recent data
- Historical from fan databases

### 3.6 WRC

| Source | Data Type | Status | Notes |
|--------|-----------|--------|-------|
| **wrc.com** | Official | ⚠️ Limited API | Basic results |
| **eWRC-results.com** | Historical | ✅ Active | Comprehensive archive |
| **Rally timing** | Live splits | ✅ Active | Stage times |

---

## 4. API Endpoints Design

### 4.1 Endpoint Structure

```
/api/history/
├── races                    # List/search races
├── races/{id}               # Single race details
├── races/{id}/results       # Race results
├── results/{id}             # Single result detail
├── drivers                  # List/search drivers
├── drivers/{id}             # Driver profile
├── drivers/{id}/stats       # Career statistics
├── drivers/{id}/results     # All results for driver
├── teams                    # List/search teams
├── teams/{id}               # Team profile
├── teams/{id}/stats         # Team statistics
├── standings                # Current standings
├── standings/history        # Standings over time
└── search                   # Full-text search
```

### 4.2 Detailed Specifications

#### GET /api/history/races

List and filter races.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `series` | string | Filter by series code (f1, nascar_cup, etc.) |
| `year` | integer | Filter by season |
| `track` | string | Filter by track name (partial match) |
| `country` | string | Filter by country code |
| `from` | date | Races after this date |
| `to` | date | Races before this date |
| `status` | string | scheduled, completed, cancelled |
| `limit` | integer | Max results (default 50, max 100) |
| `offset` | integer | Pagination offset |

**Response:**
```json
{
  "data": [
    {
      "id": "uuid",
      "series": {"code": "f1", "name": "Formula 1"},
      "season": 2024,
      "round": 1,
      "name": "Bahrain Grand Prix",
      "date": "2024-03-02",
      "track": {
        "name": "Bahrain International Circuit",
        "country": "Bahrain",
        "city": "Sakhir"
      },
      "status": "completed",
      "winner": {
        "driver": "Max Verstappen",
        "team": "Red Bull Racing"
      }
    }
  ],
  "pagination": {
    "total": 450,
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

#### GET /api/history/races/{id}/results

Get full results for a race.

**Response:**
```json
{
  "race": {
    "id": "uuid",
    "name": "Bahrain Grand Prix",
    "date": "2024-03-02",
    "series": "f1",
    "track": "Bahrain International Circuit",
    "laps": 57
  },
  "results": [
    {
      "position": 1,
      "driver": {
        "id": "uuid",
        "name": "Max Verstappen",
        "code": "VER",
        "nationality": "Netherlands"
      },
      "team": {
        "id": "uuid",
        "name": "Red Bull Racing"
      },
      "car_number": "1",
      "grid": 1,
      "positions_gained": 0,
      "laps": 57,
      "time": "1:31:44.742",
      "time_ms": 5504742,
      "points": 25,
      "status": "finished",
      "fastest_lap": {
        "rank": 1,
        "lap": 44,
        "time": "1:32.608"
      }
    }
  ],
  "fastest_lap": {
    "driver": "Max Verstappen",
    "time": "1:32.608",
    "lap": 44
  }
}
```

#### GET /api/history/drivers/{id}/stats

Get career statistics for a driver.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `series` | string | Filter stats by series |
| `from_year` | integer | Start year |
| `to_year` | integer | End year |

**Response:**
```json
{
  "driver": {
    "id": "uuid",
    "name": "Max Verstappen",
    "code": "VER",
    "nationality": "Netherlands",
    "date_of_birth": "1997-09-30",
    "photo_url": "..."
  },
  "career_stats": {
    "races_entered": 185,
    "wins": 54,
    "podiums": 98,
    "poles": 35,
    "fastest_laps": 29,
    "points": 2586.5,
    "championships": 3,
    "first_race": {
      "date": "2015-03-15",
      "race": "Australian Grand Prix",
      "team": "Toro Rosso"
    },
    "first_win": {
      "date": "2016-05-15",
      "race": "Spanish Grand Prix",
      "team": "Red Bull Racing"
    }
  },
  "by_season": [
    {
      "season": 2024,
      "series": "f1",
      "team": "Red Bull Racing",
      "position": 1,
      "points": 575,
      "wins": 19,
      "podiums": 21,
      "poles": 12
    }
  ],
  "by_track": [
    {
      "track": "Circuit de Spa-Francorchamps",
      "races": 8,
      "wins": 4,
      "podiums": 6,
      "best_finish": 1,
      "avg_finish": 2.3
    }
  ]
}
```

#### GET /api/history/standings

Get current or historical standings.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `series` | string | Series code (required) |
| `year` | integer | Season (default: current) |
| `type` | string | driver or team/constructor |
| `after_round` | integer | Standings after specific round |

**Response:**
```json
{
  "series": "f1",
  "season": 2024,
  "type": "driver",
  "after_round": 22,
  "standings": [
    {
      "position": 1,
      "driver": {
        "id": "uuid",
        "name": "Max Verstappen",
        "code": "VER"
      },
      "team": "Red Bull Racing",
      "points": 575,
      "wins": 19,
      "podiums": 21,
      "change_from_last": 0
    }
  ]
}
```

#### GET /api/history/standings/history

Get standings progression over a season.

**Response:**
```json
{
  "series": "f1",
  "season": 2024,
  "type": "driver",
  "progression": [
    {
      "after_round": 1,
      "date": "2024-03-02",
      "standings": [
        {"position": 1, "driver_code": "VER", "points": 25},
        {"position": 2, "driver_code": "PER", "points": 18}
      ]
    },
    {
      "after_round": 2,
      "date": "2024-03-09",
      "standings": [
        {"position": 1, "driver_code": "VER", "points": 50}
      ]
    }
  ]
}
```

### 4.3 Supabase Implementation

With Supabase's PostgREST, most endpoints work automatically:

```javascript
// api/history/races.js (Vercel serverless function)
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_ANON_KEY
);

export default async function handler(req, res) {
  const { series, year, limit = 50, offset = 0 } = req.query;
  
  let query = supabase
    .from('races')
    .select(`
      *,
      series:series_id (code, name, color),
      track:track_id (name, country, city),
      sessions!inner (
        results (
          position,
          driver:driver_id (full_name, code),
          team:team_id (name)
        )
      )
    `)
    .order('date', { ascending: false })
    .range(offset, offset + limit - 1);
  
  if (series) {
    query = query.eq('series.code', series);
  }
  if (year) {
    query = query.eq('season', year);
  }
  
  const { data, error, count } = await query;
  
  if (error) {
    return res.status(500).json({ error: error.message });
  }
  
  // Transform to API format
  const races = data.map(race => ({
    id: race.id,
    series: race.series,
    season: race.season,
    round: race.round,
    name: race.name,
    date: race.date,
    track: race.track,
    status: race.status,
    winner: race.sessions?.[0]?.results?.find(r => r.position === 1)
  }));
  
  return res.status(200).json({
    data: races,
    pagination: { total: count, limit, offset, has_more: offset + limit < count }
  });
}
```

---

## 5. Setup Instructions

### 5.1 Supabase Project Setup

1. **Create Project:**
   - Go to [supabase.com](https://supabase.com)
   - Create new project: `gridview-history`
   - Choose region closest to users (US West for now)
   - Save the project URL and anon key

2. **Run Schema:**
   - Go to SQL Editor in Supabase dashboard
   - Copy the entire SQL schema from Section 2
   - Execute

3. **Configure Environment:**
   ```bash
   # Add to .env.local
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your-anon-key
   SUPABASE_SERVICE_KEY=your-service-key  # For backfill scripts only
   ```

4. **Install Supabase Client:**
   ```bash
   npm install @supabase/supabase-js
   ```

### 5.2 Backfill Execution Order

```bash
# 1. Set up Python environment for backfill scripts
cd api/backfill
python -m venv venv
source venv/bin/activate
pip install requests supabase python-dateutil

# 2. Archive Ergast IMMEDIATELY (it's shutting down!)
python ergast_archive.py  # Saves to archive/

# 3. Import F1 historical data
python import_f1.py --source archive/ergast_f1_*.json

# 4. Import NASCAR (uses live API)
python import_nascar.py --years 2020-2024

# 5. Import IMSA/WEC from Alkamelsystems archives
python import_alkamel.py --source archive/alkamel_*.json

# 6. Set up ongoing sync
# Add to Vercel cron or GitHub Action
```

### 5.3 Directory Structure

```
gridview/
├── api/
│   ├── history/
│   │   ├── races.py          # GET /api/history/races
│   │   ├── results.py        # GET /api/history/results
│   │   ├── drivers.py        # GET /api/history/drivers
│   │   ├── standings.py      # GET /api/history/standings
│   │   └── search.py         # GET /api/history/search
│   └── backfill/
│       ├── ergast_archive.py
│       ├── import_f1.py
│       ├── import_nascar.py
│       ├── import_alkamel.py
│       └── sync_live.py      # Ongoing updates
├── lib/
│   └── supabase.js           # Supabase client setup
└── archive/                  # Local backups of source data
    ├── ergast_f1_2024.json
    └── ...
```

---

## 6. Migration Path

### Phase 1: Foundation (Week 1)
- [ ] Create Supabase project
- [ ] Run schema migrations
- [ ] Archive Ergast data locally
- [ ] Import F1 historical data (2020-2024 first)

### Phase 2: Multi-Series (Week 2)  
- [ ] Import NASCAR data
- [ ] Import IMSA/WEC data
- [ ] Create API endpoints
- [ ] Add to existing GridView routes

### Phase 3: Deep History (Week 3-4)
- [ ] Import F1 1950-2019
- [ ] Import historical NASCAR
- [ ] Add standings progression
- [ ] Driver stats pages

### Phase 4: Advanced (Future)
- [ ] Lap times for F1 (requires Pro tier)
- [ ] Full-text search
- [ ] GraphQL endpoint option
- [ ] Caching layer (Redis)

---

## 7. Cost Projections

| Phase | Tier | Monthly Cost | Features |
|-------|------|--------------|----------|
| MVP | Free | $0 | 500MB, 50k API calls |
| Growth | Pro | $25 | 8GB, 3M API calls, daily backups |
| Scale | Pro + Add-ons | $50+ | Larger storage, more compute |

**Break-even:** Free tier handles ~100 users with light usage. Pro tier recommended once traffic exceeds 1000 daily active users.

---

## 8. Future Considerations

### 8.1 Caching Strategy
- Cache driver stats (change rarely)
- Cache race results (immutable after completion)
- Real-time for live sessions via Supabase Realtime

### 8.2 Search
- Postgres full-text search for driver/team names
- Consider Algolia/Meilisearch for advanced search later

### 8.3 Analytics Queries
Common expensive queries to optimize:
- Championship progression charts (pre-compute or materialize)
- Head-to-head driver comparisons
- Track statistics by driver

### 8.4 Data Quality
- Deduplication logic for drivers (same person, different series)
- Track name normalization
- Regular data validation jobs

---

## Summary

**Immediate Actions:**
1. 🔴 **Archive Ergast API data NOW** — it's shutting down
2. Create Supabase project
3. Run schema migration
4. Start F1 backfill

**Stack Decision:** Supabase (Postgres + REST API) is the clear winner for GridView's needs — free tier is sufficient for MVP, scales well, and the built-in REST API means faster development.

**Timeline:** MVP with F1 + NASCAR historical data in 2-3 weeks. Full multi-series coverage in 4-6 weeks.

---

*Report generated by Athena 🦉*  
*Questions? The schema is designed for flexibility — ask about specific use cases.*
