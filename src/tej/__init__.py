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
    BadRequestError,
    NetworkError,
    NotFoundError,
    ProRequiredError,
    RateLimitError,
    ServerError,
    TejError,
)
from .models import Action, Envelope, Exchange, OHLCV, SnapshotRow

__all__ = [
    "__version__",
    "Action",
    "AsyncClient",
    "BadRequestError",
    "Client",
    "Envelope",
    "Exchange",
    "NetworkError",
    "NotFoundError",
    "OHLCV",
    "ProRequiredError",
    "RateLimitError",
    "ServerError",
    "SnapshotRow",
    "TejError",
]
