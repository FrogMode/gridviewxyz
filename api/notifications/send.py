"""
Push Notification Sender Utility
POST /api/notifications/send - Send a notification (admin only)

This endpoint is primarily used by the cron job and admin tools.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime

# pywebpush is optional - if not available, we'll use a stub
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    print("Warning: pywebpush not installed. Push notifications disabled.")

SUBSCRIPTIONS_FILE = '/tmp/gridview_subscriptions.json'


def load_subscriptions():
    """Load subscriptions from file."""
    try:
        if os.path.exists(SUBSCRIPTIONS_FILE):
            with open(SUBSCRIPTIONS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading subscriptions: {e}")
    return {}


def save_subscriptions(subs):
    """Save subscriptions to file."""
    try:
        with open(SUBSCRIPTIONS_FILE, 'w') as f:
            json.dump(subs, f, indent=2)
    except Exception as e:
        print(f"Error saving subscriptions: {e}")


def get_vapid_config():
    """Get VAPID configuration from environment."""
    return {
        'private_key': os.environ.get('VAPID_PRIVATE_KEY', ''),
        'public_key': os.environ.get('VAPID_PUBLIC_KEY', ''),
        'subject': os.environ.get('VAPID_SUBJECT', 'mailto:contact@gridview.app')
    }


def send_push_notification(subscription_info, payload):
    """Send a push notification to a single subscriber."""
    if not WEBPUSH_AVAILABLE:
        return {'success': False, 'error': 'pywebpush not available'}
    
    vapid = get_vapid_config()
    if not vapid['private_key'] or not vapid['public_key']:
        return {'success': False, 'error': 'VAPID keys not configured'}
    
    try:
        response = webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=vapid['private_key'],
            vapid_claims={'sub': vapid['subject']}
        )
        return {'success': True, 'status': response.status_code}
    except WebPushException as e:
        # 410 Gone means the subscription is no longer valid
        if e.response and e.response.status_code == 410:
            return {'success': False, 'error': 'gone', 'remove': True}
        return {'success': False, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_to_subscribers(payload, series_filter=None, alert_type=None):
    """
    Send notification to all matching subscribers.
    
    Args:
        payload: Notification payload dict
        series_filter: Optional list of series to filter by (e.g., ['f1', 'wrc'])
        alert_type: Optional alert type to filter by (e.g., 'raceStart15min')
    
    Returns:
        dict with success/fail counts
    """
    subscriptions = load_subscriptions()
    results = {'sent': 0, 'failed': 0, 'skipped': 0, 'removed': 0}
    to_remove = []
    
    for sub_id, sub_data in subscriptions.items():
        # Check series filter
        if series_filter:
            user_series = sub_data.get('preferences', {}).get('series', {})
            if not any(user_series.get(s, False) for s in series_filter):
                results['skipped'] += 1
                continue
        
        # Check alert type filter
        if alert_type:
            user_alerts = sub_data.get('preferences', {}).get('alerts', {})
            if not user_alerts.get(alert_type, False):
                results['skipped'] += 1
                continue
        
        # Send the notification
        result = send_push_notification(sub_data['subscription'], payload)
        
        if result['success']:
            results['sent'] += 1
        elif result.get('remove'):
            to_remove.append(sub_id)
            results['removed'] += 1
        else:
            results['failed'] += 1
            print(f"Failed to send to {sub_id}: {result.get('error')}")
    
    # Remove invalid subscriptions
    if to_remove:
        for sub_id in to_remove:
            del subscriptions[sub_id]
        save_subscriptions(subscriptions)
    
    return results


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        """Send a notification to subscribers."""
        try:
            # Basic auth check (in production, use proper auth)
            auth_header = self.headers.get('Authorization', '')
            admin_key = os.environ.get('ADMIN_API_KEY', 'dev-admin-key')
            
            if not auth_header.endswith(admin_key):
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Unauthorized'}).encode())
                return
            
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body)
            
            # Validate payload
            if not data.get('title') or not data.get('body'):
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'error': 'title and body required'
                }).encode())
                return
            
            # Build notification payload
            payload = {
                'title': data['title'],
                'body': data['body'],
                'icon': data.get('icon', '/icons/icon-192.png'),
                'badge': data.get('badge', '/icons/badge-72.png'),
                'tag': data.get('tag', f"gridview-{datetime.utcnow().strftime('%Y%m%d%H%M')}"),
                'url': data.get('url', '/'),
                'requireInteraction': data.get('requireInteraction', False),
                'actions': data.get('actions', [])
            }
            
            # Get filters
            series_filter = data.get('series')  # e.g., ['f1', 'wrc']
            alert_type = data.get('alertType')  # e.g., 'raceStart15min'
            
            # Send to matching subscribers
            results = send_to_subscribers(payload, series_filter, alert_type)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                'status': 'sent',
                'results': results
            }).encode())
            
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Invalid JSON'}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
