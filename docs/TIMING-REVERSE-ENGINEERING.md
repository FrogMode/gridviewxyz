# Live Timing Reverse Engineering Documentation

This document catalogs the live timing infrastructure for various racing series, including discovered endpoints, data formats, and scraping strategies.

## 📦 Implementation

All timing clients are implemented in `api/websocket_timing/`:

| Module | Series | Protocol | Status |
|--------|--------|----------|--------|
| `f1_signalr.py` | Formula 1 | SignalR 1.5 WebSocket | ✅ Working |
| `alkamelsystems.py` | IMSA, etc. | SockJS/Meteor DDP | ✅ Working |
| `nascar_feed.py` | NASCAR (all series) | JSON Polling | ✅ Working |
| `indycar_feed.py` | IndyCar, INDY NXT | JSON Polling | ✅ Working |

### Quick Start

```python
# F1 SignalR
from api.websocket_timing import F1SignalRClient
client = F1SignalRClient()
client.on_message = lambda topic, data: print(f"{topic}: {data}")
client.connect(topics=["TimingData", "LapCount"])

# IMSA Alkamelsystems
from api.websocket_timing import AlkamelSystemsClient
client = AlkamelSystemsClient(series="imsa")
client.on_document = lambda doc: print(f"{doc.collection}: {doc.fields}")
client.connect()
client.subscribe("timing")

# NASCAR Polling
from api.websocket_timing import NASCARLiveFeed
feed = NASCARLiveFeed()
state = feed.fetch_live_data(series_id=1, race_id=4792)

# IndyCar Polling
from api.websocket_timing import IndyCarLiveFeed
feed = IndyCarLiveFeed()
if feed.is_session_active():
    state = feed.fetch_timing_data()
```

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

### Live Timing WebSocket (SockJS/Meteor DDP)

Alkamelsystems uses Meteor.js with DDP (Distributed Data Protocol) for live timing:

**SockJS Info Endpoint:**
```
GET https://livetiming.alkamelsystems.com/sockjs/info
Response: {"websocket":true,"origins":["*:*"],"cookie_needed":false,"entropy":...}
```

**WebSocket Connection:**
```
wss://livetiming.alkamelsystems.com/sockjs/{3-digit}/{random-8-char}/websocket
```

**DDP Protocol Flow:**

1. Receive `o` (open frame)
2. Send connect:
   ```json
   {"msg":"connect","version":"1","support":["1","pre1","pre2"]}
   ```
3. Receive connected:
   ```json
   {"msg":"connected","session":"..."}
   ```
4. Subscribe to collections:
   ```json
   {"msg":"sub","id":"sub_1","name":"timing","params":[]}
   ```
5. Receive data:
   ```json
   {"msg":"added","collection":"timing","id":"doc_1","fields":{...}}
   {"msg":"changed","collection":"timing","id":"doc_1","fields":{...}}
   ```

**Available Collections:**
- `sessions` - Active timing sessions
- `participants` - Competitors/drivers
- `timing` - Live timing data
- `trackmap` - Track position data  
- `racecontrol` - Race control messages
- `weather` - Weather conditions
- `bestTimes` - Best lap times
- `cardata` - Car data

**SockJS Message Framing:**
- `o` - Open frame
- `h` - Heartbeat
- `c[code,"reason"]` - Close frame
- `a["json_string"]` - Array of messages (DDP wrapped in JSON string)

**Implementation:** See `api/websocket_timing/alkamelsystems.py`

### Reliability Notes
- **Stability:** HIGH for results archive
- **Rate Limiting:** None observed
- **Fragility:** MEDIUM - HTML structure may change
- **Coverage:** Historical results + live timing via WebSocket

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

### Live Feed Data Structure

```json
{
  "race_id": 4792,
  "race_name": "Coke Zero Sugar 400",
  "track_name": "Daytona Intl Speedway",
  "track_length": 2.5,
  "lap_number": 127,
  "laps_in_race": 160,
  "flag_state": 9,
  "elapsed_time": 8235,
  "number_of_caution_laps": 25,
  "number_of_lead_changes": 24,
  "stage": {"stage_num": 3, "finish_at_lap": 160},
  "vehicles": [
    {
      "running_position": 1,
      "vehicle_number": "77",
      "vehicle_manufacturer": "Chv",
      "driver": {"full_name": "Justin Haley"},
      "laps_completed": 127,
      "last_lap_speed": 71.214,
      "best_lap_speed": 201.189,
      "pit_stops": [...],
      "status": 1
    }
  ]
}
```

**Flag State Codes:**
- 1 = Green
- 2 = Yellow
- 3 = Red
- 4 = Checkered
- 5 = White
- 6 = Warm-up
- 8 = Pre-race
- 9 = Caution

**Implementation:** See `api/websocket_timing/nascar_feed.py`

### Reliability Notes
- **Stability:** HIGH
- **Rate Limiting:** Light caching recommended
- **Fragility:** LOW - Official API
- **Coverage:** Full schedule + live timing

---

## 🏎️ Formula 1 (SignalR Protocol)

### Discovery Summary
F1 uses Microsoft SignalR 1.5 protocol over WebSocket for live timing at `livetiming.formula1.com`.

**Note:** The public page returns 403 (subscription required), but the SignalR API itself is accessible!

### SignalR Connection Flow

1. **Negotiate** - Get connection token
   ```
   GET https://livetiming.formula1.com/signalr/negotiate
   Params: connectionData=[{"name":"Streaming"}]&clientProtocol=1.5
   ```
   
   Response:
   ```json
   {
     "ConnectionToken": "...",
     "ConnectionId": "uuid",
     "ProtocolVersion": "1.5",
     "TryWebSockets": true
   }
   ```

2. **Connect WebSocket**
   ```
   wss://livetiming.formula1.com/signalr/connect
   Params: connectionToken=...&connectionData=...&transport=webSockets
   ```

3. **Subscribe to Topics**
   ```json
   {"H":"Streaming","M":"Subscribe","A":[["TimingData","LapCount"]],"I":"1"}
   ```

4. **Receive Updates**
   ```json
   {"C":"msg_id","M":[{"H":"Streaming","M":"feed","A":["TimingData",{...}]}]}
   ```

### Available Topics

| Topic | Description | Format |
|-------|-------------|--------|
| `Heartbeat` | Server heartbeat | Timestamp |
| `CarData.z` | Car telemetry (RPM, speed, DRS, gear) | zlib compressed |
| `Position.z` | Car positions on track | zlib compressed |
| `TimingData` | Live timing (gaps, sectors, laps) | JSON |
| `TimingStats` | Timing statistics | JSON |
| `TimingAppData` | Extended timing data | JSON |
| `LapCount` | Current lap number | JSON |
| `SessionInfo` | Session metadata | JSON |
| `TrackStatus` | Track status (flags) | JSON |
| `RaceControlMessages` | Race control messages | JSON |
| `TeamRadio` | Team radio transcripts | JSON |
| `DriverList` | Driver information | JSON |
| `WeatherData` | Weather conditions | JSON |
| `SessionData` | Session configuration | JSON |
| `ExtrapolatedClock` | Estimated session clock | JSON |
| `TopThree` | Top 3 drivers | JSON |
| `ChampionshipPrediction` | Live championship calc | JSON |

### Data Decompression

Topics ending in `.z` contain zlib-compressed base64 data:

```python
import base64
import zlib

def decompress(data: str) -> dict:
    compressed = base64.b64decode(data)
    decompressed = zlib.decompress(compressed, -zlib.MAX_WBITS)
    return json.loads(decompressed.decode())
```

### Alternative: OpenF1 API

For easier access to F1 data, use [OpenF1](https://openf1.org/):

- **Historical data:** Free, no auth required
- **Real-time data:** Requires paid subscription
- **Endpoints:** REST API with JSON/CSV output

```python
# Get latest session car data
url = "https://api.openf1.org/v1/car_data?session_key=latest&driver_number=1"
```

### Implementation

See `api/websocket_timing/f1_signalr.py` for complete SignalR client.

### Reliability Notes
- **Stability:** HIGH - SignalR is reliable
- **Authentication:** None for API, subscription needed for web UI
- **Rate Limiting:** None observed
- **Coverage:** Full real-time timing during sessions

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
February 3, 2026

## 🔄 Recent Updates
- Added F1 SignalR WebSocket client (`api/websocket_timing/f1_signalr.py`)
- Added Alkamelsystems SockJS/DDP client (`api/websocket_timing/alkamelsystems.py`)
- Added NASCAR live feed client (`api/websocket_timing/nascar_feed.py`)
- Added IndyCar live feed client (`api/websocket_timing/indycar_feed.py`)
- Documented F1 SignalR protocol (negotiate, subscribe, data topics)
- Documented Alkamelsystems Meteor DDP protocol
- Added NASCAR flag state codes and data structure

## 🔍 Research Methods
- Browser DevTools network inspection
- JavaScript bundle analysis
- DNS/subdomain enumeration
- Direct endpoint testing
