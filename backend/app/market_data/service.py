"""Orchestrates ingestion, normalization, persistence, aggregation, and
publishing — the single place that turns a provider's bars into the canonical
feed every other module reacts to.

Downstream modules never talk to a provider, never aggregate timeframes
themselves, and never read forming bars: they subscribe to `BarClosedEvent`
and query `BarRepository` for closed, persisted, canonical data.
"""

import uuid
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import EventBus
from app.core.events import BarClosedEvent
from app.market_data.aggregator import TIMEFRAME_MINUTES, BarAggregator
from app.market_data.provider import MarketDataProvider
from app.market_data.repository import BarRepository, InstrumentRepository
from app.schemas.market_data import TIMEFRAME_ORDER, NormalizedBar, Timeframe

logger = structlog.get_logger(__name__)

BASE_TIMEFRAME: Timeframe = "1m"


class MarketDataService:
    def __init__(
        self,
        provider: MarketDataProvider,
        event_bus: EventBus,
        instrument_repository: InstrumentRepository | None = None,
        bar_repository: BarRepository | None = None,
        aggregator: BarAggregator | None = None,
    ) -> None:
        self._provider = provider
        self._event_bus = event_bus
        self._instruments = instrument_repository or InstrumentRepository()
        self._bars = bar_repository or BarRepository()
        self._aggregator = aggregator or BarAggregator()

    async def ingest_historical_range(
        self,
        db: AsyncSession,
        symbol: str,
        start: datetime,
        end: datetime,
        *,
        target_timeframes: list[Timeframe] | None = None,
    ) -> dict[Timeframe, int]:
        """Pull base (1m) bars for [start, end), persist them, build every
        higher timeframe from that same window, persist those too, and publish
        a `BarClosedEvent` per closed bar so the narrative engine can react to
        a historical replay exactly as it would to live data.

        Returns a count of bars written per timeframe.
        """
        instrument = await self._instruments.get_or_create(db, symbol)
        targets = target_timeframes or [tf for tf in TIMEFRAME_ORDER if tf != BASE_TIMEFRAME]

        base_bars: list[NormalizedBar] = [
            bar async for bar in self._provider.get_historical(symbol, BASE_TIMEFRAME, start, end)
        ]
        written: dict[Timeframe, int] = {}
        written[BASE_TIMEFRAME] = await self._persist_and_publish(db, instrument.id, symbol, base_bars)

        for timeframe in sorted(targets, key=lambda tf: TIMEFRAME_MINUTES[tf]):
            aggregated = self._aggregator.aggregate(base_bars, timeframe)
            written[timeframe] = await self._persist_and_publish(db, instrument.id, symbol, aggregated)

        return written

    async def _persist_and_publish(
        self,
        db: AsyncSession,
        instrument_id: uuid.UUID,
        symbol: str,
        bars: list[NormalizedBar],
    ) -> int:
        if not bars:
            return 0
        count = await self._bars.upsert_many(db, instrument_id, bars)
        for bar in bars:
            await self._event_bus.publish(
                BarClosedEvent(
                    instrument_id=instrument_id,
                    symbol=symbol,
                    timeframe=bar.timeframe,
                    bar_ts=bar.ts,
                )
            )
        logger.info("bars_persisted", symbol=symbol, timeframe=bars[0].timeframe, count=count)
        return count
