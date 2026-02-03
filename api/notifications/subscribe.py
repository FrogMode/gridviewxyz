"""
Push Notification Subscription API
POST /api/notifications/subscribe - Subscribe to push notifications
DELETE /api/notifications/subscribe - Unsubscribe from push notifications
GET /api/notifications/subscribe - Get subscription status
"""

from http.server import BaseHTTPRequestHandler
import json
import hashlib
import os
from datetime import datetime

# Simple file-based storage for MVP
# In production, use Vercel KV or a database
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


def generate_subscription_id(endpoint):
    """Generate a unique ID from the endpoint URL."""
    return hashlib.sha256(endpoint.encode()).hexdigest()[:16]


def get_vapid_public_key():
    """Get VAPID public key from environment."""
    # In production, set VAPID_PUBLIC_KEY in Vercel environment variables
    return os.environ.get(
        'VAPID_PUBLIC_KEY',
        # Placeholder - replace with actual generated key
        'PLACEHOLDER_VAPID_PUBLIC_KEY_GENERATE_WITH_WEB_PUSH'
    )


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Get VAPID public key and subscription status."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        subscriptions = load_subscriptions()
        
        response = {
            'vapidPublicKey': get_vapid_public_key(),
            'subscriberCount': len(subscriptions),
            'ready': get_vapid_public_key() != 'PLACEHOLDER_VAPID_PUBLIC_KEY_GENERATE_WITH_WEB_PUSH'
        }
        
        self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        """Subscribe to push notifications."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode()
            data = json.loads(body)
            
            subscription = data.get('subscription')
            preferences = data.get('preferences', {})
            
            if not subscription or not subscription.get('endpoint'):
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'error': 'Invalid subscription: endpoint required'
                }).encode())
                return
            
            # Generate subscription ID
            sub_id = generate_subscription_id(subscription['endpoint'])
            
            # Load existing subscriptions
            subscriptions = load_subscriptions()
            
            # Store subscription
            subscriptions[sub_id] = {
                'id': sub_id,
                'subscription': subscription,
                'preferences': {
                    'series': preferences.get('series', {
                        'f1': True,
                        'wrc': True,
                        'nascar': True,
                        'indycar': True,
                        'motogp': True,
                        'wec': True,
                        'imsa': True,
                        'sro': True
                    }),
                    'alerts': preferences.get('alerts', {
                        'raceStart15min': True,
                        'raceStart1hour': False,
                        'qualifying': False,
                        'practice': False,
                        'results': True
                    })
                },
                'created': datetime.utcnow().isoformat() + 'Z',
                'lastActive': datetime.utcnow().isoformat() + 'Z'
            }
            
            save_subscriptions(subscriptions)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                'status': 'subscribed',
                'id': sub_id,
                'preferences': subscriptions[sub_id]['preferences']
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

    def do_DELETE(self):
        """Unsubscribe from push notifications."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
            data = json.loads(body)
            
            endpoint = data.get('endpoint')
            if not endpoint:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Endpoint required'}).encode())
                return
            
            sub_id = generate_subscription_id(endpoint)
            subscriptions = load_subscriptions()
            
            if sub_id in subscriptions:
                del subscriptions[sub_id]
                save_subscriptions(subscriptions)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps({
                'status': 'unsubscribed',
                'id': sub_id
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
