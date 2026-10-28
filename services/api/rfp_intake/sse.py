"""SSE (Server-Sent Events) manager for real-time RFP ticket notifications.

Manages concurrent SSE connections, broadcasts events to all connected clients,
and handles connection lifecycle.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Callable

logger = logging.getLogger(__name__)


class RfpSseManager:
    """Manages SSE connections and broadcasts RFP ticket creation events."""

    def __init__(self):
        """Initialize the SSE manager with empty queues."""
        self._queues: dict[str, asyncio.Queue] = {}
        self._queue_counter = 0
        self._lock = asyncio.Lock()

    async def subscribe(self) -> tuple[str, asyncio.Queue]:
        """Create a new subscription and return its ID and queue.

        Returns:
            (subscription_id, queue): A unique ID and queue for this connection.
        """
        async with self._lock:
            self._queue_counter += 1
            sub_id = f"sub_{self._queue_counter}"
            queue: asyncio.Queue = asyncio.Queue()
            self._queues[sub_id] = queue
            logger.info(f"SSE subscription created: {sub_id} (total: {len(self._queues)})")
            return sub_id, queue

    async def unsubscribe(self, sub_id: str) -> None:
        """Remove a subscription by ID.

        Args:
            sub_id: The subscription ID to remove.
        """
        async with self._lock:
            if sub_id in self._queues:
                del self._queues[sub_id]
                logger.info(f"SSE subscription removed: {sub_id} (total: {len(self._queues)})")

    async def publish(self, event_type: str, data: dict) -> None:
        """Broadcast an event to all connected clients.

        Args:
            event_type: The SSE event name (e.g., "rfp_ticket_created").
            data: The JSON payload to send.
        """
        async with self._lock:
            queue_count = len(self._queues)

        if queue_count == 0:
            logger.debug(f"Event '{event_type}' published with no active subscriptions")
            return

        message = {"event": event_type, "data": data}
        tasks = [
            self._queues[sub_id].put(message)
            for sub_id in list(self._queues.keys())
            if sub_id in self._queues
        ]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(
                f"Event '{event_type}' published to {queue_count} subscription(s)"
            )

    async def stream(
        self, sub_id: str, queue: asyncio.Queue, keep_alive_interval: float = 30.0
    ) -> AsyncGenerator[str, None]:
        """Stream SSE frames for a subscription.

        Yields formatted SSE frames. Includes periodic keep-alive comments.

        Args:
            sub_id: The subscription ID.
            queue: The queue for this subscription.
            keep_alive_interval: Seconds between keep-alive comments.

        Yields:
            SSE frame strings (event, data, comments) with trailing newline.
        """
        keep_alive_task = asyncio.create_task(
            self._keep_alive_loop(queue, keep_alive_interval)
        )

        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=5.0)
                    event_type = message.get("event", "message")
                    data = message.get("data", {})
                    data_json = json.dumps(data)

                    frame = f"event: {event_type}\ndata: {data_json}\n\n"
                    yield frame
                except asyncio.TimeoutError:
                    # Keep looping to check for disconnection
                    pass
        finally:
            keep_alive_task.cancel()
            try:
                await keep_alive_task
            except asyncio.CancelledError:
                pass
            await self.unsubscribe(sub_id)
            logger.info(f"SSE stream closed for subscription: {sub_id}")

    async def _keep_alive_loop(
        self, queue: asyncio.Queue, interval: float
    ) -> None:
        """Periodically send keep-alive comments to a queue.

        Args:
            queue: The queue to send keep-alive to.
            interval: Seconds between keep-alive comments.
        """
        try:
            while True:
                await asyncio.sleep(interval)
                await queue.put({"event": "keep-alive", "data": {}})
        except asyncio.CancelledError:
            pass


# Global singleton instance
_sse_manager: RfpSseManager | None = None


def get_sse_manager() -> RfpSseManager:
    """Get or create the global SSE manager instance."""
    global _sse_manager
    if _sse_manager is None:
        _sse_manager = RfpSseManager()
    return _sse_manager
