"""
chassis/__init__.py
Public surface of the L9 chassis library.
Every constellation node imports ONLY from here.
"""

from .lifecycle import on_shutdown, on_startup, shutdown, startup
from .registry import clear_handlers, get_handler_map, register_handler
from .router import route_packet

__all__ = [
    "register_handler",
    "get_handler_map",
    "clear_handlers",
    "route_packet",
    "startup",
    "shutdown",
    "on_startup",
    "on_shutdown",
]
