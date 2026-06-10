"""CLI: ingest historical NQ/ES bars from Databento via the existing market-data pipeline.

    python scripts/ingest_historical.py --symbol NQ.c.0 --months 12
    python scripts/ingest_historical.py --symbol ES.c.0 --months 12

Pulls [now - months, now) in calendar-month chunks so a 12-month, 1-minute
pull never holds more than ~one month of bars in memory at once. Each chunk
goes through `MarketDataService.ingest_historical_range()` — the same
fetch -> persist -> aggregate -> publish path used everywhere else. Bar
persistence is idempotent (upsert on conflict), so re-running this script for
an overlapping range is safe.

Caveat: `BarAggregator` withholds the last (still-forming) 1d/1w bucket of
each chunk. At a month boundary that bucket is re-emitted, now complete, when
the following chunk is ingested — so the daily/weekly bar for the last day of
each month is written twice (idempotent upsert handles this correctly) and is
briefly absent between the two runs. This does not affect the 15m timeframe
used by the execution model.
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog
from databento.common.error import BentoClientError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _dateutil import shift_months  # noqa: E402

from app.core.event_bus import get_event_bus  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.market_data.databento_provider import DatabentoProvider  # noqa: E402
from app.market_data.service import MarketDataService  # noqa: E402

logger = structlog.get_logger(__name__)

SUPPORTED_SYMBOLS = ("NQ.c.0", "ES.c.0")

# Databento's GLBX.MDP3 dataset lags real time by a short, variable margin
# (observed ~10 minutes); requesting an `end` past the available range raises
# a 422 from the API. Stay safely behind "now".
_DATA_AVAILABILITY_LAG = timedelta(minutes=30)


def _month_chunks(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Split [start, end) into calendar-month-aligned chunks."""
    chunks: list[tuple[datetime, datetime]] = []
    month_start = start.replace(day=1)
    while month_start < end:
        next_month_start = shift_months(month_start, 1)
        chunk_start = max(start, month_start)
        chunk_end = min(end, next_month_start)
        chunks.append((chunk_start, chunk_end))
        month_start = next_month_start
    return chunks


async def ingest(symbol: str, months: int) -> None:
    end = datetime.now(UTC).replace(second=0, microsecond=0) - _DATA_AVAILABILITY_LAG
    start = shift_months(end, -months)
    chunks = _month_chunks(start, end)

    provider = DatabentoProvider()
    service = MarketDataService(provider=provider, event_bus=get_event_bus())

    totals: dict[str, int] = {}
    for chunk_start, chunk_end in chunks:
        try:
            async with AsyncSessionLocal() as db:
                written = await service.ingest_historical_range(db, symbol, chunk_start, chunk_end)
                await db.commit()
        except BentoClientError as exc:
            if "dataset_unavailable_range" in str(exc):
                # Databento's licensed/available range can lag "now" by hours;
                # treat this as the practical end of available history.
                logger.warning(
                    "chunk_unavailable_stopping",
                    symbol=symbol,
                    chunk_start=chunk_start.isoformat(),
                    chunk_end=chunk_end.isoformat(),
                    error=str(exc),
                )
                break
            raise
        for timeframe, count in written.items():
            totals[timeframe] = totals.get(timeframe, 0) + count
        logger.info(
            "chunk_ingested",
            symbol=symbol,
            chunk_start=chunk_start.isoformat(),
            chunk_end=chunk_end.isoformat(),
            written=written,
        )

    logger.info("ingestion_complete", symbol=symbol, start=start.isoformat(), end=end.isoformat(), totals=totals)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest historical NQ/ES bars from Databento.")
    parser.add_argument("--symbol", required=True, choices=SUPPORTED_SYMBOLS, help="Continuous-contract symbol.")
    parser.add_argument("--months", required=True, type=int, help="Number of months of history to ingest, ending now.")
    args = parser.parse_args()

    if args.months <= 0:
        parser.error("--months must be a positive integer")

    configure_logging()
    asyncio.run(ingest(args.symbol, args.months))


if __name__ == "__main__":
    main()
