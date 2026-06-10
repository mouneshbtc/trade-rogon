"""Market Structure detector tests.

Every test exercises exactly one invariant so failures are unambiguous.
Bars are constructed as lightweight dicts and coerced to Bar-like objects via
a helper — no DB required for the pure-function detector tests.

DB tests (via `db` fixture) cover repository persistence and the full
service+concept round-trip, confirming that `as_of`-pinned rules flow
correctly from ConceptDefinitionRegistry into detect_market_structure.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import NamedTuple

import pytest

from app.concepts.registry import ConceptDefinitionRegistry
from app.market_structure.detector import (
    detect_market_structure,
)
from app.market_structure.repository import StructuralEventRepository
from app.market_structure.service import MarketStructureService
from app.models.market_structure import (
    BEARISH_BOS,
    BEARISH_COUNTER_STRUCTURE_BREAK,
    BULLISH_BOS,
    BULLISH_COUNTER_STRUCTURE_BREAK,
    SWING_HIGH,
    SWING_LOW,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

_T0 = datetime(2026, 1, 2, 10, 0, 0, tzinfo=UTC)
_INST = uuid.uuid4()
_TF = "5m"
_VER = 1


class _B(NamedTuple):
    """Minimal bar tuple — only fields the detector reads."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def _bars(*specs: tuple) -> list[_B]:
    """Build a list of _B from (o, h, l, c) tuples, assigning 5-min timestamps."""
    result = []
    for idx, spec in enumerate(specs):
        o, h, lo, c = spec
        result.append(_B(ts=_T0 + timedelta(minutes=5 * idx), open=o, high=h, low=lo, close=c))
    return result


def _detect(bars: list[_B], strength: int = 1) -> list:
    return detect_market_structure(
        bars=bars,  # type: ignore[arg-type]  # _B is duck-typed like Bar
        instrument_id=_INST,
        timeframe=_TF,
        concept_definition_version=_VER,
        swing_strength=strength,
    )


def _types(events: list) -> list[str]:
    return [e.event_type for e in events]


# ── Swing Detection (strength = 1) ───────────────────────────────────────────

def test_no_events_for_too_few_bars():
    bars = _bars((100, 105, 99, 102))
    assert _detect(bars) == []


def test_no_events_for_exactly_two_bars():
    bars = _bars((100, 105, 99, 102), (101, 106, 100, 103))
    assert _detect(bars) == []


def test_swing_high_confirmed_on_third_bar():
    # bars: low → peak → lower  →  peak at bars[1] is a swing high
    bars = _bars(
        (100, 104, 99, 101),   # bar 0: left side
        (101, 108, 100, 105),  # bar 1: SWING HIGH candidate (high=108)
        (104, 107, 103, 106),  # bar 2: right side confirms (high=107 < 108)
    )
    events = _detect(bars)
    sh_events = [e for e in events if e.event_type == SWING_HIGH]
    assert len(sh_events) == 1
    assert sh_events[0].price == Decimal("108")
    assert sh_events[0].ts == bars[1].ts


def test_swing_low_confirmed_on_third_bar():
    bars = _bars(
        (105, 107, 103, 105),  # bar 0
        (105, 106, 98, 100),   # bar 1: SWING LOW candidate (low=98)
        (100, 105, 99, 103),   # bar 2: right side confirms (low=99 > 98)
    )
    events = _detect(bars)
    sl_events = [e for e in events if e.event_type == SWING_LOW]
    assert len(sl_events) == 1
    assert sl_events[0].price == Decimal("98")


def test_no_swing_high_on_monotonic_rise():
    # Each bar's high is higher than the next — no bar is a local peak
    bars = _bars(
        (100, 102, 99, 101),
        (101, 104, 100, 103),
        (103, 106, 102, 105),
        (105, 108, 104, 107),
    )
    events = _detect(bars)
    assert not any(e.event_type == SWING_HIGH for e in events)


def test_no_swing_low_on_monotonic_decline():
    bars = _bars(
        (110, 112, 109, 110),
        (110, 111, 107, 108),
        (108, 109, 105, 106),
        (106, 107, 103, 104),
    )
    events = _detect(bars)
    assert not any(e.event_type == SWING_LOW for e in events)


def test_multiple_swings_detected():
    # W-shape: swing low → swing high → swing low
    bars = _bars(
        (105, 106, 103, 104),  # 0 — left of SL
        (104, 105, 100, 101),  # 1 — SWING LOW candidate (low=100)
        (101, 108, 101, 107),  # 2 — right of SL; left of SH
        (107, 110, 106, 109),  # 3 — SWING HIGH candidate (high=110)
        (109, 109, 104, 105),  # 4 — right of SH; left of SL2
        (105, 107, 102, 103),  # 5 — SWING LOW candidate (low=102)
        (103, 106, 103, 105),  # 6 — right of SL2
    )
    events = _detect(bars)
    types = _types(events)
    assert types.count(SWING_LOW) == 2
    assert types.count(SWING_HIGH) == 1


# ── Structure State Machine (Option B) ───────────────────────────────────────

def _bullish_setup_bars() -> list[_B]:
    """
    Sequence that establishes BULLISH_STRUCTURE via HH + HL:

    bar 0: plain bar (left of swing 1)
    bar 1: SWING LOW candidate (low=95) — SL1
    bar 2: right of SL1; left of SH1
    bar 3: SWING HIGH candidate (high=115) — SH1
    bar 4: right of SH1; left of SL2
    bar 5: SWING LOW candidate (low=98) — SL2 (HL: 98 > 95)
    bar 6: right of SL2; left of SH2
    bar 7: SWING HIGH candidate (high=120) — SH2 (HH: 120 > 115)
    bar 8: right of SH2 — structure becomes BULLISH

    After SH2 confirmed:  last 2 SHs = [115, 120] (HH) ✓
                          last 2 SLs = [95, 98]  (HL) ✓  → BULLISH
    BOS target = SH2 (120); protected = SL2 (98)
    """
    return _bars(
        (100, 102, 97, 98),    # 0
        (98,  100, 95, 96),    # 1  SL candidate  low=95
        (96,  113, 96, 112),   # 2
        (112, 115, 111, 114),  # 3  SH candidate  high=115
        (114, 114, 99, 100),   # 4
        (100, 102, 98, 101),   # 5  SL candidate  low=98 (HL)
        (101, 118, 101, 117),  # 6
        (117, 120, 116, 119),  # 7  SH candidate  high=120 (HH)
        (119, 119, 112, 113),  # 8  right side → SH2 confirmed; BULLISH established
    )


def test_bullish_structure_established_via_hh_hl():
    bars = _bullish_setup_bars()
    events = _detect(bars)
    types = _types(events)
    # Two swing highs and two swing lows confirmed — no BOS/CSB yet
    assert types.count(SWING_HIGH) == 2
    assert types.count(SWING_LOW) == 2
    assert BULLISH_BOS not in types
    assert BEARISH_BOS not in types


def _bearish_setup_bars() -> list[_B]:
    """
    Establishes BEARISH_STRUCTURE via LH + LL:

    bar 0: plain (high=118 < SH1 high=120 so bar 1 can be a swing high)
    bar 1: SWING HIGH candidate (high=120) — SH1
    bar 2: right of SH1 (high=119 < 120 ✓); left of SL1
    bar 3: SWING LOW candidate (low=100) — SL1
    bar 4: right of SL1 (low=101 > 100 ✓); left of SH2 (high=113 < 115)
    bar 5: SWING HIGH candidate (high=115) — SH2 (LH: 115 < 120)
    bar 6: right of SH2 (high=114 < 115 ✓); left of SL2
    bar 7: SWING LOW candidate (low=95) — SL2 (LL: 95 < 100)
    bar 8: right side (low=96 > 95 ✓) → SH2 + SL2 confirmed; BEARISH established
    """
    return _bars(
        (110, 118, 109, 110),  # 0  left of SH1 — high=118 < 120
        (110, 120, 109, 119),  # 1  SH1 candidate  high=120
        (119, 119, 102, 103),  # 2  right of SH1; left of SL1
        (103, 104, 100, 101),  # 3  SL1 candidate  low=100
        (101, 113, 101, 112),  # 4  right of SL1; left of SH2 — high=113 < 115
        (112, 115, 113, 114),  # 5  SH2 candidate  high=115 (LH)
        (114, 114,  96,  97),  # 6  right of SH2; left of SL2
        ( 97,  98,  95,  96),  # 7  SL2 candidate  low=95  (LL)
        ( 96,  97,  96,  96),  # 8  right side → BEARISH established
    )


def test_bearish_structure_established_via_lh_ll():
    bars = _bearish_setup_bars()
    events = _detect(bars)
    types = _types(events)
    assert types.count(SWING_HIGH) == 2
    assert types.count(SWING_LOW) == 2
    assert BULLISH_BOS not in types
    assert BEARISH_BOS not in types


def test_unknown_structure_no_bos_csb_before_structure():
    """While in UNKNOWN state (not enough swings for HH+HL), no BOS/CSB fires
    even if a close pierces a swing level."""
    # Single swing high then a high close — but only ONE swing high so far, no structure
    bars = _bars(
        (100, 102, 99, 100),   # 0
        (100, 115, 99, 114),   # 1  SH candidate  high=115
        (114, 120, 113, 119),  # 2  right side + close=119 > 115 (would be BOS if structured)
    )
    events = _detect(bars)
    types = _types(events)
    assert BULLISH_BOS not in types
    assert BEARISH_BOS not in types


# ── BOS Classification ────────────────────────────────────────────────────────

def test_bullish_bos_fires_after_structure_established():
    """After BULLISH structure is established, a close above the BOS target
    (most recent swing high) emits a bullish_bos referencing that swing."""
    # Use the 9-bar bullish setup, then add a bar whose close > SH2 (120)
    bars = list(_bullish_setup_bars()) + [
        _B(_T0 + timedelta(minutes=45), 113, 125, 112, 122),  # close=122 > 120 → BOS
    ]
    events = _detect(bars)
    bos_events = [e for e in events if e.event_type == BULLISH_BOS]
    assert len(bos_events) == 1
    assert bos_events[0].price == Decimal("122")

    # BOS must reference the broken swing high (SH2, price=120)
    sh2 = next(e for e in events if e.event_type == SWING_HIGH and e.price == Decimal("120"))
    assert bos_events[0].reference_swing_event_id == sh2.id


def test_bullish_bos_references_correct_swing():
    """reference_swing_event_id links to the specific swing event broken."""
    bars = list(_bullish_setup_bars()) + [
        _B(_T0 + timedelta(minutes=45), 113, 126, 112, 123),
    ]
    events = _detect(bars)
    bos = next(e for e in events if e.event_type == BULLISH_BOS)
    swing_ids = {e.id for e in events if e.event_type == SWING_HIGH}
    assert bos.reference_swing_event_id in swing_ids


def test_bearish_bos_fires_after_structure_established():
    bars = list(_bearish_setup_bars()) + [
        _B(_T0 + timedelta(minutes=45), 96, 97, 88, 89),  # close=89 < SL2 (95) → BOS
    ]
    events = _detect(bars)
    bos_events = [e for e in events if e.event_type == BEARISH_BOS]
    assert len(bos_events) == 1
    assert bos_events[0].price == Decimal("89")

    sl2 = next(e for e in events if e.event_type == SWING_LOW and e.price == Decimal("95"))
    assert bos_events[0].reference_swing_event_id == sl2.id


def test_no_duplicate_bos_on_same_swing_level():
    """Once a swing is broken (BOS), subsequent bars below/above it don't
    re-trigger another BOS against the same swing."""
    bars = list(_bullish_setup_bars()) + [
        _B(_T0 + timedelta(minutes=45), 113, 126, 112, 122),  # first BOS
        _B(_T0 + timedelta(minutes=50), 122, 128, 121, 125),  # still above — NO second BOS
        _B(_T0 + timedelta(minutes=55), 125, 130, 124, 128),  # still above — NO third BOS
    ]
    events = _detect(bars)
    assert _types(events).count(BULLISH_BOS) == 1


# ── CSB Classification ────────────────────────────────────────────────────────

def test_bearish_csb_fires_and_transitions_to_unknown():
    """In BULLISH, a close below the protected swing low (SL2=98) emits
    bearish_counter_structure_break and resets to UNKNOWN."""
    # After bullish setup (bars 0-8): protected_sl = SL2 (low=98), bos_target = SH2 (high=120)
    # Add a bar whose close < 98 → CSB
    bars = list(_bullish_setup_bars()) + [
        _B(_T0 + timedelta(minutes=45), 113, 114, 90, 91),  # close=91 < 98 → bearish CSB
    ]
    events = _detect(bars)
    csb_events = [e for e in events if e.event_type == BEARISH_COUNTER_STRUCTURE_BREAK]
    assert len(csb_events) == 1
    assert csb_events[0].price == Decimal("91")

    sl2 = next(e for e in events if e.event_type == SWING_LOW and e.price == Decimal("98"))
    assert csb_events[0].reference_swing_event_id == sl2.id


def test_bullish_csb_fires_in_bearish_structure():
    bars = list(_bearish_setup_bars()) + [
        _B(_T0 + timedelta(minutes=45), 96, 125, 96, 124),  # close=124 > protected SH2 (115)
    ]
    events = _detect(bars)
    csb_events = [e for e in events if e.event_type == BULLISH_COUNTER_STRUCTURE_BREAK]
    assert len(csb_events) == 1

    sh2 = next(e for e in events if e.event_type == SWING_HIGH and e.price == Decimal("115"))
    assert csb_events[0].reference_swing_event_id == sh2.id


def test_no_bos_csb_after_csb_transitions_to_unknown():
    """After a CSB resets to UNKNOWN, additional close-throughs produce no
    BOS/CSB until a new HH+HL or LH+LL pair re-establishes structure."""
    bars = list(_bullish_setup_bars()) + [
        _B(_T0 + timedelta(minutes=45), 113, 114, 90, 91),  # CSB → UNKNOWN
        _B(_T0 + timedelta(minutes=50), 91,  92, 85, 86),   # lower close — no CSB/BOS
        _B(_T0 + timedelta(minutes=55), 86,  88, 84, 87),   # still UNKNOWN
    ]
    events = _detect(bars)
    types_after_csb = [
        e.event_type for e in events
        if e.ts > _T0 + timedelta(minutes=45)
    ]
    assert BULLISH_BOS not in types_after_csb
    assert BEARISH_BOS not in types_after_csb
    assert BULLISH_COUNTER_STRUCTURE_BREAK not in types_after_csb
    assert BEARISH_COUNTER_STRUCTURE_BREAK not in types_after_csb


# ── Option B: CSB → UNKNOWN (not → opposite structure) ───────────────────────

def test_csb_does_not_immediately_establish_opposite_structure():
    """Bearish CSB → UNKNOWN, not → BEARISH. Further bars can re-establish
    BULLISH if they form HH+HL, or BEARISH if they form LH+LL."""
    bars = list(_bullish_setup_bars()) + [
        _B(_T0 + timedelta(minutes=45), 113, 114, 90, 91),  # CSB → UNKNOWN
        # More bars but no new full HH+HL/LH+LL pair yet
        _B(_T0 + timedelta(minutes=50), 91, 95, 89, 94),
        _B(_T0 + timedelta(minutes=55), 94, 97, 93, 94),
    ]
    events = _detect(bars)
    types_after_csb = [e.event_type for e in events if e.ts > _T0 + timedelta(minutes=45)]
    # Only new swings are allowed — no structure-dependent events
    assert all(t in {SWING_HIGH, SWING_LOW} for t in types_after_csb if t)


# ── Reference event IDs ───────────────────────────────────────────────────────

def test_all_bos_csb_events_reference_valid_swing_ids():
    """Every BOS/CSB event's reference_swing_event_id must point to a
    swing_high or swing_low event in the same detection run."""
    bars = list(_bullish_setup_bars()) + [
        _B(_T0 + timedelta(minutes=45), 113, 126, 112, 122),  # BOS
    ]
    events = _detect(bars)
    swing_ids = {e.id for e in events if e.event_type in {SWING_HIGH, SWING_LOW}}
    structural_events = [e for e in events if e.event_type not in {SWING_HIGH, SWING_LOW}]
    for ev in structural_events:
        assert ev.reference_swing_event_id is not None
        assert ev.reference_swing_event_id in swing_ids, (
            f"{ev.event_type} references unknown swing {ev.reference_swing_event_id}"
        )


def test_swing_events_have_no_reference_id():
    bars = _bullish_setup_bars()
    events = _detect(bars)
    for ev in events:
        if ev.event_type in {SWING_HIGH, SWING_LOW}:
            assert ev.reference_swing_event_id is None


# ── Repository (integration — real Postgres) ──────────────────────────────────

@pytest.mark.asyncio
async def test_repository_save_and_retrieve(db):
    from app.market_structure.detector import DetectedEvent

    inst_id = uuid.uuid4()
    ev = DetectedEvent(
        id=uuid.uuid4(),
        instrument_id=inst_id,
        timeframe="5m",
        concept_definition_version=1,
        event_type=SWING_HIGH,
        ts=_T0,
        price=Decimal("110.5"),
    )
    repo = StructuralEventRepository()
    saved = await repo.save_events(db, [ev])
    assert len(saved) == 1
    assert saved[0].price == Decimal("110.5")

    retrieved = await repo.get_events(db, inst_id, "5m")
    assert len(retrieved) == 1
    assert retrieved[0].id == ev.id


@pytest.mark.asyncio
async def test_repository_delete_events(db):
    from app.market_structure.detector import DetectedEvent

    inst_id = uuid.uuid4()
    ev = DetectedEvent(
        id=uuid.uuid4(),
        instrument_id=inst_id,
        timeframe="5m",
        concept_definition_version=1,
        event_type=SWING_LOW,
        ts=_T0,
        price=Decimal("99.0"),
    )
    repo = StructuralEventRepository()
    await repo.save_events(db, [ev])
    deleted = await repo.delete_events(db, inst_id, "5m")
    assert deleted == 1
    remaining = await repo.get_events(db, inst_id, "5m")
    assert remaining == []


# ── Service + ConceptDefinitionRegistry (integration) ─────────────────────────

async def _seed_market_structure_concept(db) -> int:
    registry = ConceptDefinitionRegistry()
    cd = await registry.propose_version(
        db,
        concept_name="market_structure",
        rules={
            "swing_strength": {"5m": 1, "15m": 1, "1h": 1},
            "swing_basis": "wick",
            "break_basis": "close",
        },
        notes="V1 — strength=1, wick/close",
        created_by="test",
    )
    await registry.activate_version(db, concept_name="market_structure", version=cd.version, at=_T0)
    return cd.version


@pytest.mark.asyncio
async def test_service_requires_active_concept_definition(db):
    from app.concepts.exceptions import ConceptNotDefinedError

    svc = MarketStructureService()
    with pytest.raises(ConceptNotDefinedError):
        await svc.detect_and_persist(db, uuid.uuid4(), "5m", _T0, _T0 + timedelta(hours=1))


@pytest.mark.asyncio
async def test_service_returns_empty_for_no_bars(db):
    await _seed_market_structure_concept(db)
    svc = MarketStructureService()
    result = await svc.detect_and_persist(db, uuid.uuid4(), "5m", _T0, _T0 + timedelta(hours=1))
    assert result == []


@pytest.mark.asyncio
async def test_service_detect_and_persist_full_round_trip(db):
    """End-to-end: seed bars + concept → detect → persist → retrieve."""
    from app.models.market_data import Bar, Instrument

    # Seed concept
    version = await _seed_market_structure_concept(db)

    # Seed instrument
    inst = Instrument(symbol="NQ_TEST", exchange="CME", contract_type="continuous")
    db.add(inst)
    await db.flush()

    # Seed bars (9-bar bullish setup + 1 BOS bar)
    bar_specs = [
        (100, 102, 97, 98),
        (98,  100, 95, 96),
        (96,  113, 96, 112),
        (112, 115, 111, 114),
        (114, 114, 99, 100),
        (100, 102, 98, 101),
        (101, 118, 101, 117),
        (117, 120, 116, 119),
        (119, 119, 112, 113),
        (113, 126, 112, 122),  # BOS bar: close=122 > SH2=120
    ]
    bar_objs = []
    for i, (o, h, lo, c) in enumerate(bar_specs):
        bar_objs.append(Bar(
            instrument_id=inst.id,
            timeframe="5m",
            ts=_T0 + timedelta(minutes=5 * i),
            open=o, high=h, low=lo, close=c, volume=0,
        ))
    db.add_all(bar_objs)
    await db.flush()

    svc = MarketStructureService()
    events = await svc.detect_and_persist(
        db,
        instrument_id=inst.id,
        timeframe="5m",
        start=_T0,
        end=_T0 + timedelta(minutes=5 * 9),
    )

    types = [e.event_type for e in events]
    assert SWING_HIGH in types
    assert SWING_LOW in types
    assert BULLISH_BOS in types
    # All events pinned to the active concept version
    assert all(e.concept_definition_version == version for e in events)


@pytest.mark.asyncio
async def test_service_detect_replace_is_idempotent(db):
    """Running detect_and_persist twice on the same range produces the same
    result — not doubled events."""
    from app.models.market_data import Bar, Instrument

    await _seed_market_structure_concept(db)
    inst = Instrument(symbol="NQ_IDEM", exchange="CME", contract_type="continuous")
    db.add(inst)
    await db.flush()

    bar_specs = [
        (100, 102, 97, 98),
        (98,  100, 95, 96),
        (96,  113, 96, 112),
        (112, 115, 111, 114),
        (114, 114, 99, 100),
        (100, 102, 98, 101),
        (101, 118, 101, 117),
        (117, 120, 116, 119),
        (119, 119, 112, 113),
    ]
    bar_objs = [
        Bar(
            instrument_id=inst.id, timeframe="5m",
            ts=_T0 + timedelta(minutes=5 * i),
            open=o, high=h, low=lo, close=c, volume=0,
        )
        for i, (o, h, lo, c) in enumerate(bar_specs)
    ]
    db.add_all(bar_objs)
    await db.flush()

    svc = MarketStructureService()
    end = _T0 + timedelta(minutes=5 * 8)
    await svc.detect_and_persist(db, inst.id, "5m", _T0, end)
    second = await svc.detect_and_persist(db, inst.id, "5m", _T0, end, replace=True)

    repo = StructuralEventRepository()
    all_events = await repo.get_events(db, inst.id, "5m")
    assert len(all_events) == len(second), "replace=True must not accumulate duplicate events"


# ── HTTP API (end-to-end via test client) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_endpoint_requires_seeded_concept(client):
    payload = {
        "instrument_id": str(uuid.uuid4()),
        "timeframe": "5m",
        "start": _T0.isoformat(),
        "end": (_T0 + timedelta(hours=1)).isoformat(),
    }
    resp = await client.post("/api/v1/market-structure/detect", json=payload)
    # ConceptNotDefinedError → 500 (unhandled) or 422; either way it's not 200
    assert resp.status_code != 200


@pytest.mark.asyncio
async def test_get_events_endpoint_returns_empty_list(client):
    resp = await client.get(
        "/api/v1/market-structure/events",
        params={"instrument_id": str(uuid.uuid4()), "timeframe": "5m"},
    )
    assert resp.status_code == 200
    assert resp.json() == []
