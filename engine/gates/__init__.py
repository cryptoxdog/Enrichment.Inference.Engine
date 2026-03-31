# engine/gates/__init__.py
"""Gates module — PacketEnvelope safety and protocol enforcement."""

from .packet_bridge import validate_packet, wrap_response

__all__ = ["validate_packet", "wrap_response"]
