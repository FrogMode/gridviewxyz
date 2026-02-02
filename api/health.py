"""Health check endpoint."""
from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        response = {
            "status": "healthy",
            "app": "GridView",
            "version": "0.1.0",
            "endpoints": [
                "/api/health",
                "/api/f1/calendar",
                "/api/f1/standings",
                "/api/wrc/latest"
            ]
        }
        self.wfile.write(json.dumps(response, indent=2).encode())
