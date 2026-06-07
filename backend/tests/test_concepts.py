"""Concept Definition System — versioning, activation, and as-of resolution.

These invariants matter because every detector resolves "what counts" through
this layer. Get version sequencing or `as_of` ranging wrong and a backtest
silently judges history by today's rules instead of the rules in effect then.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.concepts.exceptions import ConceptNotDefinedError
from app.concepts.registry import ConceptDefinitionRegistry

pytestmark = pytest.mark.asyncio


@pytest.fixture
def registry():
    return ConceptDefinitionRegistry()


async def test_create_version_auto_increments(db, registry):
    v1 = await registry.propose_version(db, concept_name="order_block", rules={"shape": "v1"})
    v2 = await registry.propose_version(db, concept_name="order_block", rules={"shape": "v2"})

    assert v1.version == 1
    assert v2.version == 2
    assert v1.is_active is False
    assert v2.is_active is False


async def test_get_active_returns_none_until_activated(db, registry):
    await registry.propose_version(db, concept_name="fvg", rules={"min_gap_ticks": 4})

    assert await registry.get_active(db, "fvg") is None
    with pytest.raises(ConceptNotDefinedError):
        await registry.get_active_or_raise(db, "fvg")


async def test_activate_deactivates_previous_atomically(db, registry):
    v1 = await registry.propose_version(db, concept_name="breaker", rules={"a": 1})
    v2 = await registry.propose_version(db, concept_name="breaker", rules={"a": 2})

    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    await registry.activate_version(db, concept_name="breaker", version=v1.version, at=t1)

    t2 = datetime(2026, 2, 1, tzinfo=UTC)
    activated = await registry.activate_version(db, concept_name="breaker", version=v2.version, at=t2)

    assert activated is not None
    assert activated.id == v2.id
    assert activated.is_active is True
    assert activated.activated_at == t2
    assert activated.deactivated_at is None

    active = await registry.get_active(db, "breaker")
    assert active is not None
    assert active.id == v2.id

    # The previous version was deactivated at the exact instant the new one
    # took over — no gap, no overlap in the `as_of` timeline.
    versions = await registry.list_versions(db, "breaker")
    previous = next(v for v in versions if v.id == v1.id)
    assert previous.is_active is False
    assert previous.deactivated_at == t2


async def test_get_active_as_of_resolves_historically_correct_version(db, registry):
    v1 = await registry.propose_version(db, concept_name="fvg", rules={"min_gap_ticks": 2})
    v2 = await registry.propose_version(db, concept_name="fvg", rules={"min_gap_ticks": 4})

    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 3, 1, tzinfo=UTC)
    await registry.activate_version(db, concept_name="fvg", version=v1.version, at=t1)
    await registry.activate_version(db, concept_name="fvg", version=v2.version, at=t2)

    before_any = await registry.get_active_as_of(db, "fvg", t1 - timedelta(days=1))
    during_v1 = await registry.get_active_as_of(db, "fvg", t1 + timedelta(days=1))
    during_v2 = await registry.get_active_as_of(db, "fvg", t2 + timedelta(days=1))
    at_cutover = await registry.get_active_as_of(db, "fvg", t2)

    assert before_any is None
    assert during_v1 is not None and during_v1.id == v1.id
    assert during_v2 is not None and during_v2.id == v2.id
    assert at_cutover is not None and at_cutover.id == v2.id


async def test_get_active_as_of_or_raise_raises_when_undefined(db, registry):
    with pytest.raises(ConceptNotDefinedError):
        await registry.get_active_as_of_or_raise(db, "order_block", datetime(2026, 1, 1, tzinfo=UTC))
