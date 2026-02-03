# Hermes 🪽 - Paddock Buzz Tweet Tracker Report

**Task:** Build a live Twitter/X tweet tracker for GridView  
**Status:** ✅ Completed  
**Date:** 2026-02-03  
**Deployed:** https://gridview.xyz

---

## What Was Built

### 1. API Endpoint: `/api/tweets.py`

A new Python API endpoint that fetches motorsport tweets using the `bird` CLI:

- **Search Mode:** Fetches tweets by hashtag search (e.g., `#F1`, `#NASCAR`, `#IMSA`)
- **Caching:** 60-second in-memory cache to reduce API calls
- **Series Filters:** Supports `all`, `f1`, `nascar`, `indycar`, `imsa`, `wec`, `motogp`
- **Response Format:** JSON with formatted tweet data including:
  - Tweet text (cleaned, t.co URLs stripped)
  - Author info (name, username, avatar via unavatar.io)
  - Timestamps (ISO + relative time like "2h ago")
  - Engagement metrics (likes, retweets, replies)
  - Media preview URL

**Example API Call:**
```
GET /api/tweets?series=f1&limit=10
```

### 2. Frontend Widget: "Paddock Buzz"

Added to the sidebar on `index.html`:

- **Live Tweet Feed:** Displays latest motorsport tweets
- **Series Filter Tabs:** Quick filter buttons (All, F1, NASCAR, IndyCar, IMSA)
- **Auto-Refresh:** Updates every 60 seconds with visual indicator
- **Theme-Aware:** Uses CSS variables from `/public/themes/`
- **Scrollable:** Max height 500px with hidden scrollbar
- **Click-Through:** Each tweet links to original on X/Twitter

### 3. JavaScript Functions

```javascript
loadPaddockBuzz(series)  // Load tweets for a series
filterTweets(series)     // Switch series filter
startTweetsRefresh()     // Start 60s auto-refresh timer
```

---

## Search Queries

The API searches these hashtag combinations:

| Series   | Query                                          |
|----------|-----------------------------------------------|
| `all`    | `#F1 OR #NASCAR OR #IndyCar OR #IMSA OR #WEC OR #MotoGP` |
| `f1`     | `#F1 OR #Formula1`                            |
| `nascar` | `#NASCAR OR #NASCARCup`                       |
| `indycar`| `#IndyCar OR #INDYCAR`                        |
| `imsa`   | `#IMSA OR #Rolex24 OR #WeatherTech`           |
| `wec`    | `#WEC OR #LeMans24 OR #Hypercar`              |
| `motogp` | `#MotoGP`                                     |

All queries include `-filter:replies` to exclude reply tweets.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   GridView Frontend                  │
│  ┌──────────────────────────────────────────────┐   │
│  │           Paddock Buzz Widget                │   │
│  │  • Series filter tabs                        │   │
│  │  • Tweet cards with avatar, text, metrics    │   │
│  │  • 60s auto-refresh                          │   │
│  └──────────────────────────────────────────────┘   │
│                        │                            │
│                  fetch /api/tweets                  │
└────────────────────────┼────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                    /api/tweets.py                    │
│  • Check in-memory cache (60s TTL)                  │
│  • Run: bird search <query> -n <limit> --json       │
│  • Format tweets for frontend                       │
│  • Return JSON response                             │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                    bird CLI                          │
│  • Cookie-based Twitter/X authentication            │
│  • GraphQL API calls to X                           │
└─────────────────────────────────────────────────────┘
```

---

## ⚠️ Important Limitations

### Production Deployment
The `bird` CLI requires browser cookies to authenticate with Twitter/X. On Vercel's serverless environment, the CLI won't have access to these cookies, so **the tweets API will return empty results in production**.

**Workarounds for full production support:**
1. **Twitter API v2:** Switch to official Twitter API with Bearer token (requires developer account)
2. **Proxy Server:** Run a local server that fetches tweets and caches them for Vercel to serve
3. **Cron + Static:** Use a cron job to fetch tweets periodically and store as static JSON

### Current Behavior
- **Locally:** Works perfectly with bird CLI and browser cookies
- **Production (Vercel):** Returns empty tweets array gracefully, widget shows "No tweets found"

---

## Files Modified/Created

| File | Action | Description |
|------|--------|-------------|
| `api/tweets.py` | Created | New API endpoint for fetching tweets |
| `index.html` | Modified | Added Paddock Buzz widget + JavaScript |

---

## Testing

```bash
# Test API locally
curl "http://localhost:3000/api/tweets?series=f1&limit=5"

# Test bird CLI directly
bird search "#F1" -n 5 --json
```

---

## Future Enhancements

1. **Twitter API Integration:** Use official API for production reliability
2. **Sentiment Badges:** Show sentiment analysis per tweet (positive/negative/neutral)
3. **Account Mode:** Switch between hashtag search and specific account feeds
4. **Engagement Sorting:** Sort by likes/retweets for "top" tweets
5. **Quote Tweets:** Expand quoted tweets inline
6. **Mobile Optimization:** Move widget to dedicated page on mobile

---

*Generated by Hermes 🪽 subagent*
