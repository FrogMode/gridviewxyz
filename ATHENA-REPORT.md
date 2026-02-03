# Athena Research Report: GridView Expansion

**Date:** February 2, 2025  
**Mission:** Improve GridView with missing series and resilience  
**Status:** ✅ Complete

---

## Executive Summary

I've successfully researched data sources, implemented new API endpoints for NASCAR, MotoGP, and IndyCar, added caching/resilience infrastructure, and created a comprehensive push notification design document.

### Deliverables

| Item | Status | Files |
|------|--------|-------|
| NASCAR API | ✅ Complete | `api/nascar.py` |
| MotoGP API | ✅ Complete | `api/motogp.py` |
| IndyCar API | ✅ Complete | `api/indycar.py` |
| Caching Layer | ✅ Complete | `api/_utils.py` |
| Health Dashboard | ✅ Updated | `api/health.py` |
| Push Notifications | ✅ Design Doc | `docs/PUSH-NOTIFICATIONS.md` |

---

## 1. Data Source Research

### NASCAR ⭐ Excellent

**Source:** `cf.nascar.com` (NASCAR's official CDN)

**Discovered Endpoints:**
```
https://cf.nascar.com/cacher/{year}/race_list_basic.json        # All series schedule
https://cf.nascar.com/cacher/{year}/{series}/race_list_basic.json  # Series-specific
https://cf.nascar.com/live/feeds/series_{id}/{race_id}/live_feed.json  # Live/results
https://cf.nascar.com/cacher/drivers.json                       # Driver database
```

**Series IDs:**
- 1 = NASCAR Cup Series
- 2 = NASCAR Xfinity Series
- 3 = NASCAR Craftsman Truck Series

**Data Quality:** Excellent - includes schedules, live timing, full race results, driver info, stage results, and TV broadcast info.

**Rate Limits:** None observed, but implemented conservative caching (5 min TTL).

### MotoGP ✅ Good

**Source:** TheSportsDB API (League ID: 4407)

**Endpoint:**
```
https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id=4407&s={year}
```

**Data Quality:** Good - includes calendar, race results embedded in `strResult` field, standings after each race, venue info, and video links.

**Limitations:**
- Results are in a text format requiring parsing
- No live timing data
- Free tier API (may have rate limits)

### IndyCar ⚠️ Limited

**Findings:**
- No public API discovered
- Official site uses a proprietary timing system
- TheSportsDB does not have IndyCar data
- racecontrol.indycar.com redirects to leaderboard page

**Solution Implemented:**
- Static 2025 schedule with manual updates
- Links to official IndyCar.com pages for results/standings
- Notes about data source limitations

**Future Options:**
1. Web scraping of indycar.com (fragile)
2. Partnership/API access request
3. Community-maintained data source

### Other Series Researched

| Series | Source | League ID | Status |
|--------|--------|-----------|--------|
| WEC | TheSportsDB | 4413 | Already implemented |
| WRC | TheSportsDB | 4409 | Already implemented |
| F1 | OpenF1 | - | Already implemented |
| Super GT | TheSportsDB | 4412 | Available if needed |
| British GT | TheSportsDB | 4410 | Available if needed |

---

## 2. API Implementations

### NASCAR API (`/api/nascar`)

**Features:**
- Full schedule for Cup, Xfinity, and Truck series
- Detailed race results with positions, gaps, laps led
- Upcoming races endpoint
- Recent results endpoint
- Year and series filtering

**Usage:**
```
GET /api/nascar                      # Full 2025 schedule
GET /api/nascar?series=cup           # Cup Series only
GET /api/nascar?series=cup&upcoming  # Upcoming Cup races
GET /api/nascar?series=cup&results   # Recent Cup results
GET /api/nascar?series=1&race=5543   # Specific race results
```

**Response Example:**
```json
{
  "series": "NASCAR Cup Series",
  "season": 2025,
  "events": [
    {
      "race_id": 5543,
      "name": "Cook Out Clash at Bowman Gray",
      "track": "Bowman Gray Stadium",
      "date": "2025-02-02T20:00:00",
      "tv": "FOX",
      "winner_id": 4062
    }
  ]
}
```

### MotoGP API (`/api/motogp`)

**Features:**
- Season calendar with race details
- Parsed race results (from text format)
- Championship standings after each race
- Event details with venue, description, video links

**Usage:**
```
GET /api/motogp                  # 2025 calendar
GET /api/motogp?upcoming         # Upcoming races
GET /api/motogp?results          # Recent race results
GET /api/motogp?event=2218265    # Specific event details
```

### IndyCar API (`/api/indycar`)

**Features:**
- 2025 schedule with all 20 races
- Track type classification (street, road, oval)
- Links to official IndyCar.com pages
- Featured event endpoint (Indianapolis 500)

**Usage:**
```
GET /api/indycar                 # 2025 schedule
GET /api/indycar?upcoming        # Upcoming races
GET /api/indycar?featured        # Indianapolis 500 info
```

**Note:** Results/standings link to indycar.com due to API limitations.

---

## 3. Resilience Improvements

### Caching Layer (`api/_utils.py`)

**Features:**
- In-memory cache with configurable TTL
- Automatic cache hit/miss tracking
- Retry logic with exponential backoff
- Rate limiter for external APIs
- Cache statistics for monitoring

**Usage:**
```python
from api._utils import cached_fetch, get_cache_stats

data = cached_fetch(url, ttl=300, retries=2)
stats = get_cache_stats()  # {"hits": 45, "misses": 12, "hit_rate": 78.9}
```

### Health Dashboard (`/api/health`)

**Features:**
- Simple health check (default)
- Deep health check with external API status
- Cache statistics
- Endpoint listing with documentation

**Usage:**
```
GET /api/health          # Simple status
GET /api/health?deep     # Full diagnostics including external API checks
```

**Response Example (deep):**
```json
{
  "status": "healthy",
  "version": "0.3.0",
  "data_sources": {
    "nascar": {"status": "ok", "latency_ms": 234},
    "sportsdb_motogp": {"status": "ok", "latency_ms": 189}
  },
  "cache": {
    "hits": 145,
    "misses": 23,
    "hit_rate": 86.3
  }
}
```

---

## 4. Push Notification Design

Full design document created at `docs/PUSH-NOTIFICATIONS.md`.

### Key Points:

**Architecture:**
- Service Worker for background notification handling
- Web Push API (VAPID authentication)
- Vercel KV for subscription storage
- Vercel Cron for scheduled notification delivery

**Timeline:**
- Week 1: PWA foundation (manifest, service worker)
- Week 2: Subscription management API
- Week 3: Notification delivery system
- Week 4: User preferences UI
- Week 5: Beta release

**Notification Types:**
- Race start alerts (15 min, 1 hour before)
- Results available
- Session reminders (practice, qualifying)

**Cost:** Free tier sufficient for ~1K users

---

## 5. Recommendations

### Immediate Actions

1. **Deploy and Test:** Deploy to Vercel staging, test all new endpoints
2. **Frontend Integration:** Add NASCAR, MotoGP, IndyCar cards to dashboard
3. **Cache Tuning:** Monitor cache hit rates, adjust TTLs based on usage

### Short-Term (1-2 weeks)

1. **IndyCar Scraping:** Evaluate scraping indycar.com/schedule for live data
2. **Error Alerting:** Add error monitoring (Sentry, Vercel Analytics)
3. **Mobile UI:** Optimize new series cards for mobile

### Medium-Term (1 month)

1. **Push Notifications:** Implement Phase 1-2 of push notification plan
2. **Super GT/British GT:** Add Asian/European GT series if user demand
3. **Historical Data:** Add past season results for comparison

### Data Source Improvements

| Series | Current | Ideal |
|--------|---------|-------|
| NASCAR | Excellent (public API) | Add standings API if available |
| MotoGP | Good (TheSportsDB) | Official MotoGP API if accessible |
| IndyCar | Limited (static) | API partnership or reliable scraping |
| WEC | Good (TheSportsDB) | Live timing integration |
| IMSA | Good (Alkamelsystems) | More reliable parsing |

---

## 6. Files Changed/Created

### New Files
- `api/nascar.py` - NASCAR API endpoint
- `api/motogp.py` - MotoGP API endpoint
- `api/indycar.py` - IndyCar API endpoint
- `api/_utils.py` - Shared caching and utilities
- `docs/PUSH-NOTIFICATIONS.md` - Push notification design

### Modified Files
- `api/health.py` - Enhanced health dashboard

### Branch
All changes are on branch: `feature/expanded-series`

---

## 7. Testing Notes

**Manual Testing Performed:**
- ✅ NASCAR schedule fetch (2025, all series)
- ✅ NASCAR live feed data (race 5543)
- ✅ MotoGP calendar and results parsing
- ✅ IndyCar static schedule

**Recommended Testing:**
```bash
# NASCAR
curl "https://your-vercel.app/api/nascar?upcoming"
curl "https://your-vercel.app/api/nascar?series=cup&results"

# MotoGP
curl "https://your-vercel.app/api/motogp?upcoming"
curl "https://your-vercel.app/api/motogp?results"

# IndyCar
curl "https://your-vercel.app/api/indycar?featured"

# Health
curl "https://your-vercel.app/api/health?deep"
```

---

*Report generated by Athena, Research & Strategy Sub-Agent*
*Mission Duration: ~45 minutes*
