"""
F1 Live Timing SignalR Client

Reverse-engineered from livetiming.formula1.com
Protocol: Microsoft SignalR 1.5 over WebSocket

Connection Flow:
1. GET /signalr/negotiate - Get connection token and settings
2. Connect to WebSocket: wss://livetiming.formula1.com/signalr/connect
3. Send hub subscription: {"H":"Streaming","M":"Subscribe","A":[["Heartbeat","..."]]}
4. Receive real-time data updates

Available Topics:
- Heartbeat: Server heartbeat
- CarData.z: Compressed car telemetry data
- Position.z: Compressed position data  
- TimingStats: Timing statistics
- TimingData: Live timing data
- LapCount: Current lap information
- SessionInfo: Session metadata
- TrackStatus: Track conditions (flags, etc.)
- RaceControlMessages: Race control messages
- TeamRadio: Team radio transcripts
- DriverList: Driver information
- TimingAppData: Extended timing app data
- WeatherData: Weather conditions
- SessionData: Session configuration
- ExtrapolatedClock: Estimated session clock

Note: Many topics return .z compressed data (zlib deflate).
"""

import json
import time
import zlib
import urllib.request
import urllib.parse
import threading
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass
import logging

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

logger = logging.getLogger(__name__)


@dataclass
class SignalRConfig:
    """SignalR connection configuration."""
    connection_token: str
    connection_id: str
    protocol_version: str = "1.5"
    keep_alive_timeout: float = 20.0
    disconnect_timeout: float = 30.0


class F1SignalRClient:
    """
    F1 Live Timing SignalR Client
    
    Connects to livetiming.formula1.com via SignalR WebSocket protocol
    to receive real-time Formula 1 timing data.
    
    Usage:
        client = F1SignalRClient()
        client.on_message = lambda topic, data: print(f"{topic}: {data}")
        client.connect()
        
        # Subscribe to specific topics
        client.subscribe(["TimingData", "LapCount", "TrackStatus"])
        
        # Or subscribe to all available topics
        client.subscribe_all()
    """
    
    BASE_URL = "https://livetiming.formula1.com"
    WS_URL = "wss://livetiming.formula1.com/signalr/connect"
    
    # All available SignalR topics
    ALL_TOPICS = [
        "Heartbeat",
        "CarData.z",
        "Position.z",
        "TimingStats",
        "TimingData",
        "LapCount",
        "SessionInfo",
        "TrackStatus",
        "RaceControlMessages",
        "TeamRadio",
        "DriverList",
        "TimingAppData",
        "WeatherData",
        "SessionData",
        "ExtrapolatedClock",
        "TopThree",
        "RcmSeries",
        "ChampionshipPrediction",
    ]
    
    def __init__(self, user_agent: str = "GridView/1.0"):
        if not HAS_WEBSOCKET:
            raise ImportError("websocket-client package required: pip install websocket-client")
        
        self.user_agent = user_agent
        self.config: Optional[SignalRConfig] = None
        self.ws: Optional[websocket.WebSocketApp] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Callbacks
        self.on_message: Optional[Callable[[str, Any], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        
        # Message counter for SignalR protocol
        self._message_id = 0
    
    def negotiate(self) -> SignalRConfig:
        """
        Negotiate SignalR connection parameters.
        
        Returns:
            SignalRConfig with connection token and settings
        """
        connection_data = json.dumps([{"name": "Streaming"}])
        params = urllib.parse.urlencode({
            "connectionData": connection_data,
            "clientProtocol": "1.5"
        })
        
        url = f"{self.BASE_URL}/signalr/negotiate?{params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "*/*",
        })
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        
        self.config = SignalRConfig(
            connection_token=data["ConnectionToken"],
            connection_id=data["ConnectionId"],
            protocol_version=data.get("ProtocolVersion", "1.5"),
            keep_alive_timeout=data.get("KeepAliveTimeout", 20.0),
            disconnect_timeout=data.get("DisconnectTimeout", 30.0),
        )
        
        logger.info(f"Negotiated SignalR connection: {self.config.connection_id}")
        return self.config
    
    def _build_ws_url(self) -> str:
        """Build the WebSocket connection URL with auth token."""
        if not self.config:
            raise RuntimeError("Must call negotiate() first")
        
        connection_data = json.dumps([{"name": "Streaming"}])
        params = urllib.parse.urlencode({
            "connectionToken": self.config.connection_token,
            "connectionData": connection_data,
            "clientProtocol": self.config.protocol_version,
            "transport": "webSockets"
        })
        
        return f"{self.WS_URL}?{params}"
    
    def _decompress_data(self, data: str) -> Any:
        """
        Decompress zlib-compressed data from .z topics.
        
        F1 sends compressed data as base64-encoded zlib deflate.
        """
        try:
            import base64
            compressed = base64.b64decode(data)
            decompressed = zlib.decompress(compressed, -zlib.MAX_WBITS)
            return json.loads(decompressed.decode())
        except Exception as e:
            logger.debug(f"Decompression failed (may not be compressed): {e}")
            return data
    
    def _on_ws_message(self, ws, message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            # SignalR message types:
            # {} - Empty keep-alive
            # {"C": "msg_id", "M": [...]} - Hub messages
            # {"I": "id"} - Invocation result
            # {"E": "error"} - Error
            
            if not data:
                # Keep-alive
                return
            
            if "E" in data:
                logger.error(f"SignalR error: {data['E']}")
                if self.on_error:
                    self.on_error(Exception(data["E"]))
                return
            
            if "M" in data:
                # Hub messages
                for msg in data["M"]:
                    hub = msg.get("H", "")
                    method = msg.get("M", "")
                    args = msg.get("A", [])
                    
                    if hub.lower() == "streaming" and method == "feed":
                        # F1 feed update: A = [topic, data, timestamp?]
                        if len(args) >= 2:
                            topic = args[0]
                            payload = args[1]
                            
                            # Decompress if .z topic
                            if topic.endswith(".z"):
                                payload = self._decompress_data(payload)
                            
                            if self.on_message:
                                self.on_message(topic, payload)
            
            if "R" in data:
                # Invocation result
                result = data["R"]
                if self.on_message:
                    self.on_message("_result", result)
                    
        except json.JSONDecodeError:
            logger.warning(f"Non-JSON message received: {message[:100]}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _on_ws_error(self, ws, error):
        """Handle WebSocket error."""
        logger.error(f"WebSocket error: {error}")
        if self.on_error:
            self.on_error(error)
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self._running = False
        if self.on_disconnect:
            self.on_disconnect()
    
    def _on_ws_open(self, ws):
        """Handle WebSocket connection opened."""
        logger.info("WebSocket connected to F1 Live Timing")
        if self.on_connect:
            self.on_connect()
    
    def connect(self, topics: Optional[List[str]] = None):
        """
        Connect to F1 Live Timing SignalR hub.
        
        Args:
            topics: Optional list of topics to subscribe to on connect.
                   If None, subscribes to Heartbeat only.
        """
        if not self.config:
            self.negotiate()
        
        ws_url = self._build_ws_url()
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            header={
                "User-Agent": self.user_agent,
            },
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close,
        )
        
        self._running = True
        self._thread = threading.Thread(target=self._run_forever, daemon=True)
        self._thread.start()
        
        # Wait a moment for connection to establish
        time.sleep(0.5)
        
        if topics:
            self.subscribe(topics)
    
    def _run_forever(self):
        """Run WebSocket event loop."""
        self.ws.run_forever(
            ping_interval=15,
            ping_timeout=10,
        )
    
    def subscribe(self, topics: List[str]):
        """
        Subscribe to F1 timing topics.
        
        Args:
            topics: List of topic names (e.g., ["TimingData", "LapCount"])
        """
        if not self.ws:
            raise RuntimeError("Not connected. Call connect() first.")
        
        self._message_id += 1
        
        # SignalR hub invocation format
        msg = {
            "H": "Streaming",
            "M": "Subscribe",
            "A": [topics],
            "I": str(self._message_id)
        }
        
        self.ws.send(json.dumps(msg))
        logger.info(f"Subscribed to topics: {topics}")
    
    def subscribe_all(self):
        """Subscribe to all available F1 timing topics."""
        self.subscribe(self.ALL_TOPICS)
    
    def disconnect(self):
        """Disconnect from F1 Live Timing."""
        self._running = False
        if self.ws:
            self.ws.close()
            self.ws = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Disconnected from F1 Live Timing")
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._running and self.ws is not None


def test_connection():
    """
    Test F1 SignalR connection.
    
    Returns connection status and sample data.
    """
    results = {
        "negotiate": False,
        "connection_token": None,
        "protocol_version": None,
        "error": None
    }
    
    try:
        client = F1SignalRClient()
        config = client.negotiate()
        
        results["negotiate"] = True
        results["connection_token"] = config.connection_token[:20] + "..."
        results["protocol_version"] = config.protocol_version
        
    except Exception as e:
        results["error"] = str(e)
    
    return results


if __name__ == "__main__":
    # Simple test
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    def on_message(topic, data):
        print(f"\n[{topic}]")
        if isinstance(data, dict):
            print(json.dumps(data, indent=2)[:500])
        else:
            print(str(data)[:500])
    
    def on_connect():
        print("Connected!")
    
    def on_error(e):
        print(f"Error: {e}")
    
    client = F1SignalRClient()
    client.on_message = on_message
    client.on_connect = on_connect
    client.on_error = on_error
    
    try:
        client.connect(topics=["Heartbeat", "TimingData", "TrackStatus"])
        print("Listening for 30 seconds...")
        time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
