"""
WebSocket Timing Module for GridView

Provides real-time timing data from various racing series via WebSocket/SignalR connections.

Supported Series:
- F1: SignalR-based live timing (requires OpenF1 or direct connection)
- IMSA: Alkamelsystems SockJS/Meteor DDP protocol
- NASCAR: JSON polling (not WebSocket, but included for API consistency)
- IndyCar: Azure Blob polling (not WebSocket, but included for API consistency)
"""

from .f1_signalr import F1SignalRClient
from .alkamelsystems import AlkamelSystemsClient
from .nascar_feed import NASCARLiveFeed
from .indycar_feed import IndyCarLiveFeed

__all__ = [
    'F1SignalRClient',
    'AlkamelSystemsClient',
    'NASCARLiveFeed',
    'IndyCarLiveFeed',
]
