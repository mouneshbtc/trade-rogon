import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.concepts.registry import ConceptDefinitionRegistry
from app.market_structure.repository import StructuralEventRepository
from app.models.market_data import Instrument
from app.models.market_structure import SWING_HIGH, SWING_LOW
from app.models.smt import SMTDivergenceEvent
from app.smt.detector import SMTDivergenceFact, detect_smt
from app.smt.repository import SMTRepository

_CONCEPT_NAME = "smt"


def _dedup_events(events: list[SMTDivergenceFact]) -> list[SMTDivergenceFact]:
    """Collapse events sharing (instrument_a_id, instrument_b_id, timeframe, ts, direction).

    `detect_smt` runs an A-leads pass and a B-leads pass per direction; both can
    resolve to the same divergence ts (max(anchor.ts, companion.ts) + bar_width)
    for the same direction, which `uq_smt_divergence_event` treats as one row.
    Keep the first (earliest-detected) fact for each key.
    """
    seen: dict[tuple[uuid.UUID, uuid.UUID, str, datetime, str], SMTDivergenceFact] = {}
    for event in events:
        key = (event.instrument_a_id, event.instrument_b_id, event.timeframe, event.ts, event.direction)
        seen.setdefault(key, event)
    return list(seen.values())

# Static bar-width map — used for confirmation-ts computation and proximity delta.
_TIMEFRAME_TO_TIMEDELTA: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
}


class SMTService:
    def __init__(
        self,
        event_repo: StructuralEventRepository | None = None,
        smt_repo: SMTRepository | None = None,
        registry: ConceptDefinitionRegistry | None = None,
    ) -> None:
        self._event_repo = event_repo or StructuralEventRepository()
        self._smt_repo = smt_repo or SMTRepository()
        self._registry = registry or ConceptDefinitionRegistry()

    # ── Instrument resolution ─────────────────────────────────────────────────

    async def _resolve_instrument(self, db: AsyncSession, symbol: str) -> Instrument:
        result = await db.execute(
            select(Instrument).where(Instrument.symbol == symbol)
        )
        inst = result.scalar_one_or_none()
        if inst is None:
            raise ValueError(
                f"Instrument '{symbol}' not found. Seed it before running SMT detection."
            )
        return inst

    # ── Main detect + persist ─────────────────────────────────────────────────

    async def detect_and_persist(
        self,
        db: AsyncSession,
        timeframe: str,
        start: datetime,
        end: datetime,
        *,
        replace: bool = True,
    ) -> tuple[list[SMTDivergenceEvent], str, str]:
        """Run SMT detection over [start, end] and persist results.

        Instrument pair is resolved from the active 'smt' ConceptDefinition rules.
        Market Structure must have been run for both instruments before calling this.

        Returns:
            (saved_events, symbol_a, symbol_b)
        """
        concept_def = await self._registry.get_active_or_raise(db, _CONCEPT_NAME)
        rules = concept_def.rules
        cdv = concept_def.version

        symbol_a: str = rules["instrument_a_symbol"]
        symbol_b: str = rules["instrument_b_symbol"]

        if timeframe not in _TIMEFRAME_TO_TIMEDELTA:
            raise ValueError(f"Unsupported timeframe '{timeframe}' for SMT detection.")
        bar_width = _TIMEFRAME_TO_TIMEDELTA[timeframe]

        inst_a = await self._resolve_instrument(db, symbol_a)
        inst_b = await self._resolve_instrument(db, symbol_b)

        # ── Load in-range swing events ────────────────────────────────────────
        a_events = await self._event_repo.get_events(db, inst_a.id, timeframe, start, end)
        b_events = await self._event_repo.get_events(db, inst_b.id, timeframe, start, end)

        a_shs = [e for e in a_events if e.event_type == SWING_HIGH]
        a_sls = [e for e in a_events if e.event_type == SWING_LOW]
        b_shs = [e for e in b_events if e.event_type == SWING_HIGH]
        b_sls = [e for e in b_events if e.event_type == SWING_LOW]

        if not a_events:
            raise ValueError(
                f"No Market Structure events found for '{symbol_a}' in [{start}, {end}]. "
                "Run Market Structure detection first."
            )
        if not b_events:
            raise ValueError(
                f"No Market Structure events found for '{symbol_b}' in [{start}, {end}]. "
                "Run Market Structure detection first."
            )

        # ── Seed prior swings from before range start ─────────────────────────
        # Prepend the last swing of each type before `start` so the first in-range
        # swing has a prior reference even if there is no in-range predecessor.
        seed_a_sh = await self._event_repo.get_last_swing_before(db, inst_a.id, timeframe, start, SWING_HIGH)
        seed_a_sl = await self._event_repo.get_last_swing_before(db, inst_a.id, timeframe, start, SWING_LOW)
        seed_b_sh = await self._event_repo.get_last_swing_before(db, inst_b.id, timeframe, start, SWING_HIGH)
        seed_b_sl = await self._event_repo.get_last_swing_before(db, inst_b.id, timeframe, start, SWING_LOW)

        all_a_shs = ([seed_a_sh] if seed_a_sh else []) + a_shs
        all_a_sls = ([seed_a_sl] if seed_a_sl else []) + a_sls
        all_b_shs = ([seed_b_sh] if seed_b_sh else []) + b_shs
        all_b_sls = ([seed_b_sl] if seed_b_sl else []) + b_sls

        # ── Run detector ──────────────────────────────────────────────────────
        detected = detect_smt(
            instrument_a_id=inst_a.id,
            instrument_b_id=inst_b.id,
            timeframe=timeframe,
            concept_definition_version=cdv,
            a_swing_highs=all_a_shs,
            a_swing_lows=all_a_sls,
            b_swing_highs=all_b_shs,
            b_swing_lows=all_b_sls,
            bar_width=bar_width,
            rules=rules,
        )
        detected = _dedup_events(detected)

        # ── Persist ───────────────────────────────────────────────────────────
        if replace:
            await self._smt_repo.delete_for_range(db, inst_a.id, inst_b.id, timeframe, start, end)

        saved = await self._smt_repo.save_events(db, detected)
        return saved, symbol_a, symbol_b

    async def get_events(
        self,
        db: AsyncSession,
        timeframe: str,
        *,
        direction: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[list[SMTDivergenceEvent], str, str]:
        """Return SMT events. Resolves instrument pair from active ConceptDefinition."""
        concept_def = await self._registry.get_active_or_raise(db, _CONCEPT_NAME)
        rules = concept_def.rules
        symbol_a = rules["instrument_a_symbol"]
        symbol_b = rules["instrument_b_symbol"]

        inst_a = await self._resolve_instrument(db, symbol_a)
        inst_b = await self._resolve_instrument(db, symbol_b)

        events = await self._smt_repo.get_events(
            db, inst_a.id, inst_b.id, timeframe,
            direction=direction, start=start, end=end,
        )
        return events, symbol_a, symbol_b
