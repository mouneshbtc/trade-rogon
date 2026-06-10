"""Databento implementation of `MarketDataProvider`.

Only the canonical 1-minute schema is fetched here — every higher timeframe is
built internally by `BarAggregator` so the engine's bar boundaries are defined
by *our* session/timeframe rules, not whatever a vendor happens to pre-aggregate.
A swap to another vendor means writing a new subclass of `MarketDataProvider`;
nothing else in the system would change.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import databento as db
import pandas as pd
import structlog

from app.config import settings
from app.market_data.provider import LiveBarCallback, MarketDataProvider
from app.schemas.market_data import NormalizedBar, Timeframe

logger = structlog.get_logger(__name__)

DATABENTO_BASE_SCHEMA = "ohlcv-1m"
DATABENTO_BASE_TIMEFRAME: Timeframe = "1m"


class DatabentoProvider(MarketDataProvider):
    def __init__(self, api_key: str | None = None, dataset: str | None = None) -> None:
        self._api_key = api_key or settings.databento_api_key
        self._dataset = dataset or settings.databento_dataset
        self._historical = db.Historical(key=self._api_key)

    async def get_historical(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> AsyncIterator[NormalizedBar]:
        if timeframe != DATABENTO_BASE_TIMEFRAME:
            raise ValueError(
                f"DatabentoProvider only fetches the {DATABENTO_BASE_TIMEFRAME} base schema "
                f"({timeframe!r} requested) — use BarAggregator to build higher timeframes"
            )

        store = await self._historical.timeseries.get_range_async(
            dataset=self._dataset,
            start=start,
            end=end,
            symbols=[symbol],
            schema=DATABENTO_BASE_SCHEMA,
            stype_in="continuous",
        )

        frame = store.to_df(price_type="float", tz=UTC)
        for ts_index, row in frame.iterrows():
            yield NormalizedBar(
                symbol=symbol,
                timeframe=DATABENTO_BASE_TIMEFRAME,
                ts=ts_index.to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                is_closed=True,
            )

    async def subscribe_live(self, symbol: str, timeframe: Timeframe, callback: LiveBarCallback) -> None:
        if timeframe != DATABENTO_BASE_TIMEFRAME:
            raise ValueError(
                f"DatabentoProvider only streams the {DATABENTO_BASE_TIMEFRAME} base schema "
                f"({timeframe!r} requested) — use BarAggregator to build higher timeframes"
            )

        live = db.Live(key=self._api_key)

        async def _on_record(record: db.DBNRecord) -> None:
            if not isinstance(record, db.OHLCVMsg):
                return
            assert record.pretty_ts_event is not None
            bar = NormalizedBar(
                symbol=symbol,
                timeframe=DATABENTO_BASE_TIMEFRAME,
                ts=pd.Timestamp(record.pretty_ts_event).to_pydatetime(),
                open=record.pretty_open,
                high=record.pretty_high,
                low=record.pretty_low,
                close=record.pretty_close,
                volume=float(record.volume),
                is_closed=True,
            )
            await callback(bar)

        def _on_record_sync(record: db.DBNRecord) -> None:
            import asyncio

            asyncio.create_task(_on_record(record))

        def _on_exception(exc: Exception) -> None:
            logger.exception("databento_live_stream_error", symbol=symbol, error=str(exc))

        live.add_callback(record_callback=_on_record_sync, exception_callback=_on_exception)
        live.subscribe(
            dataset=self._dataset,
            schema=DATABENTO_BASE_SCHEMA,
            symbols=[symbol],
            stype_in="continuous",
        )
        live.start()
        try:
            await live.wait_for_close()
        finally:
            live.stop()
