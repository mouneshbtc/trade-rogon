"""Builds higher-timeframe bars from a stream of lower-timeframe (1m) bars.

The engine aggregates internally rather than trusting a vendor's pre-rolled
bars, so every consumer sees bar boundaries defined by *our* rules — and so
the same aggregation logic runs identically over live data and historical
replays in the backtester.
"""

from datetime import UTC, datetime, timedelta

from app.schemas.market_data import NormalizedBar, Timeframe

TIMEFRAME_MINUTES: dict[Timeframe, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}


class BarAggregator:
    """Rolls up ordered 1m bars into any higher timeframe.

    Intraday buckets (5m–4h) align to fixed windows since the Unix epoch.
    Daily/weekly buckets align to `session_anchor_hour` (UTC) — a futures
    trading day rolls over at the exchange's session break, not at midnight
    UTC. The value here is placeholder infrastructure config; the
    authoritative anchor should be confirmed with the trader when the
    session / Daily-Bias concepts are defined, and this re-pointed at it
    through configuration — never by changing detection code.
    """

    def __init__(self, session_anchor_hour: int = 18):
        if not 0 <= session_anchor_hour < 24:
            raise ValueError("session_anchor_hour must be in [0, 24)")
        self._session_anchor_hour = session_anchor_hour

    def aggregate(self, bars: list[NormalizedBar], target_timeframe: Timeframe) -> list[NormalizedBar]:
        """Roll `bars` (contiguous, ascending, single source timeframe) up into
        `target_timeframe` bars.

        Only *complete* buckets are returned — a bucket is emitted once a bar
        belonging to the following bucket has been observed, so the result
        never contains a still-forming (repaint-prone) bar.
        """
        if not bars:
            return []
        target_minutes = TIMEFRAME_MINUTES[target_timeframe]
        symbol = bars[0].symbol

        buckets: dict[datetime, list[NormalizedBar]] = {}
        order: list[datetime] = []
        for bar in bars:
            bucket_start = self._bucket_start(bar.ts, target_minutes, target_timeframe)
            if bucket_start not in buckets:
                buckets[bucket_start] = []
                order.append(bucket_start)
            buckets[bucket_start].append(bar)

        results: list[NormalizedBar] = []
        for index, bucket_start in enumerate(order):
            members = buckets[bucket_start]
            if index == len(order) - 1:
                bucket_end = bucket_start + timedelta(minutes=target_minutes)
                if bars[-1].ts < bucket_end:
                    continue  # last bucket may still be forming — withhold it
            results.append(
                NormalizedBar(
                    symbol=symbol,
                    timeframe=target_timeframe,
                    ts=bucket_start,
                    open=members[0].open,
                    high=max(m.high for m in members),
                    low=min(m.low for m in members),
                    close=members[-1].close,
                    volume=sum(m.volume for m in members),
                    is_closed=True,
                )
            )
        return results

    def _bucket_start(self, ts: datetime, target_minutes: int, timeframe: Timeframe) -> datetime:
        ts = ts.astimezone(UTC)
        if timeframe in ("1d", "1w"):
            return self._session_bucket_start(ts, timeframe)
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        elapsed_minutes = (ts - epoch).total_seconds() / 60
        bucket_index = int(elapsed_minutes // target_minutes)
        return epoch + timedelta(minutes=bucket_index * target_minutes)

    def _session_bucket_start(self, ts: datetime, timeframe: Timeframe) -> datetime:
        anchor = ts.replace(hour=self._session_anchor_hour, minute=0, second=0, microsecond=0)
        if ts < anchor:
            anchor -= timedelta(days=1)
        if timeframe == "1d":
            return anchor
        # Weekly bucket starts at the most recent Sunday's session-anchor bucket.
        days_since_sunday = (anchor.weekday() + 1) % 7  # Mon=0->1 ... Sat=5->6, Sun=6->0
        return anchor - timedelta(days=days_since_sunday)
