# GridView Push Notifications - Usage Guide

## Overview

GridView uses the Web Push API to send race start alerts and notifications to users. This guide covers setup, configuration, and usage.

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│    User Browser     │     │   Vercel Backend    │
│  ┌───────────────┐  │     │  ┌───────────────┐  │
│  │ Service Worker│◄─┼─────┼──│  Push Sender  │  │
│  └───────────────┘  │     │  └───────────────┘  │
│         │           │     │         ▲           │
│         ▼           │     │         │           │
│  ┌───────────────┐  │     │  ┌───────────────┐  │
│  │  Notification │  │     │  │  Cron Job     │  │
│  │    Display    │  │     │  │ (15 min)      │  │
│  └───────────────┘  │     │  └───────────────┘  │
└─────────────────────┘     └─────────────────────┘
```

## Setup Guide

### 1. Generate VAPID Keys

VAPID (Voluntary Application Server Identification) keys are required for secure push notifications.

```bash
# Install web-push CLI globally
npm install -g web-push

# Generate keys
web-push generate-vapid-keys
```

This outputs:
```
Public Key:
BNbxGY...longBase64String...

Private Key:
anotherBase64String
```

### 2. Configure Vercel Environment Variables

In your Vercel project settings, add:

| Variable | Description |
|----------|-------------|
| `VAPID_PUBLIC_KEY` | Public key from step 1 |
| `VAPID_PRIVATE_KEY` | Private key from step 1 |
| `VAPID_SUBJECT` | Contact email: `mailto:your@email.com` |
| `ADMIN_API_KEY` | Secret key for admin endpoints |
| `CRON_SECRET` | Secret for cron job authentication |

### 3. Add PWA Icons

Replace placeholder icons in `/public/icons/`:

- `icon-72.png` through `icon-512.png` - App icons
- `badge-72.png` - Notification badge (monochrome)

Recommended tool: [RealFaviconGenerator](https://realfavicongenerator.net)

### 4. Deploy

```bash
vercel --prod
```

The cron job (`/api/cron/race-alerts`) runs every 15 minutes automatically.

## API Endpoints

### GET /api/notifications/subscribe

Returns VAPID public key and subscription status.

**Response:**
```json
{
  "vapidPublicKey": "BNbxGY...",
  "subscriberCount": 42,
  "ready": true
}
```

### POST /api/notifications/subscribe

Subscribe to push notifications.

**Request:**
```json
{
  "subscription": {
    "endpoint": "https://fcm.googleapis.com/fcm/send/...",
    "keys": {
      "p256dh": "...",
      "auth": "..."
    }
  },
  "preferences": {
    "series": { "f1": true, "wrc": true },
    "alerts": { "raceStart15min": true, "results": true }
  }
}
```

**Response:**
```json
{
  "status": "subscribed",
  "id": "abc123",
  "preferences": { ... }
}
```

### DELETE /api/notifications/subscribe

Unsubscribe from notifications.

**Request:**
```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/..."
}
```

### POST /api/notifications/send (Admin)

Send notification to subscribers. Requires `Authorization: Bearer <ADMIN_API_KEY>`.

**Request:**
```json
{
  "title": "🏁 F1: Race Starting!",
  "body": "Australian GP starts in 15 minutes",
  "url": "/?series=f1",
  "series": ["f1"],
  "alertType": "raceStart15min"
}
```

### POST /api/notifications/test

Send a test notification to verify setup.

**Request:**
```json
{
  "subscription": { ... }
}
```

### GET /api/cron/race-alerts

Cron endpoint that checks for upcoming sessions and sends notifications.
Called automatically by Vercel Cron every 15 minutes.

## User Preferences

Users can configure:

### Series Alerts
- F1
- WRC
- NASCAR
- IndyCar
- IMSA
- WEC
- MotoGP

### Alert Types
- **raceStart15min** - 15 minutes before race
- **raceStart1hour** - 1 hour before race
- **results** - When race results are available

## Notification Payload Format

```json
{
  "title": "🏎️ F1: Starting in 15 minutes!",
  "body": "Australian Grand Prix - Race",
  "icon": "/icons/icon-192.png",
  "badge": "/icons/badge-72.png",
  "tag": "race-15min-f1-20250202",
  "url": "/?series=f1",
  "requireInteraction": true,
  "actions": [
    { "action": "view-live", "title": "📺 Watch" },
    { "action": "dismiss", "title": "Dismiss" }
  ]
}
```

## Browser Support

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome | ✅ | Full support (desktop & Android) |
| Firefox | ✅ | Full support |
| Safari | ✅ | iOS 16.4+, macOS Ventura+ |
| Edge | ✅ | Full support |
| Samsung Internet | ✅ | Full support |

## Testing

### Local Testing

1. Run local dev server: `vercel dev`
2. Open browser DevTools → Application → Service Workers
3. Click "Enable Notifications" in the UI
4. Use "Send Test Notification" button

### Manual Push Test

```bash
# Using web-push CLI
web-push send-notification \
  --endpoint="https://fcm.googleapis.com/..." \
  --key="userKey" \
  --auth="authSecret" \
  --vapid-subject="mailto:contact@gridview.app" \
  --vapid-pubkey="$VAPID_PUBLIC_KEY" \
  --vapid-pvtkey="$VAPID_PRIVATE_KEY" \
  --payload='{"title":"Test","body":"Hello!"}'
```

## Troubleshooting

### "Notifications not supported"
- Ensure HTTPS (required for Service Workers)
- Check browser compatibility

### "Permission denied"
- User blocked notifications in browser settings
- Guide users to enable in browser preferences

### Notifications not arriving
1. Check Service Worker is registered (DevTools → Application)
2. Verify VAPID keys are configured in Vercel
3. Check subscription endpoint is valid
4. Review server logs for push errors

### "410 Gone" errors
- Subscription expired or user unsubscribed
- System automatically removes these subscriptions

## Cost & Limits

- **Push delivery**: Free (FCM, Mozilla Push, APNs)
- **Vercel Cron**: Free tier includes 2 cron jobs
- **File storage**: Using `/tmp/` for MVP; upgrade to Vercel KV for production

## Future Improvements

1. **Vercel KV storage** - Replace file-based subscription storage
2. **Rich notifications** - Live position updates during races
3. **Action buttons** - Direct links to streams
4. **Notification groups** - Batch session alerts
5. **Quiet hours** - Respect user sleep schedules
6. **Analytics** - Track open/click rates

## Files

| File | Purpose |
|------|---------|
| `public/sw.js` | Service Worker for push handling |
| `public/manifest.json` | PWA manifest |
| `api/notifications/subscribe.py` | Subscription management |
| `api/notifications/send.py` | Send notifications (admin) |
| `api/notifications/test.py` | Test notification endpoint |
| `api/cron/race-alerts.py` | Scheduled notification cron |

---

*Last updated: 2025-02-02*
