"""Liquidity Engine tests.

Covers the three-stage model (Pool → Raid → Outcome) with:
  - Pure-function tests for all detection logic (no DB)
  - Outcome classifier strategy tests
  - Repository integration tests (Postgres)
  - Service round-trip tests (Postgres)
  - HTTP API smoke tests

Bar data is provided via duck-typed _B namedtuples — the detector only reads
.high / .low / .open / .close / .ts attributes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import NamedTuple

import pytest

from app.liquidity.detector import (
    PoolFact,
    SwingRef,
    detect_eqh_eql_pools,
    detect_pdh_pdl_pools,
    detect_raids_and_outcomes,
)
from app.liquidity.outcome_classifier import (
    SameBarClassifier,
    get_classifier,
)
from app.liquidity.repository import LiquidityRepository
from app.models.liquidity import (
    EQH,
    EQL,
    OUTCOME_RUN,
    OUTCOME_SWEEP,
    OUTCOME_UNRESOLVED,
    PDH,
    PDL,
    STATUS_ACTIVE,
    STATUS_RAIDED,
    STATUS_RESOLVED,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_T0 = datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC)
_INST = uuid.uuid4()
_TF = "5m"
_CDV = 1
_TICK = Decimal("0.25")
_TOLERANCE = _TICK * 4  # 4 ticks = 1.0 point

_DEFAULT_RULES = {
    "close_at_level_outcome": "unresolved",
}


class _B(NamedTuple):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def _bars(*specs: tuple, base_ts: datetime = _T0) -> list[_B]:
    return [
        _B(ts=base_ts + timedelta(minutes=5 * i), open=o, high=h, low=lo, close=c)
        for i, (o, h, lo, c) in enumerate(specs)
    ]


def _pool(
    pool_type: str,
    price: float,
    ts: datetime = _T0,
    status: str = STATUS_ACTIVE,
) -> PoolFact:
    return PoolFact(
        id=uuid.uuid4(),
        instrument_id=_INST,
        timeframe=_TF,
        concept_definition_version=_CDV,
        pool_type=pool_type,
        price=Decimal(str(price)),
        ts=ts,
        status=status,
    )


def _classifier(**kw) -> SameBarClassifier:
    return SameBarClassifier(**kw)


def _detect(bars: list, pools: list[PoolFact], classifier=None):
    c = classifier or _classifier()
    return detect_raids_and_outcomes(
        bars=bars, pools=pools, classifier=c,
        instrument_id=_INST, timeframe=_TF,
        concept_definition_version=_CDV,
    )


# ── PDH / PDL pool detection ──────────────────────────────────────────────────

def test_pdh_pdl_from_consecutive_daily_bars():
    daily = _bars((100, 120, 95, 110), (110, 125, 108, 118))
    pools = detect_pdh_pdl_pools(daily, _INST, _TF, _CDV)
    assert len(pools) == 2
    types = {p.pool_type for p in pools}
    assert types == {PDH, PDL}


def test_pdh_price_is_previous_day_high():
    daily = _bars((100, 120, 95, 110), (110, 125, 108, 118))
    pools = detect_pdh_pdl_pools(daily, _INST, _TF, _CDV)
    pdh = next(p for p in pools if p.pool_type == PDH)
    assert pdh.price == Decimal("120")


def test_pdl_price_is_previous_day_low():
    daily = _bars((100, 120, 95, 110), (110, 125, 108, 118))
    pools = detect_pdh_pdl_pools(daily, _INST, _TF, _CDV)
    pdl = next(p for p in pools if p.pool_type == PDL)
    assert pdl.price == Decimal("95")


def test_pdh_pdl_ts_is_new_session_open():
    daily = _bars((100, 120, 95, 110), (110, 125, 108, 118))
    pools = detect_pdh_pdl_pools(daily, _INST, _TF, _CDV)
    new_session_ts = daily[1].ts
    assert all(p.ts == new_session_ts for p in pools)


def test_no_pools_from_single_daily_bar():
    daily = _bars((100, 120, 95, 110))
    pools = detect_pdh_pdl_pools(daily, _INST, _TF, _CDV)
    assert pools == []


def test_three_daily_bars_produce_two_days_of_pools():
    daily = _bars(
        (100, 110, 95, 105),
        (105, 115, 100, 112),
        (112, 120, 108, 118),
    )
    pools = detect_pdh_pdl_pools(daily, _INST, _TF, _CDV)
    assert len(pools) == 4  # 2 days × 2 (pdh + pdl)


def test_source_bar_ts_set_for_pdh_pdl():
    daily = _bars((100, 120, 95, 110), (110, 125, 108, 118))
    pools = detect_pdh_pdl_pools(daily, _INST, _TF, _CDV)
    for p in pools:
        assert p.source_bar_ts == daily[0].ts  # previous bar's ts


# ── EQH / EQL pool detection ──────────────────────────────────────────────────

def _sh(price: float, ts: datetime) -> SwingRef:
    return SwingRef(event_id=uuid.uuid4(), price=Decimal(str(price)), ts=ts, event_type="swing_high")


def _sl(price: float, ts: datetime) -> SwingRef:
    return SwingRef(event_id=uuid.uuid4(), price=Decimal(str(price)), ts=ts, event_type="swing_low")


_SH_T0 = _T0
_SH_T1 = _T0 + timedelta(minutes=5)
_SH_T2 = _T0 + timedelta(minutes=10)
_SH_T3 = _T0 + timedelta(minutes=15)


def test_eqh_pair_within_tolerance():
    swings = [_sh(100.0, _SH_T0), _sh(100.5, _SH_T1)]
    pools = detect_eqh_eql_pools(swings, _INST, _TF, _CDV, tolerance=Decimal("1.0"))
    assert len(pools) == 1
    assert pools[0].pool_type == EQH


def test_eqh_pair_outside_tolerance_no_pool():
    swings = [_sh(100.0, _SH_T0), _sh(102.0, _SH_T1)]
    pools = detect_eqh_eql_pools(swings, _INST, _TF, _CDV, tolerance=Decimal("1.0"))
    assert pools == []


def test_eqh_level_is_highest_in_cluster():
    swings = [_sh(100.0, _SH_T0), _sh(100.5, _SH_T1)]
    pools = detect_eqh_eql_pools(swings, _INST, _TF, _CDV, tolerance=Decimal("1.0"))
    assert pools[0].price == Decimal("100.5")


def test_eqh_pool_ts_is_later_swing():
    swings = [_sh(100.0, _SH_T0), _sh(100.5, _SH_T1)]
    pools = detect_eqh_eql_pools(swings, _INST, _TF, _CDV, tolerance=Decimal("1.0"))
    assert pools[0].ts == _SH_T1


def test_eqh_swing_can_belong_to_multiple_pools():
    """No first-cluster-wins: B appears in pairs (A,B) and (B,C)."""
    swings = [
        _sh(100.0, _SH_T0),  # A
        _sh(100.3, _SH_T1),  # B — within tolerance of A and C
        _sh(100.6, _SH_T2),  # C — within tolerance of B
    ]
    pools = detect_eqh_eql_pools(swings, _INST, _TF, _CDV, tolerance=Decimal("1.0"))
    # Pairs: (A,B), (A,C), (B,C) — all within 1.0 tolerance
    assert len(pools) == 3


def test_eqh_intervening_higher_high_invalidates_pair():
    swings = [
        _sh(100.0, _SH_T0),
        _sh(110.0, _SH_T1),  # higher than both — invalidates (T0, T2) pair
        _sh(100.5, _SH_T2),
    ]
    pools = detect_eqh_eql_pools(swings, _INST, _TF, _CDV, tolerance=Decimal("1.0"))
    # (T0, T2) pair: intervening T1.price=110 > max(100,100.5)=100.5 → invalid
    # (T0, T1): |100.0 - 110.0| = 10.0 > 1.0 → invalid
    # (T1, T2): |110.0 - 100.5| = 9.5 > 1.0 → invalid
    assert pools == []


def test_eql_pool_level_is_lowest_in_cluster():
    swings = [_sl(98.0, _SH_T0), _sl(98.5, _SH_T1)]
    pools = detect_eqh_eql_pools(swings, _INST, _TF, _CDV, tolerance=Decimal("1.0"))
    assert len(pools) == 1
    assert pools[0].pool_type == EQL
    assert pools[0].price == Decimal("98.0")  # min of the pair


def test_eqh_source_swing_event_ids_populated():
    a, b = _sh(100.0, _SH_T0), _sh(100.5, _SH_T1)
    pools = detect_eqh_eql_pools([a, b], _INST, _TF, _CDV, tolerance=Decimal("1.0"))
    assert pools[0].source_swing_event_ids == [str(a.event_id), str(b.event_id)]


# ── Raid detection ────────────────────────────────────────────────────────────

def test_raid_fires_on_wick_above_pdh():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 99))  # high=101 > 100 → raid
    raids, _ = _detect(bars, [pool])
    assert len(raids) == 1


def test_no_raid_on_exact_touch_strict_gt():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 100.0, 98, 99))  # high == 100 exactly — strict_gt → no raid
    raids, _ = _detect(bars, [pool])
    assert raids == []


def test_no_raid_when_close_exceeds_but_wick_does_not():
    # close > pool price but high == pool price (impossible in real markets,
    # but ensures we're checking wick, not close)
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 100.0, 98, 100.5))  # high == 100, close=100.5 (hypothetical)
    # close > pool.price but high == pool.price → no raid (wick-basis, strict_gt)
    raids, _ = _detect(bars, [pool])
    assert raids == []


def test_raid_fires_on_wick_below_pdl():
    pool = _pool(PDL, 100.0, ts=_T0)
    bars = _bars((101, 102, 99, 101))  # low=99 < 100 → raid
    raids, _ = _detect(bars, [pool])
    assert len(raids) == 1


def test_no_raid_on_exact_touch_pdl():
    pool = _pool(PDL, 100.0, ts=_T0)
    bars = _bars((101, 102, 100.0, 101))  # low == 100 → no raid
    raids, _ = _detect(bars, [pool])
    assert raids == []


def test_no_raid_before_pool_ts():
    # Pool ts is at bar 2; bars 0 and 1 are before the pool is active
    pool_ts = _T0 + timedelta(minutes=10)
    pool = _pool(PDH, 100.0, ts=pool_ts)
    bars = _bars(
        (99, 101, 98, 99),  # bar 0: ts=_T0, would raid but pool not active yet
        (99, 101, 98, 99),  # bar 1: ts=_T0+5m, same
        (99, 101, 98, 99),  # bar 2: ts=_T0+10m == pool_ts — now active → raids
    )
    raids, _ = _detect(bars, [pool])
    assert len(raids) == 1
    assert raids[0].ts == bars[2].ts


def test_no_raid_gap_open_above_pdh():
    pool = _pool(PDH, 100.0, ts=_T0)
    # open=102 > pool.price (gap open above) → not a wick-through from inside
    bars = _bars((102, 105, 101, 103))
    raids, _ = _detect(bars, [pool], classifier=_classifier())
    raids2, _ = detect_raids_and_outcomes(
        bars=bars, pools=[pool], classifier=_classifier(),
        instrument_id=_INST, timeframe=_TF,
        concept_definition_version=_CDV,
        gap_open_counts_as_raid=False,
    )
    assert raids2 == []


def test_raid_gap_open_counted_when_configured():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((102, 105, 101, 103))  # gap open above
    raids, _ = detect_raids_and_outcomes(
        bars=bars, pools=[pool], classifier=_classifier(),
        instrument_id=_INST, timeframe=_TF,
        concept_definition_version=_CDV,
        gap_open_counts_as_raid=True,
    )
    assert len(raids) == 1


def test_multiple_raids_on_same_pool():
    # close=99 < 100 → Sweep → pool resolved → no second raid
    # Let's use a close that produces Unresolved to allow another raid
    pool2 = _pool(PDH, 100.0, ts=_T0)
    bars2 = _bars(
        (99, 101, 98, 100.0),  # high=101>100, close=100 exactly → Unresolved → pool stays raided
        (99, 101, 98, 100.0),  # second raid possible (pool not resolved)
    )
    classifier = _classifier(close_at_level_outcome="unresolved")
    raids, outcomes = detect_raids_and_outcomes(
        bars=bars2, pools=[pool2], classifier=classifier,
        instrument_id=_INST, timeframe=_TF, concept_definition_version=_CDV,
    )
    assert len(raids) == 2
    assert len(outcomes) == 2
    assert all(o.outcome_type == OUTCOME_UNRESOLVED for o in outcomes)


# ── Outcome classification ────────────────────────────────────────────────────

def test_sweep_high_side():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 99))  # high=101>100, close=99<100 → Sweep
    _, outcomes = _detect(bars, [pool])
    assert len(outcomes) == 1
    assert outcomes[0].outcome_type == OUTCOME_SWEEP


def test_run_high_side():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 101))  # high=101>100, close=101>100 → Run
    _, outcomes = _detect(bars, [pool])
    assert outcomes[0].outcome_type == OUTCOME_RUN


def test_unresolved_close_at_level():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 100.0))  # close exactly at 100 → Unresolved
    _, outcomes = _detect(bars, [pool])
    assert outcomes[0].outcome_type == OUTCOME_UNRESOLVED


def test_sweep_low_side():
    pool = _pool(PDL, 100.0, ts=_T0)
    bars = _bars((101, 102, 99, 101))  # low=99<100, close=101>100 → Sweep
    _, outcomes = _detect(bars, [pool])
    assert outcomes[0].outcome_type == OUTCOME_SWEEP


def test_run_low_side():
    pool = _pool(PDL, 100.0, ts=_T0)
    bars = _bars((101, 102, 99, 99))  # low=99<100, close=99<100 → Run
    _, outcomes = _detect(bars, [pool])
    assert outcomes[0].outcome_type == OUTCOME_RUN


def test_outcome_links_to_raid_id():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 99))
    raids, outcomes = _detect(bars, [pool])
    assert outcomes[0].raid_id == raids[0].id


def test_outcome_links_to_pool_id():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 99))
    raids, outcomes = _detect(bars, [pool])
    assert outcomes[0].pool_id == pool.id


# ── Pool status lifecycle ─────────────────────────────────────────────────────

def test_pool_status_active_when_no_raids():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((98, 99, 97, 98))  # no raid
    _detect(bars, [pool])
    assert pool.status == STATUS_ACTIVE


def test_pool_status_raided_after_unresolved():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 100.0))  # unresolved
    _detect(bars, [pool])
    assert pool.status == STATUS_RAIDED


def test_pool_status_resolved_after_sweep():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 99))  # sweep
    _detect(bars, [pool])
    assert pool.status == STATUS_RESOLVED


def test_pool_status_resolved_after_run():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 102))  # run
    _detect(bars, [pool])
    assert pool.status == STATUS_RESOLVED


def test_no_raids_after_resolved():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars(
        (99, 101, 98, 99),  # bar 0: sweep → resolved
        (99, 101, 98, 99),  # bar 1: would raid again but pool is resolved
    )
    raids, outcomes = _detect(bars, [pool])
    assert len(raids) == 1   # only the first raid
    assert len(outcomes) == 1


def test_outcome_model_recorded():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 99))
    _, outcomes = _detect(bars, [pool])
    assert outcomes[0].outcome_model == "same_bar"


def test_confirmation_delay_bars_zero_for_same_bar():
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 99))
    _, outcomes = _detect(bars, [pool])
    assert outcomes[0].confirmation_delay_bars == 0


# ── Outcome classifier registry ───────────────────────────────────────────────

def test_get_classifier_same_bar():
    c = get_classifier("same_bar", {})
    assert isinstance(c, SameBarClassifier)
    assert c.model_name == "same_bar"


def test_get_classifier_unknown_raises():
    with pytest.raises(ValueError, match="Unknown outcome_timing"):
        get_classifier("crystal_ball", {})


def test_same_bar_classifier_respects_close_at_level_config():
    c_sweep = SameBarClassifier(close_at_level_outcome="sweep")
    pool = _pool(PDH, 100.0, ts=_T0)
    bars = _bars((99, 101, 98, 100.0))
    _, outcomes = detect_raids_and_outcomes(
        bars=bars, pools=[pool], classifier=c_sweep,
        instrument_id=_INST, timeframe=_TF, concept_definition_version=_CDV,
    )
    assert outcomes[0].outcome_type == OUTCOME_SWEEP


# ── Repository integration (Postgres) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_repository_save_and_retrieve_pool(db):
    repo = LiquidityRepository()
    pool = _pool(PDH, 110.5, ts=_T0)
    saved = await repo.save_pools(db, [pool])
    assert len(saved) == 1

    retrieved = await repo.get_pools(db, _INST, _TF)
    assert any(p.price == Decimal("110.5") for p in retrieved)


@pytest.mark.asyncio
async def test_repository_save_raid_linked_to_pool(db):
    from app.liquidity.detector import RaidFact

    repo = LiquidityRepository()
    pool = _pool(PDH, 100.0, ts=_T0)
    await repo.save_pools(db, [pool])

    raid = RaidFact(
        id=uuid.uuid4(),
        pool_id=pool.id,
        instrument_id=_INST,
        timeframe=_TF,
        concept_definition_version=_CDV,
        ts=_T0 + timedelta(minutes=5),
        raid_price=Decimal("100.5"),
    )
    saved = await repo.save_raids(db, [raid])
    assert len(saved) == 1
    assert saved[0].pool_id == pool.id


@pytest.mark.asyncio
async def test_repository_save_outcome_linked_to_raid(db):
    from app.liquidity.detector import OutcomeFact, RaidFact

    repo = LiquidityRepository()
    pool = _pool(PDH, 100.0, ts=_T0)
    await repo.save_pools(db, [pool])

    raid = RaidFact(
        id=uuid.uuid4(), pool_id=pool.id, instrument_id=_INST, timeframe=_TF,
        concept_definition_version=_CDV, ts=_T0 + timedelta(minutes=5),
        raid_price=Decimal("100.5"),
    )
    await repo.save_raids(db, [raid])

    outcome = OutcomeFact(
        id=uuid.uuid4(), raid_id=raid.id, pool_id=pool.id, instrument_id=_INST,
        timeframe=_TF, concept_definition_version=_CDV, outcome_type=OUTCOME_SWEEP,
        ts=_T0 + timedelta(minutes=5), close_price=Decimal("99.5"),
        outcome_model="same_bar", confirmation_delay_bars=0,
    )
    saved = await repo.save_outcomes(db, [outcome])
    assert saved[0].outcome_type == OUTCOME_SWEEP


@pytest.mark.asyncio
async def test_repository_delete_clears_all(db):
    from app.liquidity.detector import OutcomeFact, RaidFact

    inst2 = uuid.uuid4()
    repo = LiquidityRepository()
    pool = PoolFact(
        id=uuid.uuid4(), instrument_id=inst2, timeframe=_TF,
        concept_definition_version=_CDV, pool_type=PDH, price=Decimal("100"),
        ts=_T0,
    )
    await repo.save_pools(db, [pool])

    raid = RaidFact(
        id=uuid.uuid4(), pool_id=pool.id, instrument_id=inst2, timeframe=_TF,
        concept_definition_version=_CDV, ts=_T0 + timedelta(minutes=5),
        raid_price=Decimal("100.5"),
    )
    await repo.save_raids(db, [raid])

    outcome = OutcomeFact(
        id=uuid.uuid4(), raid_id=raid.id, pool_id=pool.id, instrument_id=inst2,
        timeframe=_TF, concept_definition_version=_CDV, outcome_type=OUTCOME_SWEEP,
        ts=_T0 + timedelta(minutes=5), close_price=Decimal("99"),
        outcome_model="same_bar", confirmation_delay_bars=0,
    )
    await repo.save_outcomes(db, [outcome])

    await repo.delete_for_range(db, inst2, _TF)
    remaining = await repo.get_pools(db, inst2, _TF)
    assert remaining == []


# ── Service integration (Postgres) ────────────────────────────────────────────

async def _seed_liquidity_concept(db) -> int:
    from app.concepts.registry import ConceptDefinitionRegistry
    registry = ConceptDefinitionRegistry()
    cd = await registry.propose_version(
        db,
        concept_name="liquidity",
        rules={
            "pool_types": ["pdh", "pdl", "eqh", "eql"],
            "session_timezone": "America/New_York",
            "daily_session": "globex",
            "eqh_eql_tolerance_ticks": 4,
            "eqh_eql_min_cluster_size": 2,
            "eqh_eql_level": "highest_in_cluster",
            "raid_condition": "strict_gt",
            "gap_open_counts_as_raid": False,
            "outcome_timing": "same_bar",
            "close_at_level_outcome": "unresolved",
            "tick_size_points": 0.25,
        },
        notes="V1 — proposed defaults",
        created_by="test",
    )
    await registry.activate_version(db, concept_name="liquidity", version=cd.version, at=_T0)
    return cd.version


@pytest.mark.asyncio
async def test_service_requires_active_concept(db):
    from app.concepts.exceptions import ConceptNotDefinedError
    from app.liquidity.service import LiquidityService

    svc = LiquidityService()
    with pytest.raises(ConceptNotDefinedError):
        await svc.detect_and_persist(db, uuid.uuid4(), _TF, _T0, _T0 + timedelta(hours=1))


@pytest.mark.asyncio
async def test_service_returns_empty_for_no_bars(db):
    from app.liquidity.service import LiquidityService

    await _seed_liquidity_concept(db)
    svc = LiquidityService()
    pools, raids, outcomes = await svc.detect_and_persist(
        db, uuid.uuid4(), _TF, _T0, _T0 + timedelta(hours=1)
    )
    assert pools == []
    assert raids == []
    assert outcomes == []


@pytest.mark.asyncio
async def test_service_detects_pdh_pdl_from_daily_bars(db):
    from app.liquidity.service import LiquidityService
    from app.models.market_data import Bar, Instrument

    await _seed_liquidity_concept(db)

    inst = Instrument(symbol="NQ_LIQ_TEST", exchange="CME", contract_type="continuous")
    db.add(inst)
    await db.flush()

    # Two 1D bars so we get 1 PDH + 1 PDL
    daily_t0 = datetime(2026, 1, 1, 23, 0, 0, tzinfo=UTC)  # session open day 1
    daily_t1 = datetime(2026, 1, 2, 23, 0, 0, tzinfo=UTC)  # session open day 2 → PDH/PDL from day 1
    db.add(Bar(instrument_id=inst.id, timeframe="1d", ts=daily_t0,
               open=100, high=120, low=95, close=110, volume=0))
    db.add(Bar(instrument_id=inst.id, timeframe="1d", ts=daily_t1,
               open=110, high=125, low=108, close=118, volume=0))
    # A few 5m working-timeframe bars (in day 2 range, after PDH/PDL active)
    detection_start = daily_t1
    detection_end = daily_t1 + timedelta(hours=4)
    for i in range(5):
        db.add(Bar(
            instrument_id=inst.id, timeframe="5m",
            ts=detection_start + timedelta(minutes=5 * i),
            open=110, high=115, low=108, close=112, volume=0,
        ))
    await db.flush()

    svc = LiquidityService()
    pools, raids, outcomes = await svc.detect_and_persist(
        db, inst.id, "5m", detection_start, detection_end,
    )

    pool_types = {p.pool_type for p in pools}
    assert PDH in pool_types
    assert PDL in pool_types


@pytest.mark.asyncio
async def test_service_replace_is_idempotent(db):
    from app.liquidity.service import LiquidityService
    from app.models.market_data import Bar, Instrument

    await _seed_liquidity_concept(db)

    inst = Instrument(symbol="NQ_LIQ_IDEM", exchange="CME", contract_type="continuous")
    db.add(inst)
    await db.flush()

    daily_t0 = datetime(2026, 1, 1, 23, 0, 0, tzinfo=UTC)
    daily_t1 = datetime(2026, 1, 2, 23, 0, 0, tzinfo=UTC)
    db.add(Bar(instrument_id=inst.id, timeframe="1d", ts=daily_t0,
               open=100, high=120, low=95, close=110, volume=0))
    db.add(Bar(instrument_id=inst.id, timeframe="1d", ts=daily_t1,
               open=110, high=125, low=108, close=118, volume=0))
    detection_start = daily_t1
    detection_end = daily_t1 + timedelta(hours=1)
    for i in range(3):
        db.add(Bar(
            instrument_id=inst.id, timeframe="5m",
            ts=detection_start + timedelta(minutes=5 * i),
            open=110, high=115, low=108, close=112, volume=0,
        ))
    await db.flush()

    svc = LiquidityService()
    await svc.detect_and_persist(db, inst.id, "5m", detection_start, detection_end)
    second = await svc.detect_and_persist(db, inst.id, "5m", detection_start, detection_end, replace=True)

    repo = LiquidityRepository()
    all_pools = await repo.get_pools(db, inst.id, "5m")
    assert len(all_pools) == len(second[0]), "replace=True must not accumulate duplicate pools"


# ── HTTP API smoke tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_endpoint_requires_seeded_concept(client):
    payload = {
        "instrument_id": str(uuid.uuid4()),
        "timeframe": "5m",
        "start": _T0.isoformat(),
        "end": (_T0 + timedelta(hours=1)).isoformat(),
    }
    resp = await client.post("/api/v1/liquidity/detect", json=payload)
    assert resp.status_code != 200


@pytest.mark.asyncio
async def test_get_pools_endpoint_returns_empty(client):
    resp = await client.get(
        "/api/v1/liquidity/pools",
        params={"instrument_id": str(uuid.uuid4()), "timeframe": "5m"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_raids_endpoint_returns_empty(client):
    resp = await client.get(
        "/api/v1/liquidity/raids",
        params={"instrument_id": str(uuid.uuid4()), "timeframe": "5m"},
    )
    assert resp.status_code == 200
    assert resp.json() == []
