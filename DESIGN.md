# GridView Design System

## Design Research Notes

### Analyzed Sites
- **motorsport.com** - Red accents on dark backgrounds, data-heavy widgets, sidebar ads, premium feel
- **autosport.com** - Red/orange accents, clean typography, header banners, clear hierarchy
- **f1.com** - F1 red, carbon fiber textures, gradient backgrounds, very polished
- **racer.com** - Traditional layout, simpler approach
- **the-race.com** - Clean, modern, good white space, purple/magenta accents

### What Works (Patterns to Adopt)

1. **Color Schemes**
   - Dark backgrounds (#0a0a0f, #111117) with subtle gradients
   - Racing red (#e10600, #ff1e00) as primary accent
   - Secondary accents: orange (#ff6b35), amber (#fbbf24) for warnings/highlights
   - Green (#22c55e) for live indicators and success states
   - Clean white/gray text hierarchy

2. **Typography**
   - Bold, condensed fonts for headings (racing aesthetic)
   - Clean sans-serif for body (Inter, system fonts)
   - Clear size hierarchy (32px+ for main titles, 20-24px sections, 14-16px body)
   - Uppercase for series labels and category tags
   - Monospace for timing/position data

3. **Layout Patterns**
   - Full-width header with leaderboard ad slot
   - Main content (left/center) + sidebar (right) on desktop
   - Card-based content modules
   - Sticky navigation on scroll
   - Footer with links and attribution

4. **Data Presentation**
   - Position numbers prominently styled
   - Zebra striping on tables
   - Driver/team color indicators where applicable
   - Time gaps clearly formatted (monospace)
   - Expandable/collapsible sections for dense data

5. **Ad Placements (Non-Intrusive)**
   - Header: Leaderboard (728x90) or responsive
   - Sidebar: Medium Rectangle (300x250), Half Page (300x600)
   - Between content blocks: Billboard (970x250) on wide screens
   - Mobile: Banners collapse or become inline

---

## GridView Design Specification

### Brand Colors
```
Primary Red:      #e10600 (racing red)
Dark Background:  #0a0a0f (near-black)
Card Background:  #16161d (elevated surfaces)
Border:           #2a2a35 (subtle dividers)
Text Primary:     #ffffff
Text Secondary:   #9ca3af
Text Muted:       #6b7280
Accent Green:     #22c55e (live indicators)
Accent Orange:    #ff6b35 (highlights)
Accent Amber:     #fbbf24 (warnings)
```

### Typography Scale
```
Hero:        36-48px, 800 weight
Section:     24px, 700 weight  
Card Title:  18px, 600 weight
Body:        14-16px, 400 weight
Caption:     12px, 400 weight
Mono/Data:   14px, monospace (times, positions)
```

### Layout Grid
- Max container: 1400px
- Main content: ~70% (980px)
- Sidebar: ~30% (320px)
- Gutter: 24px
- Card padding: 16-24px
- Section spacing: 32-48px

### Ad Slots
```
#ad-leaderboard   → 728x90  (header area, responsive)
#ad-sidebar-top   → 300x250 (sidebar top)
#ad-sidebar-mid   → 300x600 (sidebar middle)
#ad-inline        → 970x250 (between sections, desktop only)
```

### Components

#### Series Card
- 120x100px minimum
- Icon/logo centered
- Series name below
- Live/status indicator
- Hover: subtle lift + glow

#### Results Row
- Position badge (colored, bold)
- Driver name (primary text)
- Team (secondary, can show team color)
- Time/gap (monospace, right-aligned)
- Zebra striping for readability

#### Event Card
- Date badge (prominent)
- Event name (title)
- Location/track (subtitle)
- Status indicator (upcoming/live/completed)

### Responsive Breakpoints
```
xs: < 640px   (mobile - single column, no sidebar ads)
sm: 640-768px (tablet - simplified layout)
md: 768-1024px (small desktop - sidebar visible)
lg: 1024-1280px (desktop - full layout)
xl: > 1280px  (wide - extra spacing)
```

### Dark Mode Polish
- Subtle gradient backgrounds (not flat black)
- Card shadows with slight colored glow on hover
- Borders slightly lighter than background
- Avoid pure white (#ffffff → #f0f0f5 for large text areas)

---

## Implementation Notes

### Ad Integration
Ad slots use placeholder divs with clear comments for easy network integration:
```html
<!-- AD SLOT: Leaderboard 728x90 -->
<div id="ad-leaderboard" class="ad-slot ad-leaderboard">
  <!-- Insert ad network code here -->
</div>
```

### API Endpoints (Unchanged)
- `/api/health` - Health check
- `/api/f1` - F1 data
- `/api/wrc` - WRC data

### Future Enhancements
- Real team color indicators (Ferrari red, Mercedes teal, etc.)
- Checkered flag patterns for race winners
- Animated transitions for live data updates
- Driver/team logos when available
- Dark/light mode toggle (currently dark only)
