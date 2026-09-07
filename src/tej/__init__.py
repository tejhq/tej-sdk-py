"""Python SDK for `tej-api <https://api.tejhq.dev>`_.

Zero runtime dependencies. Sync + async clients with identical surface.

Quick start::

    from tej import Client

    c = Client()
    rows = c.ohlcv("RELIANCE", "nse", "2025-01-01", "2025-01-31")
    print(len(rows))

Async::

    import asyncio
    from tej import AsyncClient

    async def main():
        async with AsyncClient() as c:
            return await c.ohlcv("RELIANCE", "nse", "2025-01-01", "2025-01-31")

    asyncio.run(main())
"""

from ._version import __version__
from .async_client import AsyncClient
from .client import Client
from .exceptions import (
    AuthError,
    BadRequestError,
    NetworkError,
    NotFoundError,
    ProRequiredError,
    RateLimitError,
    ServerError,
    TejError,
)
from .models import (
    OHLCV,
    Action,
    AdjustedRow,
    Envelope,
    Exchange,
    MetricsRow,
    ResolveHit,
    SnapshotRow,
    SymbolInterval,
    UniverseMember,
)

__all__ = [
    "__version__",
    "Action",
    "AdjustedRow",
    "AsyncClient",
    "AuthError",
    "BadRequestError",
    "Client",
    "Envelope",
    "Exchange",
    "MetricsRow",
    "NetworkError",
    "NotFoundError",
    "OHLCV",
    "ProRequiredError",
    "RateLimitError",
    "ResolveHit",
    "ServerError",
    "SnapshotRow",
    "SymbolInterval",
    "TejError",
    "UniverseMember",
]
