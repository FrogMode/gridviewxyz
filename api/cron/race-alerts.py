"""
Race Alerts Cron Job
GET /api/cron/race-alerts - Check upcoming sessions and send notifications

This endpoint is called by Vercel Cron every 15 minutes.
It checks all racing series for upcoming sessions and sends
notifications to subscribers based on their preferences.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError

# Import notification sender
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from notifications.send import send_to_subscribers, WEBPUSH_AVAILABLE
except ImportError:
    WEBPUSH_AVAILABLE = False
    def send_to_subscribers(*args, **kwargs):
        return {'sent': 0, 'failed': 0, 'skipped': 0, 'removed': 0}

# Track sent notifications to avoid duplicates
SENT_CACHE_FILE = '/tmp/gridview_sent_alerts.json'


def load_sent_cache():
    """Load cache of sent notification IDs."""
    try:
        if os.path.exists(SENT_CACHE_FILE):
            with open(SENT_CACHE_FILE, 'r') as f:
                data = json.load(f)
                # Clean old entries (older than 24 hours)
                cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
                return {k: v for k, v in data.items() if v > cutoff}
    except Exception:
        pass
    return {}


def save_sent_cache(cache):
    """Save sent notification cache."""
    try:
        with open(SENT_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass


def get_series_emoji(series):
    """Get emoji for series."""
    return {
        'f1': '🏎️',
        'wrc': '🌍',
        'nascar': '🏁',
        'indycar': '🇺🇸',
        'motogp': '🏍️',
        'wec': '🏎️',
        'imsa': '🏎️',
        'sro': '🏆'
    }.get(series.lower(), '🏁')


def fetch_upcoming_sessions():
    """
    Fetch upcoming sessions from our schedule APIs.
    Returns a list of sessions happening in the next 15-60 minutes.
    """
    upcoming = []
    base_url = os.environ.get('VERCEL_URL', 'localhost:3000')
    if not base_url.startswith('http'):
        base_url = f'https://{base_url}'
    
    # Series endpoints that have schedule data
    series_endpoints = {
        'f1': '/api/f1',
        'wrc': '/api/wrc', 
        'nascar': '/api/nascar',
        'indycar': '/api/indycar',
        'motogp': '/api/motogp',
        'wec': '/api/wec',
        'imsa': '/api/imsa'
    }
    
    now = datetime.utcnow()
    
    for series, endpoint in series_endpoints.items():
        try:
            req = Request(f'{base_url}{endpoint}', headers={'Accept': 'application/json'})
            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                # Look for upcoming sessions in the response
                # Different series have different response structures
                sessions = []
                
                if 'schedule' in data:
                    sessions = data['schedule']
                elif 'events' in data:
                    sessions = data['events']
                elif 'sessions' in data:
                    sessions = data['sessions']
                elif 'races' in data:
                    sessions = data['races']
                
                for session in sessions:
                    session_time = None
                    
                    # Try different time field names
                    for time_field in ['start_time', 'startTime', 'datetime', 'date', 'time']:
                        if time_field in session:
                            try:
                                time_str = session[time_field]
                                if 'T' in time_str:
                                    session_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                                else:
                                    session_time = datetime.fromisoformat(time_str)
                                break
                            except:
                                continue
                    
                    if not session_time:
                        continue
                    
                    # Make timezone-naive for comparison
                    if session_time.tzinfo:
                        session_time = session_time.replace(tzinfo=None)
                    
                    # Calculate minutes until session
                    delta = (session_time - now).total_seconds() / 60
                    
                    # Check if within notification windows
                    if 10 <= delta <= 20:  # 15-minute window
                        upcoming.append({
                            'series': series,
                            'name': session.get('name') or session.get('sessionName') or session.get('title', 'Session'),
                            'event': session.get('event') or session.get('eventName') or session.get('grandPrix', ''),
                            'time': session_time.isoformat(),
                            'minutes_until': int(delta),
                            'alert_type': 'raceStart15min',
                            'id': f"{series}-{session_time.strftime('%Y%m%d%H%M')}"
                        })
                    elif 55 <= delta <= 65:  # 1-hour window
                        upcoming.append({
                            'series': series,
                            'name': session.get('name') or session.get('sessionName') or session.get('title', 'Session'),
                            'event': session.get('event') or session.get('eventName') or session.get('grandPrix', ''),
                            'time': session_time.isoformat(),
                            'minutes_until': int(delta),
                            'alert_type': 'raceStart1hour',
                            'id': f"{series}-{session_time.strftime('%Y%m%d%H%M')}-1h"
                        })
                        
        except Exception as e:
            print(f"Error fetching {series}: {e}")
            continue
    
    return upcoming


def send_session_alert(session, sent_cache):
    """Send notification for an upcoming session."""
    alert_id = f"{session['id']}-{session['alert_type']}"
    
    # Check if already sent
    if alert_id in sent_cache:
        return {'skipped': True, 'reason': 'already_sent'}
    
    emoji = get_series_emoji(session['series'])
    series_upper = session['series'].upper()
    
    # Build notification
    if session['alert_type'] == 'raceStart15min':
        title = f"{emoji} {series_upper}: Starting in 15 minutes!"
        body = f"{session['event']} - {session['name']}"
        tag = f"race-15min-{session['id']}"
    else:
        title = f"{emoji} {series_upper}: Starting in 1 hour"
        body = f"{session['event']} - {session['name']}"
        tag = f"race-1hour-{session['id']}"
    
    payload = {
        'title': title,
        'body': body,
        'icon': f'/icons/{session["series"]}-192.png',
        'badge': '/icons/badge-72.png',
        'tag': tag,
        'url': f'/?series={session["series"]}',
        'requireInteraction': session['alert_type'] == 'raceStart15min',
        'actions': [
            {'action': 'view-live', 'title': '📺 Watch'},
            {'action': 'dismiss', 'title': 'Dismiss'}
        ]
    }
    
    # Send to subscribers
    results = send_to_subscribers(
        payload,
        series_filter=[session['series']],
        alert_type=session['alert_type']
    )
    
    # Mark as sent
    sent_cache[alert_id] = datetime.utcnow().isoformat()
    
    return {
        'skipped': False,
        'session': session['name'],
        'series': session['series'],
        'results': results
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Process scheduled notification check."""
        try:
            # Verify cron secret (Vercel adds this header)
            auth_header = self.headers.get('Authorization', '')
            cron_secret = os.environ.get('CRON_SECRET', '')
            
            # In development, allow without auth
            if cron_secret and auth_header != f'Bearer {cron_secret}':
                # Also check for Vercel's cron header
                if self.headers.get('x-vercel-cron') != '1':
                    self.send_response(401)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'Unauthorized'}).encode())
                    return
            
            # Check if push is available
            if not WEBPUSH_AVAILABLE:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'skipped',
                    'reason': 'pywebpush not available'
                }).encode())
                return
            
            # Fetch upcoming sessions
            upcoming = fetch_upcoming_sessions()
            sent_cache = load_sent_cache()
            
            # Send alerts
            results = []
            for session in upcoming:
                result = send_session_alert(session, sent_cache)
                results.append(result)
            
            # Save updated cache
            save_sent_cache(sent_cache)
            
            # Summary
            sent_count = sum(1 for r in results if not r.get('skipped'))
            skipped_count = sum(1 for r in results if r.get('skipped'))
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                'status': 'complete',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'upcoming_sessions': len(upcoming),
                'notifications_sent': sent_count,
                'notifications_skipped': skipped_count,
                'details': results
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }).encode())
