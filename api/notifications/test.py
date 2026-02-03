"""
Test Notification Endpoint
POST /api/notifications/test - Send a test notification to verify setup

No auth required - sends only to the requesting subscription.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime

# pywebpush is optional
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False


def get_vapid_config():
    """Get VAPID configuration from environment."""
    return {
        'private_key': os.environ.get('VAPID_PRIVATE_KEY', ''),
        'public_key': os.environ.get('VAPID_PUBLIC_KEY', ''),
        'subject': os.environ.get('VAPID_SUBJECT', 'mailto:contact@gridview.app')
    }


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        """Send a test notification to a specific subscription."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body)
            
            subscription = data.get('subscription')
            if not subscription or not subscription.get('endpoint'):
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'error': 'Subscription required'
                }).encode())
                return
            
            # Check if pywebpush is available
            if not WEBPUSH_AVAILABLE:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'simulated',
                    'message': 'pywebpush not installed - notification simulated',
                    'payload': {
                        'title': '🏁 GridView Test',
                        'body': 'Notifications are working! (simulated)'
                    }
                }).encode())
                return
            
            vapid = get_vapid_config()
            if not vapid['private_key'] or not vapid['public_key']:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'not_configured',
                    'message': 'VAPID keys not configured - set VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY'
                }).encode())
                return
            
            # Build test payload
            payload = {
                'title': '🏁 GridView Test Notification',
                'body': f'Push notifications are working! Sent at {datetime.utcnow().strftime("%H:%M UTC")}',
                'icon': '/icons/icon-192.png',
                'badge': '/icons/badge-72.png',
                'tag': 'gridview-test',
                'url': '/',
                'actions': [
                    {'action': 'view-live', 'title': '📺 Live Timing'},
                    {'action': 'dismiss', 'title': 'Dismiss'}
                ]
            }
            
            # Send the notification
            try:
                response = webpush(
                    subscription_info=subscription,
                    data=json.dumps(payload),
                    vapid_private_key=vapid['private_key'],
                    vapid_claims={'sub': vapid['subject']}
                )
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'sent',
                    'httpStatus': response.status_code,
                    'message': 'Test notification sent successfully!'
                }).encode())
                
            except WebPushException as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'failed',
                    'error': str(e),
                    'httpStatus': e.response.status_code if e.response else None
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
