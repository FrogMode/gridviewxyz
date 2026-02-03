# Live Timing Reverse Engineering Documentation

This document catalogs the live timing infrastructure for various racing series, including discovered endpoints, data formats, and scraping strategies.

---

## 🏎️ IndyCar (NTT INDYCAR Series)

### Discovery Summary
IndyCar's live timing system uses **Azure Blob Storage** with JSON polling (not WebSockets). The leaderboard app is a Next.js SPA hosted on Azure Static Web Apps.

**Live App:** `https://proud-island-0d704c910.4.azurestaticapps.net/`
**Embedded at:** `https://www.indycar.com/leaderboard`

### Data Endpoints

All endpoints are publicly accessible Azure Blob Storage URLs:

| Endpoint | Description | Update Frequency |
|----------|-------------|------------------|
| `https://indycar.blob.core.windows.net/racecontrol/tsconfig.json` | Config/session status | On change |
| `https://indycar.blob.core.windows.net/racecontrol/schedulefeed.json` | Full season schedule | Daily |
| `https://indycar.blob.core.windows.net/racecontrol/driversfeed.json` | Driver info & stats | Daily |
| `https://indycar.blob.core.windows.net/racecontrol/timingscoring-ris.json` | **LIVE timing/scoring** | ~1s during sessions |
| `https://indycar.blob.core.windows.net/racecontrol/trackactivityleaderboardfeed.json` | Current session leaderboard | ~1s during sessions |
| `https://indycar.blob.core.windows.net/ntt-data/INDYCAR_DATA_POLLING/data_polling_blob.json` | NTT pit stop predictions | During races |

**INDY NXT (support series):**
- `https://indycar.blob.core.windows.net/racecontrol/driversfeed_nxt.json`
- `https://indycar.blob.core.windows.net/racecontrol/schedulefeed_nxt.json`
- `https://indycar.blob.core.windows.net/racecontrol/trackactivityleaderboardfeed_nxt.json`

### Data Format Examples

**tsconfig.json (Session Status)**
```json
{
  "no_track_activity": true,  // false when session is live
  "timed_race": false,
  "rain_delay": false,
  "show_quick_insights": true,
  "alt_tire_color": "Red",
  "show_static_track_map": true,
  "doubleheader_race": false,
  "ways_to_watch": [...]
}
```

**timingscoring-ris.json (Live Timing)**
```json
{
  "timing_results": {
    "heartbeat": {
      "SessionStatus": "GREEN|YELLOW|RED|WARM|COLD",
      "LapNumber": 45,
      "TimeRemaining": "00:45:32",
      ...
    },
    "entries": [
      {
        "Position": 1,
        "Number": "10",
        "Driver": "Alex Palou",
        "Team": "Chip Ganassi Racing",
        "LastLap": "01:01.234",
        "BestLap": "01:00.987",
        "Gap": "",
        "PitStops": 2,
        ...
      }
    ]
  }
}
```

**schedulefeed.json (Schedule)**
```json
{
  "schedule": {
    "race": [
      {
        "seriesid": "55",
        "eventid": "5515",
        "name": "Firestone Grand Prix of St. Petersburg",
        "city": "St. Petersburg",
        "state": "Florida",
        "laps": "100",
        "track_length": "1.8",
        "green_flag": "2026-03-01 17:00:00",
        "broadcasts": {...},
        "past_winners": {...}
      }
    ]
  }
}
```

### Scraping Strategy

```python
import urllib.request
import json

INDYCAR_BASE = "https://indycar.blob.core.windows.net/racecontrol"

def fetch_json(endpoint: str) -> dict:
    """Fetch JSON from IndyCar blob storage."""
    url = f"{INDYCAR_BASE}/{endpoint}?{int(time.time())}"  # Cache bust
    req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def is_session_active() -> bool:
    """Check if a session is currently active."""
    config = fetch_json("tsconfig.json")
    return not config.get("no_track_activity", True)

def get_live_standings() -> list:
    """Get current session standings."""
    data = fetch_json("timingscoring-ris.json")
    return data.get("timing_results", {}).get("entries", [])
```

### Reliability Notes
- **Stability:** HIGH - Azure Blob Storage is very reliable
- **Rate Limiting:** None observed (use reasonable polling intervals)
- **Fragility:** LOW - Endpoint structure has been stable since 2024
- **Coverage:** LIVE sessions + historical schedule/results

---

## 🏁 IMSA (WeatherTech SportsCar Championship)

### Discovery Summary
IMSA uses **Alkamelsystems** for timing, with a public results archive and live timing.

**Results Archive:** `https://imsa.results.alkamelcloud.com/`
**Live Timing:** `http://livetiming.alkamelsystems.com/imsa`

### Data Access
- Results are available as static JSON files
- Live timing uses a Meteor.js SPA with real-time subscriptions (harder to scrape)

### Results JSON Structure
```
Results/{year_code}_{year}/{event_num}_{venue}/{series}/{session}/{document}.JSON
```

Example:
```
Results/26_2026/03_Daytona%20International%20Speedway/01_IMSA%20WeatherTech/202601241340_Race/03_Results_Race.JSON
```

### Available Documents
- `03_Results_*.JSON` - Classification
- `05_Results by Class_*.JSON` - Class-based results
- `13_Best Sector Times_*.JSON` - Sector analysis
- `17_FastestLapSequence_*.JSON` - Fastest lap progression
- `23_Time Cards_*.JSON` - Detailed timing
- `26_Weather_*.JSON` - Weather conditions

### Scraping Strategy
See `api/_alkamel.py` for the complete implementation.

### Reliability Notes
- **Stability:** HIGH for results archive
- **Rate Limiting:** None observed
- **Fragility:** MEDIUM - HTML structure may change
- **Coverage:** Historical results (live requires more complex scraping)

---

## 🌐 FIA WEC / ELMS / Asian Le Mans

### Discovery Summary
These series also use Alkamelsystems but with a **premium/backoffice paywall**.

**URLs Discovered:**
- `https://fiawec.results.alkamelcloud.com/` → Redirects to backoffice login
- `https://elms.results.alkamelcloud.com/` → Redirects to backoffice login
- `https://alms.results.alkamelcloud.com/` → Redirects to backoffice login

### Access Status
❌ **NOT PUBLICLY ACCESSIBLE** - Requires premium subscription

### Alternative Data Sources
- FIA WEC: TheSportsDB API (limited data) - see `api/wec.py`
- ELMS/ALMS: No known public API

---

## 🏎️ NASCAR

### Discovery Summary
NASCAR has a well-documented public API with JSON feeds.

**Base URL:** `https://cf.nascar.com`

### Data Endpoints

| Endpoint | Description |
|----------|-------------|
| `/cacher/{year}/race_list_basic.json` | Season schedule |
| `/cacher/{year}/{series_id}/race_list_basic.json` | Series-specific schedule |
| `/live/feeds/series_{series_id}/{race_id}/live_feed.json` | Live race data |

**Series IDs:**
- 1 = Cup Series
- 2 = Xfinity Series  
- 3 = Craftsman Truck Series

### Reliability Notes
- **Stability:** HIGH
- **Rate Limiting:** Light caching recommended
- **Fragility:** LOW - Official API
- **Coverage:** Full schedule + live timing

---

## 🌍 Formula E

### Discovery Summary
Formula E does NOT use Alkamelsystems. Their timing system is proprietary.

**Attempted URLs (all failed):**
- `https://fe.results.alkamelcloud.com/` - Does not exist
- `https://fiaformulae.results.alkamelcloud.com/` - 404

### Known Timing Infrastructure
- Live timing is embedded in their website/app
- Uses WebSocket-based real-time updates
- No known public API

### Research Needed
- Capture network traffic during live session
- Identify WebSocket endpoints
- Reverse-engineer message format

---

## 🏍️ MotoGP

### Discovery Summary
MotoGP has a JSON-based live timing system.

**API Base:** `https://api.motogp.com`

See `api/motogp.py` for implementation details.

---

## 📡 Live Timing Technologies

### Polling-Based (Easier to Scrape)
- **IndyCar** - Azure Blob Storage JSON (1s updates)
- **NASCAR** - Static JSON feeds
- **IMSA** - Static result files

### WebSocket-Based (Harder to Scrape)
- **Formula 1** - SignalR (covered by OpenF1 API)
- **Formula E** - Unknown WebSocket protocol
- **Alkamelsystems Live** - Meteor.js DDP

### Meteor.js (Alkamelsystems Live Timing)

Alkamelsystems uses Meteor.js with DDP (Distributed Data Protocol) for live timing:

```javascript
// Connection (conceptual)
const socket = new WebSocket('wss://livetiming.alkamelsystems.com/websocket');

// DDP Handshake
socket.send(JSON.stringify({
  msg: 'connect',
  version: '1',
  support: ['1', 'pre1', 'pre2']
}));

// Subscribe to data
socket.send(JSON.stringify({
  msg: 'sub',
  id: 'unique-id',
  name: 'collection-name',
  params: []
}));
```

---

## 🔧 Proof of Concept: IndyCar Live Scraper

See `api/indycar_live.py` for a working implementation that:
1. Fetches session status from tsconfig.json
2. Polls live timing data during active sessions
3. Provides formatted standings/timing data

---

## ⚠️ Legal & Ethical Considerations

1. **Terms of Service:** Check each series' ToS before scraping
2. **Rate Limiting:** Be respectful with request frequency
3. **Attribution:** Give credit to data sources
4. **Commercial Use:** May require licensing agreements

---

## 📅 Last Updated
February 2026

## 🔍 Research Methods
- Browser DevTools network inspection
- JavaScript bundle analysis
- DNS/subdomain enumeration
- Direct endpoint testing
