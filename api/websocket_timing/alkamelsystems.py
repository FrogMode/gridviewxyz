"""
Alkamelsystems Live Timing Client (IMSA, etc.)

Reverse-engineered from livetiming.alkamelsystems.com
Protocol: Meteor DDP over SockJS WebSocket

Connection Flow:
1. GET /sockjs/info - Verify WebSocket support
2. Connect to: wss://livetiming.alkamelsystems.com/sockjs/{3-digit}/{random-8-char}/websocket
3. Receive "o" (open frame)
4. Send DDP connect: {"msg":"connect","version":"1","support":["1","pre1","pre2"]}
5. Receive {"msg":"connected","session":"..."}
6. Subscribe to collections: {"msg":"sub","id":"uuid","name":"collection","params":[]}

Available Collections:
- sessions: Active timing sessions
- participants: Competitors/drivers
- timing: Live timing data
- trackmap: Track position data
- racecontrol: Race control messages
- weather: Weather conditions

Message Types:
- added: New document added to collection
- changed: Document updated
- removed: Document removed from collection
- ready: Subscription ready
- result: Method call result
"""

import json
import time
import random
import string
import threading
import ssl
from typing import Callable, Dict, List, Optional, Any
from dataclasses import dataclass
import logging

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

logger = logging.getLogger(__name__)


def generate_id(length: int = 8) -> str:
    """Generate random alphanumeric ID for SockJS."""
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


@dataclass
class DDPDocument:
    """Represents a DDP collection document."""
    id: str
    collection: str
    fields: Dict[str, Any]


class AlkamelSystemsClient:
    """
    Alkamelsystems Live Timing Client
    
    Connects to Alkamelsystems live timing via SockJS/Meteor DDP protocol.
    Used by IMSA and other racing series.
    
    Usage:
        client = AlkamelSystemsClient(series="imsa")
        client.on_document = lambda doc: print(f"{doc.collection}: {doc.fields}")
        client.connect()
        client.subscribe("timing")
        client.subscribe("participants")
    """
    
    # Series-specific base URLs
    SERIES_URLS = {
        "imsa": "livetiming.alkamelsystems.com",
        "elms": "livetiming.alkamelsystems.com",  # May redirect to backoffice
        "wec": "livetiming.alkamelsystems.com",   # May redirect to backoffice
    }
    
    # Known collections
    COLLECTIONS = [
        "sessions",
        "participants", 
        "timing",
        "trackmap",
        "racecontrol",
        "weather",
        "bestTimes",
        "cardata",
    ]
    
    def __init__(self, series: str = "imsa", ssl_verify: bool = False):
        if not HAS_WEBSOCKET:
            raise ImportError("websocket-client package required: pip install websocket-client")
        
        self.series = series.lower()
        self.base_host = self.SERIES_URLS.get(self.series, "livetiming.alkamelsystems.com")
        self.ssl_verify = ssl_verify
        
        self.ws: Optional[websocket.WebSocketApp] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._session_id: Optional[str] = None
        self._subscriptions: Dict[str, str] = {}  # name -> sub_id
        
        # Message counter for DDP protocol
        self._msg_id = 0
        
        # Callbacks
        self.on_document: Optional[Callable[[DDPDocument], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        self.on_ready: Optional[Callable[[str], None]] = None  # Called when subscription is ready
        
        # Document cache
        self.documents: Dict[str, Dict[str, DDPDocument]] = {}  # collection -> {id -> doc}
    
    def _build_ws_url(self) -> str:
        """Build SockJS WebSocket URL."""
        server_num = random.randint(100, 999)
        session_id = generate_id(8)
        return f"wss://{self.base_host}/sockjs/{server_num}/{session_id}/websocket"
    
    def _next_id(self) -> str:
        """Generate next message ID."""
        self._msg_id += 1
        return f"msg_{self._msg_id}"
    
    def _send_ddp(self, msg: Dict[str, Any]):
        """Send DDP message over SockJS."""
        if not self.ws:
            raise RuntimeError("Not connected")
        
        # SockJS wraps messages in array and escapes quotes
        json_str = json.dumps(msg)
        sockjs_msg = json.dumps([json_str])
        
        logger.debug(f"Sending: {json_str[:200]}")
        self.ws.send(sockjs_msg)
    
    def _parse_sockjs_message(self, raw: str) -> List[Dict]:
        """Parse SockJS message frame."""
        messages = []
        
        if raw.startswith('o'):
            # Open frame
            logger.debug("Received SockJS open frame")
            return [{"_sockjs": "open"}]
        
        if raw.startswith('h'):
            # Heartbeat
            return [{"_sockjs": "heartbeat"}]
        
        if raw.startswith('c'):
            # Close frame
            logger.debug(f"Received SockJS close frame: {raw}")
            return [{"_sockjs": "close", "data": raw}]
        
        if raw.startswith('a'):
            # Array of messages
            try:
                inner = raw[1:]  # Remove 'a' prefix
                arr = json.loads(inner)
                for item in arr:
                    if isinstance(item, str):
                        messages.append(json.loads(item))
                    else:
                        messages.append(item)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse SockJS message: {e}")
        
        return messages
    
    def _on_ws_message(self, ws, message: str):
        """Handle incoming WebSocket message."""
        try:
            ddp_messages = self._parse_sockjs_message(message)
            
            for msg in ddp_messages:
                if "_sockjs" in msg:
                    if msg["_sockjs"] == "open":
                        # Send DDP connect
                        self._send_ddp({
                            "msg": "connect",
                            "version": "1",
                            "support": ["1", "pre1", "pre2"]
                        })
                    continue
                
                msg_type = msg.get("msg", "")
                
                if msg_type == "connected":
                    self._session_id = msg.get("session")
                    logger.info(f"DDP connected, session: {self._session_id}")
                    if self.on_connect:
                        self.on_connect()
                
                elif msg_type == "ping":
                    self._send_ddp({"msg": "pong"})
                
                elif msg_type == "added":
                    collection = msg.get("collection", "")
                    doc_id = msg.get("id", "")
                    fields = msg.get("fields", {})
                    
                    doc = DDPDocument(id=doc_id, collection=collection, fields=fields)
                    
                    # Cache document
                    if collection not in self.documents:
                        self.documents[collection] = {}
                    self.documents[collection][doc_id] = doc
                    
                    logger.debug(f"Added to {collection}: {doc_id}")
                    if self.on_document:
                        self.on_document(doc)
                
                elif msg_type == "changed":
                    collection = msg.get("collection", "")
                    doc_id = msg.get("id", "")
                    fields = msg.get("fields", {})
                    cleared = msg.get("cleared", [])
                    
                    # Update cached document
                    if collection in self.documents and doc_id in self.documents[collection]:
                        doc = self.documents[collection][doc_id]
                        doc.fields.update(fields)
                        for key in cleared:
                            doc.fields.pop(key, None)
                    else:
                        doc = DDPDocument(id=doc_id, collection=collection, fields=fields)
                        if collection not in self.documents:
                            self.documents[collection] = {}
                        self.documents[collection][doc_id] = doc
                    
                    logger.debug(f"Changed in {collection}: {doc_id}")
                    if self.on_document:
                        self.on_document(self.documents[collection][doc_id])
                
                elif msg_type == "removed":
                    collection = msg.get("collection", "")
                    doc_id = msg.get("id", "")
                    
                    if collection in self.documents:
                        self.documents[collection].pop(doc_id, None)
                    logger.debug(f"Removed from {collection}: {doc_id}")
                
                elif msg_type == "ready":
                    subs = msg.get("subs", [])
                    for sub_id in subs:
                        # Find subscription name by ID
                        for name, sid in self._subscriptions.items():
                            if sid == sub_id:
                                logger.info(f"Subscription ready: {name}")
                                if self.on_ready:
                                    self.on_ready(name)
                                break
                
                elif msg_type == "nosub":
                    sub_id = msg.get("id", "")
                    error = msg.get("error", {})
                    logger.warning(f"Subscription failed {sub_id}: {error}")
                
                elif msg_type == "result":
                    result_id = msg.get("id", "")
                    result = msg.get("result")
                    error = msg.get("error")
                    if error:
                        logger.error(f"Method error {result_id}: {error}")
                    else:
                        logger.debug(f"Method result {result_id}: {result}")
                
                elif msg_type == "error":
                    logger.error(f"DDP error: {msg}")
                    if self.on_error:
                        self.on_error(Exception(str(msg)))
                        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            if self.on_error:
                self.on_error(e)
    
    def _on_ws_error(self, ws, error):
        """Handle WebSocket error."""
        logger.error(f"WebSocket error: {error}")
        if self.on_error:
            self.on_error(error)
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self._running = False
        self._session_id = None
        if self.on_disconnect:
            self.on_disconnect()
    
    def _on_ws_open(self, ws):
        """Handle WebSocket connection opened."""
        logger.info(f"WebSocket connected to {self.base_host}")
    
    def connect(self):
        """Connect to Alkamelsystems live timing."""
        ws_url = self._build_ws_url()
        
        ssl_opts = {}
        if not self.ssl_verify:
            ssl_opts = {"cert_reqs": ssl.CERT_NONE}
        
        self.ws = websocket.WebSocketApp(
            ws_url,
            header={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close,
        )
        
        self._running = True
        self._thread = threading.Thread(target=self._run_forever, daemon=True)
        self._thread.start()
    
    def _run_forever(self):
        """Run WebSocket event loop."""
        ssl_opts = {}
        if not self.ssl_verify:
            ssl_opts = {"cert_reqs": ssl.CERT_NONE}
        
        self.ws.run_forever(
            ping_interval=25,
            ping_timeout=10,
            sslopt=ssl_opts,
        )
    
    def subscribe(self, collection: str, params: Optional[List] = None):
        """
        Subscribe to a DDP collection.
        
        Args:
            collection: Name of collection (e.g., "timing", "participants")
            params: Optional parameters for subscription
        """
        if not self.ws or not self._session_id:
            raise RuntimeError("Not connected. Call connect() first and wait for on_connect.")
        
        sub_id = self._next_id()
        self._subscriptions[collection] = sub_id
        
        self._send_ddp({
            "msg": "sub",
            "id": sub_id,
            "name": collection,
            "params": params or []
        })
        
        logger.info(f"Subscribing to collection: {collection}")
    
    def subscribe_all(self):
        """Subscribe to all known collections."""
        for collection in self.COLLECTIONS:
            try:
                self.subscribe(collection)
                time.sleep(0.1)  # Small delay between subscriptions
            except Exception as e:
                logger.warning(f"Failed to subscribe to {collection}: {e}")
    
    def unsubscribe(self, collection: str):
        """Unsubscribe from a collection."""
        if collection in self._subscriptions:
            sub_id = self._subscriptions.pop(collection)
            self._send_ddp({
                "msg": "unsub",
                "id": sub_id
            })
            logger.info(f"Unsubscribed from: {collection}")
    
    def call_method(self, method: str, params: Optional[List] = None) -> str:
        """
        Call a Meteor method.
        
        Args:
            method: Method name
            params: Method parameters
            
        Returns:
            Message ID for tracking result
        """
        msg_id = self._next_id()
        self._send_ddp({
            "msg": "method",
            "method": method,
            "params": params or [],
            "id": msg_id
        })
        return msg_id
    
    def disconnect(self):
        """Disconnect from Alkamelsystems."""
        self._running = False
        if self.ws:
            self.ws.close()
            self.ws = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        self._session_id = None
        self._subscriptions.clear()
        logger.info("Disconnected from Alkamelsystems")
    
    def get_documents(self, collection: str) -> List[DDPDocument]:
        """Get all cached documents from a collection."""
        return list(self.documents.get(collection, {}).values())
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._running and self._session_id is not None


def check_service_status(series: str = "imsa") -> Dict[str, Any]:
    """
    Check if Alkamelsystems service is online.
    
    Returns:
        Dict with service status information
    """
    import urllib.request
    
    result = {
        "series": series,
        "sockjs_available": False,
        "websocket_supported": False,
        "error": None
    }
    
    try:
        host = AlkamelSystemsClient.SERIES_URLS.get(series.lower(), "livetiming.alkamelsystems.com")
        url = f"https://{host}/sockjs/info"
        
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0"
        })
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            data = json.loads(resp.read())
            result["sockjs_available"] = True
            result["websocket_supported"] = data.get("websocket", False)
            result["entropy"] = data.get("entropy")
            
    except Exception as e:
        result["error"] = str(e)
    
    return result


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    # Check service status
    print("Checking Alkamelsystems status...")
    status = check_service_status("imsa")
    print(json.dumps(status, indent=2))
    
    if not status["sockjs_available"]:
        print("Service not available")
        sys.exit(1)
    
    # Test connection
    def on_connect():
        print("\n=== Connected! Subscribing to collections... ===\n")
        client.subscribe("sessions")
        client.subscribe("timing")
    
    def on_document(doc):
        print(f"\n[{doc.collection}] {doc.id}")
        print(json.dumps(doc.fields, indent=2)[:500])
    
    def on_ready(name):
        print(f"\n=== Subscription ready: {name} ===")
    
    def on_error(e):
        print(f"\nError: {e}")
    
    client = AlkamelSystemsClient(series="imsa")
    client.on_connect = on_connect
    client.on_document = on_document
    client.on_ready = on_ready
    client.on_error = on_error
    
    try:
        client.connect()
        print("Listening for 30 seconds...")
        time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
