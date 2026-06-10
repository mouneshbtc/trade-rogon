"""The one interface every market data source must satisfy.

`MarketDataService` (and everything downstream of it) depends only on this
ABC — swapping Databento for another vendor means writing a new
`MarketDataProvider` subclass and changing a single DI wire-up, nothing else.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime

from app.schemas.market_data import NormalizedBar, Timeframe

LiveBarCallback = Callable[[NormalizedBar], Awaitable[None]]


class MarketDataProvider(ABC):
    """Source of normalized OHLCV bars for a symbol, historical or live."""

    @abstractmethod
    def get_historical(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> AsyncIterator[NormalizedBar]:
        """Yield closed bars for [start, end), in chronological order."""
        ...

    @abstractmethod
    async def subscribe_live(self, symbol: str, timeframe: Timeframe, callback: LiveBarCallback) -> None:
        """Invoke `callback` with each bar as it closes. Runs until cancelled."""
        ...
