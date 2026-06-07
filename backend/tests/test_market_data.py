"""Market data — bar aggregation correctness and idempotent ingestion.

Aggregation is the seam every higher-timeframe concept depends on: get bucket
boundaries or the forming-bar withholding wrong and every detector built on
top inherits repainting bars. Idempotent upsert is what makes replay-on-
reconnect (or re-running a historical ingest) safe.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.market_data.aggregator import BarAggregator
from app.market_data.repository import BarRepository, InstrumentRepository
from app.schemas.market_data import NormalizedBar


def _bar(ts: datetime, *, o=100.0, h=101.0, low=99.0, c=100.5, v=10.0) -> NormalizedBar:
    return NormalizedBar(
        symbol="NQ", timeframe="1m", ts=ts, open=o, high=h, low=low, close=c, volume=v, is_closed=True
    )


def _minutes(start: datetime, count: int) -> list[NormalizedBar]:
    return [_bar(start + timedelta(minutes=i)) for i in range(count)]


@pytest.fixture
def aggregator():
    return BarAggregator(session_anchor_hour=18)


def test_aggregate_builds_complete_intraday_buckets_aligned_to_epoch(aggregator):
    # Epoch-aligned 5m buckets: minutes 0-4 and 5-9 are separate buckets.
    start = datetime(2026, 1, 5, 14, 0, tzinfo=UTC)  # already a 5m boundary
    bars = _minutes(start, 12)  # spans 3 buckets: [0-4], [5-9], [10-11..]

    result = aggregator.aggregate(bars, "5m")

    # Only the first two buckets are complete — the third (10-14) is still forming.
    assert [b.ts for b in result] == [start, start + timedelta(minutes=5)]
    assert all(b.timeframe == "5m" for b in result)


def test_aggregate_withholds_forming_final_bucket(aggregator):
    start = datetime(2026, 1, 5, 14, 0, tzinfo=UTC)
    bars = _minutes(start, 5)  # exactly one 5m bucket — but no bar from the *next* bucket yet

    result = aggregator.aggregate(bars, "5m")

    assert result == []  # nothing confirms the bucket is closed, so withhold it


def test_aggregate_ohlcv_rolls_up_correctly(aggregator):
    start = datetime(2026, 1, 5, 14, 0, tzinfo=UTC)
    bars = [
        _bar(start + timedelta(minutes=0), o=100.0, h=101.0, low=99.5, c=100.2, v=5.0),
        _bar(start + timedelta(minutes=1), o=100.2, h=102.0, low=100.0, c=101.5, v=7.0),
        _bar(start + timedelta(minutes=2), o=101.5, h=101.8, low=98.0, c=99.0, v=3.0),
        # next bucket — confirms the first is closed
        _bar(start + timedelta(minutes=5), o=99.0, h=99.5, low=98.5, c=99.2, v=1.0),
    ]

    result = aggregator.aggregate(bars, "5m")

    assert len(result) == 1
    rolled = result[0]
    assert rolled.open == 100.0          # first member's open
    assert rolled.high == 102.0          # max high across members
    assert rolled.low == 98.0            # min low across members
    assert rolled.close == 99.0          # last member's close
    assert rolled.volume == 15.0         # summed volume


def test_aggregate_daily_buckets_align_to_session_anchor(aggregator):
    # session_anchor_hour=18 (UTC): the trading day rolls over at 18:00, not
    # midnight — a bar at 17:00 the next calendar day still belongs to the
    # *prior* session.
    session_start = datetime(2026, 1, 5, 18, 0, tzinfo=UTC)
    bars = [
        _bar(session_start),                           # Jan 5 18:00 -> opens the session
        _bar(session_start + timedelta(hours=23)),     # Jan 6 17:00 -> still same session
        _bar(session_start + timedelta(days=1)),       # Jan 6 18:00 -> confirms session closed
    ]

    result = aggregator.aggregate(bars, "1d")

    assert len(result) == 1
    assert result[0].ts == session_start
    assert result[0].open == bars[0].open
    assert result[0].close == bars[1].close


def test_aggregate_returns_empty_for_no_bars(aggregator):
    assert aggregator.aggregate([], "5m") == []


@pytest.mark.asyncio
async def test_upsert_many_is_idempotent(db):
    instruments = InstrumentRepository()
    bars_repo = BarRepository()
    instrument = await instruments.get_or_create(db, "NQ")

    start = datetime(2026, 1, 5, 14, 0, tzinfo=UTC)
    first_pass = _minutes(start, 3)
    await bars_repo.upsert_many(db, instrument.id, first_pass)

    end = start + timedelta(minutes=10)
    rows_after_first = await bars_repo.get_range(db, instrument.id, "1m", start, end)
    assert len(rows_after_first) == 3

    # Replay the exact same range — must not duplicate rows.
    await bars_repo.upsert_many(db, instrument.id, first_pass)
    rows_after_replay = await bars_repo.get_range(db, instrument.id, "1m", start, end)
    assert len(rows_after_replay) == 3

    # Re-ingesting with revised values overwrites in place rather than inserting.
    revised = [_bar(start, o=200.0, h=201.0, low=199.0, c=200.5, v=99.0)]
    await bars_repo.upsert_many(db, instrument.id, revised)
    rows_after_revision = await bars_repo.get_range(db, instrument.id, "1m", start, end)
    assert len(rows_after_revision) == 3
    revised_row = next(r for r in rows_after_revision if r.ts == start)
    assert float(revised_row.open) == 200.0
    assert float(revised_row.volume) == 99.0
