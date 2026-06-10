"""Liquidity Engine detector — pools, raids, outcomes.

All rules are resolved from ConceptDefinition.rules at call time.
No rule is hardcoded. The detector is a collection of pure functions:
same inputs → identical output (replay-safe).

Three-stage model:
  LiquidityPool (detected from bars or swing events)
  → LiquidityRaid (wick-through of an active pool)
  → LiquidityOutcome (Sweep / Run / Unresolved, via pluggable classifier)

Pool status is tracked internally and written as the pool's FINAL state
after detection completes — avoiding incremental UPDATE round-trips.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.liquidity.outcome_classifier import OutcomeClassifier, OutcomeType
from app.models.liquidity import (
    EQH,
    EQL,
    PDH,
    PDL,
    STATUS_ACTIVE,
    STATUS_RAIDED,
    STATUS_RESOLVED,
)

# ── In-memory facts (pre-persistence) ────────────────────────────────────────

@dataclass
class PoolFact:
    id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    concept_definition_version: int
    pool_type: str
    price: Decimal
    ts: datetime
    status: str = STATUS_ACTIVE
    source_bar_ts: datetime | None = None
    source_swing_event_ids: list[str] | None = None


@dataclass
class RaidFact:
    id: uuid.UUID
    pool_id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    concept_definition_version: int
    ts: datetime
    raid_price: Decimal


@dataclass
class OutcomeFact:
    id: uuid.UUID
    raid_id: uuid.UUID
    pool_id: uuid.UUID
    instrument_id: uuid.UUID
    timeframe: str
    concept_definition_version: int
    outcome_type: str
    ts: datetime
    close_price: Decimal
    outcome_model: str
    confirmation_delay_bars: int


@dataclass
class SwingRef:
    """Snapshot of a structural_event — passed in by the service layer."""

    event_id: uuid.UUID
    price: Decimal
    ts: datetime
    event_type: str  # "swing_high" | "swing_low"


# ── Pool detection ────────────────────────────────────────────────────────────

def detect_pdh_pdl_pools(
    daily_bars: list,
    instrument_id: uuid.UUID,
    working_timeframe: str,
    concept_definition_version: int,
) -> list[PoolFact]:
    """Create PDH/PDL pools from consecutive 1D bars.

    For each pair (prev_bar, curr_bar): PDH at prev_bar.high, PDL at
    prev_bar.low. Pool ts = curr_bar.ts (active from start of new session).

    daily_bars must be ordered by ts ascending and contain at least 2 bars.
    """
    if len(daily_bars) < 2:
        return []

    pools: list[PoolFact] = []
    for prev_bar, curr_bar in zip(daily_bars, daily_bars[1:]):
        pools.append(PoolFact(
            id=uuid.uuid4(),
            instrument_id=instrument_id,
            timeframe=working_timeframe,
            concept_definition_version=concept_definition_version,
            pool_type=PDH,
            price=Decimal(str(prev_bar.high)),
            ts=curr_bar.ts,
            source_bar_ts=prev_bar.ts,
        ))
        pools.append(PoolFact(
            id=uuid.uuid4(),
            instrument_id=instrument_id,
            timeframe=working_timeframe,
            concept_definition_version=concept_definition_version,
            pool_type=PDL,
            price=Decimal(str(prev_bar.low)),
            ts=curr_bar.ts,
            source_bar_ts=prev_bar.ts,
        ))
    return pools


def detect_eqh_eql_pools(
    swing_events: list[SwingRef],
    instrument_id: uuid.UUID,
    timeframe: str,
    concept_definition_version: int,
    tolerance: Decimal,
    min_cluster_size: int = 2,
) -> list[PoolFact]:
    """Create EQH/EQL pools from swing event clusters.

    All qualifying pairs are persisted independently — no first-cluster-wins
    pruning. A swing event can belong to multiple pools simultaneously.

    Pair (A, B) qualifies when:
      - |A.price − B.price| <= tolerance
      - No swing between A and B has price > max(A, B) (for EQH)
        or price < min(A, B) (for EQL)

    Pool price = max of the pair's prices (EQH: stops above highest high).
    Pool ts    = ts of the LATER swing in the pair (when cluster completes).
    """
    pools: list[PoolFact] = []
    highs = sorted([s for s in swing_events if s.event_type == "swing_high"], key=lambda s: s.ts)
    lows = sorted([s for s in swing_events if s.event_type == "swing_low"], key=lambda s: s.ts)

    def _cluster_pools(swings: list[SwingRef], pool_type: str, high_side: bool) -> list[PoolFact]:
        result = []
        n = len(swings)
        for i in range(n):
            for j in range(i + min_cluster_size - 1, n):
                if j == i:
                    continue
                a, b = swings[i], swings[j]
                if abs(a.price - b.price) > tolerance:
                    continue
                # No intervening swing that invalidates the cluster
                intervening = swings[i + 1: j]
                max_price = max(a.price, b.price)
                min_price = min(a.price, b.price)
                if high_side:
                    if any(s.price > max_price for s in intervening):
                        continue  # a higher high "took out" the level between them
                else:
                    if any(s.price < min_price for s in intervening):
                        continue  # a lower low "took out" the level between them

                pool_price = max_price if high_side else min_price
                result.append(PoolFact(
                    id=uuid.uuid4(),
                    instrument_id=instrument_id,
                    timeframe=timeframe,
                    concept_definition_version=concept_definition_version,
                    pool_type=pool_type,
                    price=pool_price,
                    ts=b.ts,
                    source_swing_event_ids=[str(a.event_id), str(b.event_id)],
                ))
        return result

    pools.extend(_cluster_pools(highs, EQH, high_side=True))
    pools.extend(_cluster_pools(lows, EQL, high_side=False))
    return pools


# ── Raid + Outcome detection ──────────────────────────────────────────────────

def _is_high_side(pool_type: str) -> bool:
    return pool_type in (PDH, EQH)


def _raid_triggered(bar, pool: PoolFact, *, raid_condition: str, gap_open_counts_as_raid: bool) -> bool:
    """Check whether bar wicks through the pool level."""
    high_side = _is_high_side(pool.pool_type)
    if high_side:
        wick = Decimal(str(bar.high))
        if not gap_open_counts_as_raid and Decimal(str(bar.open)) >= pool.price:
            return False  # bar opened above the level — no wick-through from inside
        return wick > pool.price if raid_condition == "strict_gt" else wick >= pool.price
    else:
        wick = Decimal(str(bar.low))
        if not gap_open_counts_as_raid and Decimal(str(bar.open)) <= pool.price:
            return False  # bar opened below the level
        return wick < pool.price if raid_condition == "strict_gt" else wick <= pool.price


def detect_raids_and_outcomes(
    bars: list,
    pools: list[PoolFact],
    classifier: OutcomeClassifier,
    instrument_id: uuid.UUID,
    timeframe: str,
    concept_definition_version: int,
    raid_condition: str = "strict_gt",
    gap_open_counts_as_raid: bool = False,
) -> tuple[list[RaidFact], list[OutcomeFact]]:
    """Walk bars in order; for each bar, check each active pool for a raid.

    Pool status is tracked locally and written back into PoolFact.status at
    the end, so the repository can insert pools with their final status in
    one pass (no incremental UPDATE round-trips needed).

    A resolved pool (Sweep or Run outcome recorded) is skipped for all
    subsequent bars — its liquidity has been taken.
    """
    raids: list[RaidFact] = []
    outcomes: list[OutcomeFact] = []

    # Local status mirror — updated as raids/outcomes are processed
    pool_status: dict[uuid.UUID, str] = {p.id: STATUS_ACTIVE for p in pools}

    for bar_idx, bar in enumerate(bars):
        bar_ts = bar.ts
        for pool in pools:
            # Pool must be active by this bar's ts
            if pool.ts > bar_ts:
                continue
            if pool_status[pool.id] == STATUS_RESOLVED:
                continue
            if not _raid_triggered(bar, pool, raid_condition=raid_condition, gap_open_counts_as_raid=gap_open_counts_as_raid):
                continue

            # ── Raid ──────────────────────────────────────────────────────────
            raid_id = uuid.uuid4()
            wick_price = Decimal(str(bar.high)) if _is_high_side(pool.pool_type) else Decimal(str(bar.low))
            raids.append(RaidFact(
                id=raid_id,
                pool_id=pool.id,
                instrument_id=instrument_id,
                timeframe=timeframe,
                concept_definition_version=concept_definition_version,
                ts=bar_ts,
                raid_price=wick_price,
            ))
            if pool_status[pool.id] == STATUS_ACTIVE:
                pool_status[pool.id] = STATUS_RAIDED

            # ── Outcome ───────────────────────────────────────────────────────
            result = classifier.classify(pool.price, pool.pool_type, bars, bar_idx)
            outcomes.append(OutcomeFact(
                id=uuid.uuid4(),
                raid_id=raid_id,
                pool_id=pool.id,
                instrument_id=instrument_id,
                timeframe=timeframe,
                concept_definition_version=concept_definition_version,
                outcome_type=result.outcome_type.value,
                ts=result.confirmation_ts,
                close_price=result.close_price,
                outcome_model=classifier.model_name,
                confirmation_delay_bars=result.confirmation_delay_bars,
            ))

            if result.outcome_type in (OutcomeType.SWEEP, OutcomeType.RUN):
                pool_status[pool.id] = STATUS_RESOLVED

    # Write final statuses back into PoolFact objects for the repository
    for pool in pools:
        pool.status = pool_status[pool.id]

    return raids, outcomes
