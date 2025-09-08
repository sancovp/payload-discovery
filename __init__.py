"""
PayloadDiscovery - A system for creating numbered instruction sequences for agent consumption.
"""

from .core import (
    PayloadDiscoveryPiece,
    PayloadDiscovery,
    safe_write_config,
    load_payload_discovery
)

__all__ = [
    "PayloadDiscoveryPiece",
    "PayloadDiscovery", 
    "safe_write_config",
    "load_payload_discovery"
]