"""CLI: seed and activate the V1 concept definitions required for the pipeline to run.

    python scripts/seed_concepts.py

Every detection/evaluation service calls `registry.get_active_or_raise(db, name)`
and refuses to run with no active definition. The rule payloads below are the
same V1 rule sets used throughout `backend/tests/` (market_structure, liquidity,
displacement, smt, fvg, daily_fvg_sweep_reversal) — nothing here is invented.

The only deviation from the test fixtures is the `smt` concept's
`instrument_a_symbol`/`instrument_b_symbol`: tests use placeholder symbols
("NQ"/"ES") for synthetic instruments, but real ingestion stores instruments
under their Databento continuous-contract symbols (`NQ.c.0`/`ES.c.0`, from
`settings.databento_nq_symbol`/`databento_es_symbol`). The rule *schema* is
unchanged; only these two values are adapted so SMT can resolve real
instruments.

Idempotent: if an active version already has these exact rules, nothing is
created or re-activated. Otherwise a new version is proposed and activated,
backdated (`activated_at`) so it is in force for any historical replay range.
"""

import asyncio
from datetime import UTC, datetime

import structlog

from app.concepts.registry import get_concept_registry
from app.config import settings
from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)

# Backdated activation timestamp — must precede any historical replay range so
# `get_active_as_of` resolves to this version for the entire dataset.
_ACTIVATED_AT = datetime(2000, 1, 1, tzinfo=UTC)

CONCEPT_RULES: dict[str, dict] = {
    "market_structure": {
        "swing_strength": {"5m": 1, "15m": 1, "1h": 1},
        "swing_basis": "wick",
        "break_basis": "close",
    },
    "liquidity": {
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
    "displacement": {
        "displacement_basis": "either",
        "min_body_ratio": 0.70,
        "min_body_ticks": 6,
        "tick_size_points": 0.25,
        "max_sequence_bars": 3,
        "consecutive_merge": True,
    },
    "smt": {
        "instrument_a_symbol": settings.databento_nq_symbol,
        "instrument_b_symbol": settings.databento_es_symbol,
        "swing_proximity_bars": 3,
        "tick_size_points": 0.25,
    },
    "fvg": {
        "min_gap_ticks": 1,
        "tick_size_points": 0.25,
    },
    "daily_fvg_sweep_reversal": {
        "direction_map": {
            "bullish": {
                "raid_direction": "bearish",
                "smt_direction": "bullish",
                "displacement_direction": "bullish",
                "fvg_direction": "bullish",
            },
            "bearish": {
                "raid_direction": "bullish",
                "smt_direction": "bearish",
                "displacement_direction": "bearish",
                "fvg_direction": "bearish",
            },
        },
        "timing_windows": {
            "smt_bars_around_raid": 5,
            "displacement_max_bars_from_raid": 10,
            "fvg_max_bars_from_displacement": 3,
        },
    },
}


async def seed() -> None:
    registry = get_concept_registry()
    created: list[str] = []
    activated: list[str] = []
    errors: list[str] = []

    async with AsyncSessionLocal() as db:
        for concept_name, rules in CONCEPT_RULES.items():
            try:
                active = await registry.get_active(db, concept_name)
                if active is not None and active.rules == rules:
                    logger.info("concept_already_active", concept=concept_name, version=active.version)
                    continue

                new_version = await registry.propose_version(
                    db,
                    concept_name=concept_name,
                    rules=rules,
                    notes="V1 — seeded from approved rule sets in backend/tests/",
                    created_by="seed_concepts",
                )
                created.append(f"{concept_name} v{new_version.version}")

                await registry.activate_version(
                    db, concept_name=concept_name, version=new_version.version, at=_ACTIVATED_AT
                )
                activated.append(f"{concept_name} v{new_version.version}")
                logger.info("concept_seeded", concept=concept_name, version=new_version.version)
            except Exception as exc:
                errors.append(f"{concept_name}: {exc}")
                logger.exception("concept_seed_failed", concept=concept_name)

        await db.commit()

    logger.info("seed_complete", created=created, activated=activated, errors=errors)


def main() -> None:
    configure_logging()
    asyncio.run(seed())


if __name__ == "__main__":
    main()
