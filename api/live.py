"""Live Race Detection API - checks all series for active sessions."""
from http.server import BaseHTTPRequestHandler
import json
import urllib.request
from datetime import datetime, timezone, timedelta

def check_f1_live() -> dict:
    """Check if F1 session is currently live via OpenF1."""
    try:
        url = "https://api.openf1.org/v1/sessions?session_key=latest"
        req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            sessions = json.loads(resp.read())
        
        if not sessions:
            return None
        
        session = sessions[0] if isinstance(sessions, list) else sessions
        
        # Check if session is recent (within last 4 hours)
        date_str = session.get("date_start")
        if date_str:
            # Parse ISO date
            start = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            end_estimate = start + timedelta(hours=3)  # Most sessions < 3 hours
            
            if start <= now <= end_estimate:
                return {
                    "series": "f1",
                    "series_name": "Formula 1",
                    "event": session.get("location") or session.get("circuit_short_name"),
                    "session": session.get("session_name"),
                    "session_type": session.get("session_type"),
                    "country": session.get("country_name"),
                    "started": date_str,
                    "status": "live"
                }
            elif now < start and (start - now) < timedelta(hours=1):
                return {
                    "series": "f1",
                    "series_name": "Formula 1", 
                    "event": session.get("location") or session.get("circuit_short_name"),
                    "session": session.get("session_name"),
                    "session_type": session.get("session_type"),
                    "country": session.get("country_name"),
                    "starts": date_str,
                    "status": "starting_soon"
                }
    except Exception as e:
        print(f"F1 check error: {e}")
    return None

def check_imsa_live() -> dict:
    """Check IMSA live timing for active sessions."""
    try:
        import ssl
        import websocket
        import random
        import string
        
        def gid(n=8):
            return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))
        
        ws_url = f"wss://livetiming.alkamelsystems.com/sockjs/{random.randint(100,999)}/{gid()}/websocket"
        ws = websocket.create_connection(ws_url, sslopt={"cert_reqs": ssl.CERT_NONE}, timeout=5)
        ws.settimeout(2)
        
        ws.recv()  # open frame
        
        # Connect
        msg = '{"msg":"connect","version":"1","support":["1"]}'
        ws.send(f'["{msg.replace(chr(34), chr(92)+chr(34))}"]')
        
        for _ in range(3):
            try:
                ws.recv()
            except:
                pass
        
        # Subscribe to sessions
        sub = '{"msg":"sub","id":"s1","name":"sessions","params":[]}'
        ws.send(f'["{sub.replace(chr(34), chr(92)+chr(34))}"]')
        
        # Check for data
        has_session = False
        session_data = None
        for _ in range(5):
            try:
                r = ws.recv()
                if '"added"' in r and '"sessions"' in r:
                    has_session = True
                    # Try to parse session data
                    try:
                        inner = r[3:-2].replace('\\"', '"')
                        data = json.loads(inner)
                        if data.get("msg") == "added":
                            session_data = data.get("fields", {})
                    except:
                        pass
            except:
                pass
        
        ws.close()
        
        if has_session:
            return {
                "series": "imsa",
                "series_name": "IMSA SportsCar",
                "event": session_data.get("name", "Live Session") if session_data else "Live Session",
                "session": session_data.get("session", "Race") if session_data else "Race",
                "status": "live"
            }
    except Exception as e:
        print(f"IMSA check error: {e}")
    return None

def check_wec_live() -> dict:
    """Check WEC for live events based on schedule."""
    try:
        url = "https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id=4413&s=2026"
        req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        
        events = data.get("events") or []
        now = datetime.now(timezone.utc)
        
        for event in events:
            date_str = event.get("dateEvent")
            if date_str:
                event_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                # WEC races can be 6-24 hours, check if within race window
                if event_date <= now <= event_date + timedelta(hours=24):
                    return {
                        "series": "wec",
                        "series_name": "WEC",
                        "event": event.get("strEvent"),
                        "venue": event.get("strVenue"),
                        "country": event.get("strCountry"),
                        "status": "live"
                    }
                elif now < event_date and (event_date - now) < timedelta(hours=2):
                    return {
                        "series": "wec",
                        "series_name": "WEC",
                        "event": event.get("strEvent"),
                        "venue": event.get("strVenue"),
                        "status": "starting_soon"
                    }
    except Exception as e:
        print(f"WEC check error: {e}")
    return None

def get_upcoming_races(limit: int = 5) -> list:
    """Get upcoming races across all series."""
    upcoming = []
    now = datetime.now(timezone.utc)
    
    # F1 upcoming
    try:
        url = "https://api.openf1.org/v1/sessions?year=2026&session_type=Race"
        req = urllib.request.Request(url, headers={"User-Agent": "GridView/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            sessions = json.loads(resp.read())
        
        for s in sessions:
            date_str = s.get("date_start")
            if date_str:
                start = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if start > now:
                    upcoming.append({
                        "series": "f1",
                        "series_name": "Formula 1",
                        "event": s.get("location") or s.get("circuit_short_name"),
                        "session": s.get("session_name"),
                        "country": s.get("country_name"),
                        "date": date_str,
                        "timestamp": start.timestamp()
                    })
    except:
        pass
    
    # Sort by date and limit
    upcoming.sort(key=lambda x: x.get("timestamp", 0))
    return upcoming[:limit]

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            
            live_races = []
            
            # Check each series
            f1 = check_f1_live()
            if f1:
                live_races.append(f1)
            
            # Only check IMSA if websocket module available
            try:
                import websocket
                imsa = check_imsa_live()
                if imsa:
                    live_races.append(imsa)
            except ImportError:
                pass
            
            wec = check_wec_live()
            if wec:
                live_races.append(wec)
            
            # Get upcoming
            upcoming = get_upcoming_races(5)
            
            response = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "live": live_races,
                "live_count": len(live_races),
                "upcoming": upcoming
            }
            
            self._send_json(response)
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'public, max-age=30')  # Short cache for live data
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
