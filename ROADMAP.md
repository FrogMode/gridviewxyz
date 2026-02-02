# GridView Roadmap

Based on audience research findings.

## Phase 1: Core Experience (Now)

### Must-Have Features
- [x] Multi-series dashboard (F1, WRC)
- [ ] Add IMSA, WEC, IndyCar, NASCAR
- [ ] Unified calendar with timezone picker
- [ ] Mobile-optimized layout
- [ ] Spoiler-free mode toggle
- [ ] Quick race recap cards

### Content Priorities
- Race results (fast, clean display)
- Championship standings
- Upcoming schedule with countdowns
- News headlines (aggregated, not full articles)

## Phase 2: Engagement (Next)

### Features
- [ ] Push notifications for race start
- [ ] Favorite series/teams selection
- [ ] Personalized dashboard
- [ ] Live timing links
- [ ] Video content curation (YouTube embeds)

### Content
- Technical explainers
- Driver profiles
- Track guides

## Phase 3: Community (Future)

### Features
- [ ] User accounts
- [ ] Comments / discussion
- [ ] Fantasy integration
- [ ] Predictions / polls
- [ ] Sim racing content section

---

## Site Structure

```
GridView
├── Home (Dashboard)
│   ├── [Spoiler Toggle]
│   ├── What's Happening Now (live indicator)
│   ├── Quick Results (last 24-48h)
│   ├── Coming Up (next 7 days)
│   └── Series Cards
│
├── Calendar
│   ├── All Series unified view
│   ├── Timezone picker
│   ├── Filter by series
│   └── Export to calendar
│
├── Results
│   ├── By series
│   ├── Full race results
│   └── Championship impact
│
├── Standings
│   ├── All championships
│   └── Historical comparison
│
├── News
│   ├── Aggregated headlines
│   ├── Filter by series
│   └── No full articles (link out)
│
└── [Future] Videos
    ├── Highlights
    ├── Analysis
    └── Curated YouTube
```

---

## Design Principles

1. **Speed first** — Page load < 2s, data visible immediately
2. **Mobile first** — 70%+ traffic will be mobile
3. **Respect attention** — No autoplay, no popups, minimal ads
4. **Spoiler protection** — One toggle hides all results
5. **Unified experience** — Same patterns across all series

---

## Audience Insights Driving Decisions

| Finding | Feature Response |
|---------|------------------|
| 75% new fans are women | Accessible design, explain jargon |
| 57% under 35 | Mobile-first, social sharing |
| 61% engage daily | Push notifications, fresh content |
| Ad overload complaints | Fewer, better-placed ads |
| Want multi-series | Unified dashboard |
| Spoiler frustration | Spoiler-free mode |
| Timezone confusion | Local time everywhere |
