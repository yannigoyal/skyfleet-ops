"""Fleet telemetry subsystem for SkyFleet Ops.

Public API:
    TelemetryUpdate         - Immutable telemetry snapshot dataclass
    TelemetryCache          - Thread-safe in-memory telemetry store
    TelemetrySource         - Abstract interface for telemetry providers
    create_telemetry_source - Factory that selects simulator or MAVLink gateway
    create_stream_router    - FastAPI router factory for the SSE endpoint
"""

from .cache import TelemetryCache
from .factory import create_telemetry_source
from .interface import TelemetrySource
from .models import TelemetryUpdate
from .stream import create_stream_router

__all__ = [
    "TelemetryUpdate",
    "TelemetryCache",
    "TelemetrySource",
    "create_telemetry_source",
    "create_stream_router",
]
