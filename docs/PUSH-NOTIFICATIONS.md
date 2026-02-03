# Push Notifications Design Document

## ⚡ Quick Setup (VAPID Keys)

Before push notifications work, you need VAPID keys:

```bash
# Generate keys (one-time)
npx web-push generate-vapid-keys

# Example output:
# Public Key: BNp8x7F...
# Private Key: X2mK9p3...
```

**Set these environment variables:**

| Variable | Description | Where |
|----------|-------------|-------|
| `VAPID_PUBLIC_KEY` | Your public key | Vercel env vars + `index.html` |
| `VAPID_PRIVATE_KEY` | Your private key | Vercel env vars only (secret!) |
| `VAPID_SUBJECT` | Contact URL | Vercel env vars (e.g., `mailto:contact@gridview.xyz`) |

**In `index.html`, update line ~420:**
```javascript
const VAPID_PUBLIC_KEY = 'YOUR_ACTUAL_PUBLIC_KEY_HERE';
```

**In Vercel:**
1. Go to Project Settings → Environment Variables
2. Add `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`
3. Redeploy

---

## Overview

This document outlines the implementation plan for PWA (Progressive Web App) push notifications in GridView, enabling race start alerts and other time-sensitive notifications.

## Goals

1. **Race Start Alerts**: Notify users when a race is about to start (15 min, 1 hour before)
2. **Results Available**: Notify when race results are published
3. **Session Reminders**: Practice, qualifying, and race session reminders
4. **Breaking News**: (Future) Important news from subscribed series

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         GridView PWA                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │   Service   │   │   Push      │   │   Notification      │   │
│  │   Worker    │◄──┤   Manager   │◄──┤   Preferences       │   │
│  └──────┬──────┘   └──────┬──────┘   └─────────────────────┘   │
│         │                 │                                      │
└─────────┼─────────────────┼──────────────────────────────────────┘
          │                 │
          ▼                 ▼
┌─────────────────┐  ┌─────────────────┐
│   Browser Push  │  │   GridView API   │
│   Service       │  │   (Vercel Edge)  │
│   (FCM/APNS)    │  ├─────────────────┤
└─────────────────┘  │ /api/subscribe   │
                     │ /api/notify      │
                     │ /api/schedule    │
                     └────────┬─────────┘
                              │
                     ┌────────▼─────────┐
                     │   Scheduler      │
                     │   (Vercel Cron)  │
                     └──────────────────┘
```

### Technology Stack

- **Push API**: Web Push Protocol (RFC 8030)
- **Service Worker**: Handle background notifications
- **Vercel Edge Functions**: Subscription management and sending
- **Vercel KV / Upstash**: Store push subscriptions
- **Vercel Cron**: Schedule notification delivery

## Implementation Plan

### Phase 1: PWA Foundation (Week 1)

1. **Create Service Worker** (`public/sw.js`)
   ```javascript
   // Handle push events
   self.addEventListener('push', event => {
     const data = event.data.json();
     event.waitUntil(
       self.registration.showNotification(data.title, {
         body: data.body,
         icon: '/icons/icon-192.png',
         badge: '/icons/badge-72.png',
         tag: data.tag,
         data: { url: data.url }
       })
     );
   });
   
   // Handle notification clicks
   self.addEventListener('notificationclick', event => {
     event.notification.close();
     event.waitUntil(
       clients.openWindow(event.notification.data.url || '/')
     );
   });
   ```

2. **Create Web App Manifest** (`public/manifest.json`)
   ```json
   {
     "name": "GridView - Motorsport Aggregator",
     "short_name": "GridView",
     "start_url": "/",
     "display": "standalone",
     "background_color": "#0a0a0f",
     "theme_color": "#e10600",
     "icons": [
       { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
       { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
     ]
   }
   ```

3. **Register Service Worker**
   ```javascript
   if ('serviceWorker' in navigator && 'PushManager' in window) {
     navigator.serviceWorker.register('/sw.js');
   }
   ```

### Phase 2: Subscription Management (Week 2)

1. **Generate VAPID Keys**
   ```bash
   npx web-push generate-vapid-keys
   ```
   Store in Vercel environment variables:
   - `VAPID_PUBLIC_KEY`
   - `VAPID_PRIVATE_KEY`
   - `VAPID_SUBJECT` (mailto:contact@gridview.app)

2. **Create Subscribe API** (`api/subscribe.py`)
   ```python
   # POST /api/subscribe
   # Body: { subscription: PushSubscription, preferences: {...} }
   
   async def handler(request):
       data = await request.json()
       subscription = data['subscription']
       preferences = data.get('preferences', {})
       
       # Store in KV
       subscription_id = generate_id(subscription['endpoint'])
       await kv.set(f"push:{subscription_id}", {
           "subscription": subscription,
           "preferences": preferences,
           "created": datetime.now().isoformat()
       })
       
       return {"status": "subscribed", "id": subscription_id}
   ```

3. **Client-Side Subscribe Flow**
   ```javascript
   async function subscribe() {
     const registration = await navigator.serviceWorker.ready;
     const subscription = await registration.pushManager.subscribe({
       userVisibleOnly: true,
       applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
     });
     
     await fetch('/api/subscribe', {
       method: 'POST',
       body: JSON.stringify({
         subscription: subscription.toJSON(),
         preferences: getPreferences()
       })
     });
   }
   ```

### Phase 3: Notification Delivery (Week 3)

1. **Create Notification Sender** (`api/notify.py`)
   ```python
   from pywebpush import webpush
   
   async def send_notification(subscription, payload):
       webpush(
           subscription_info=subscription,
           data=json.dumps(payload),
           vapid_private_key=VAPID_PRIVATE_KEY,
           vapid_claims={"sub": VAPID_SUBJECT}
       )
   ```

2. **Create Cron Job** (`api/cron/check-schedule.py`)
   ```python
   # Runs every 15 minutes via Vercel Cron
   
   async def handler():
       # Get events starting in next 15-60 minutes
       upcoming = await get_upcoming_sessions()
       
       for event in upcoming:
           subscribers = await get_subscribers_for_series(event['series'])
           
           for sub in subscribers:
               if should_notify(sub, event):
                   await send_notification(sub['subscription'], {
                       "title": f"🏁 {event['series']}: Starting Soon!",
                       "body": f"{event['name']} starts in {event['minutes_until']} minutes",
                       "tag": f"race-{event['id']}",
                       "url": f"/event/{event['id']}"
                   })
   ```

3. **Vercel Cron Configuration** (`vercel.json`)
   ```json
   {
     "crons": [
       {
         "path": "/api/cron/check-schedule",
         "schedule": "*/15 * * * *"
       }
     ]
   }
   ```

### Phase 4: User Preferences UI (Week 4)

1. **Preferences Storage**
   ```javascript
   const defaultPreferences = {
     series: {
       f1: true,
       nascar: false,
       indycar: false,
       motogp: false,
       wec: false,
       imsa: false,
       wrc: false
     },
     notifications: {
       raceStart15min: true,
       raceStart1hour: false,
       qualifying: false,
       practice: false,
       results: true
     }
   };
   ```

2. **Settings UI Component**
   - Checkbox for each series
   - Toggle for notification types
   - Test notification button
   - Unsubscribe option

## Data Model

### Subscription Record
```json
{
  "id": "push:abc123",
  "subscription": {
    "endpoint": "https://fcm.googleapis.com/fcm/send/...",
    "keys": {
      "p256dh": "...",
      "auth": "..."
    }
  },
  "preferences": {
    "series": ["f1", "nascar"],
    "alerts": ["raceStart15min", "results"]
  },
  "created": "2025-02-02T19:00:00Z",
  "lastActive": "2025-02-02T20:00:00Z"
}
```

### Notification Payload
```json
{
  "title": "🏁 F1: Race Starting Soon!",
  "body": "Australian Grand Prix starts in 15 minutes",
  "icon": "/icons/f1-192.png",
  "badge": "/icons/badge-72.png",
  "tag": "race-f1-2025-01",
  "url": "/f1/event/australian-gp",
  "timestamp": 1738530600000
}
```

## Security Considerations

1. **VAPID Authentication**: All push messages signed with VAPID keys
2. **Subscription Validation**: Verify subscription endpoints before storing
3. **Rate Limiting**: Max 10 notifications per user per day
4. **Unsubscribe on Error**: Remove subscriptions that return 410 Gone
5. **No Sensitive Data**: Notifications contain only public race info

## Browser Support

| Browser | Push Support | Notes |
|---------|-------------|-------|
| Chrome | ✅ | Full support via FCM |
| Firefox | ✅ | Full support via Mozilla Push |
| Safari | ✅ | iOS 16.4+, macOS Ventura+ |
| Edge | ✅ | Full support via WNS |
| Samsung Internet | ✅ | Full support |

## Cost Estimation

- **Vercel KV**: Free tier supports 30K requests/month (sufficient for ~1K users)
- **Push Services**: Free (FCM, Mozilla Push, APNS)
- **Vercel Cron**: Free tier includes 2 cron jobs

## Timeline

| Week | Milestone |
|------|-----------|
| 1 | PWA foundation (manifest, service worker, icons) |
| 2 | Subscription API and KV storage |
| 3 | Notification delivery and cron job |
| 4 | User preferences UI and testing |
| 5 | Beta release and monitoring |

## Future Enhancements

1. **Rich Notifications**: Include race position updates, lap leader changes
2. **Action Buttons**: "Watch Live" button linking to broadcast
3. **Notification Groups**: Batch session notifications for same event
4. **Time Zone Intelligence**: Adjust reminder times based on user locale
5. **Quiet Hours**: Respect user's sleep schedule

## Dependencies

```json
{
  "dependencies": {
    "pywebpush": "^1.14.0"
  }
}
```

Update `requirements.txt`:
```
pywebpush>=1.14.0
```

## Testing

1. **Manual Testing**: Use browser DevTools > Application > Service Workers
2. **Push Testing**: `webpush --vapid-key ... --send-notification ...`
3. **End-to-End**: Cypress tests with mock service worker

## Monitoring

- Track subscription count in Vercel Analytics
- Log notification delivery success/failure
- Monitor cron job execution
- Alert on high error rates

---

*Document Version: 1.0*
*Last Updated: 2025-02-02*
