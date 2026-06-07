"""Lightweight async pub/sub event bus.

In-process to start (a single asyncio queue per subscriber); the publish/
subscribe interface is intentionally narrow so a Redis-Streams-backed
implementation can replace this one later — across process boundaries — without
any subscriber changing a line of code. This is the mechanism that keeps
modules decoupled: a detector publishes a `BarClosedEvent` reaction or an
`AnnotationCreatedEvent` and never calls into another module directly.
"""

from collections import defaultdict

import structlog

from app.core.events import DomainEvent

logger = structlog.get_logger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type[DomainEvent], list] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler) -> None:
        """Register an async handler: `async def handler(event: DomainEvent) -> None`."""
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: type[DomainEvent], handler) -> None:
        self._subscribers[event_type] = [h for h in self._subscribers[event_type] if h != handler]

    async def publish(self, event: DomainEvent) -> None:
        """Dispatch to every subscriber of this event's exact type.

        A handler that raises is logged and isolated — one broken subscriber
        must never prevent others from receiving the event or crash the
        publisher (e.g. market-data ingestion must keep running even if a
        detector throws).
        """
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "event_handler_failed",
                    event_type=type(event).__name__,
                    handler=getattr(handler, "__qualname__", repr(handler)),
                )


_bus = EventBus()


def get_event_bus() -> EventBus:
    """FastAPI/DI entry point — single shared bus instance for the process."""
    return _bus
