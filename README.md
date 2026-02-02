# GridView

**gridview.xyz** — All motorsport. One dashboard.

Real-world and sim racing results, standings, and schedules in one place.

## Deploy to Vercel

### Option 1: Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
cd projects/motorsport-aggregator-vercel
vercel
```

### Option 2: GitHub Integration

1. Push this folder to a GitHub repo
2. Import in Vercel dashboard: https://vercel.com/new
3. Deploy automatically

## API Endpoints

| Endpoint | Description | Status |
|----------|-------------|--------|
| `/api/health` | API health check | ✅ |
| `/api/f1/calendar` | F1 2025 race calendar | ✅ |
| `/api/f1/standings` | F1 current drivers | ✅ |
| `/api/wrc/latest` | WRC latest results | ✅ (sample) |

## Local Development

```bash
# Install Vercel CLI
npm i -g vercel

# Run locally
vercel dev
```

## Project Structure

```
motorsport-aggregator-vercel/
├── api/
│   ├── health.py          # Health check
│   ├── f1/
│   │   ├── calendar.py    # F1 calendar
│   │   └── standings.py   # F1 drivers
│   └── wrc/
│       └── latest.py      # WRC results
├── public/
│   └── index.html         # Frontend
├── vercel.json            # Vercel config
└── requirements.txt       # Python deps
```

## Data Sources

- **F1:** OpenF1 API (https://openf1.org) - Free, no auth
- **WRC:** Sample data (full scraper pending)

## Next Steps

- [ ] Add more F1 endpoints (results, lap times)
- [ ] Integrate WRC scraper
- [ ] Add NASCAR, IndyCar, IMSA, WEC
- [ ] Add iRacing integration (needs auth)
