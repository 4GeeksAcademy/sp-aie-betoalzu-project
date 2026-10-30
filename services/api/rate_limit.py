"""Small process-local sliding-window limiter for authenticated inference.

This is an application safety net, not a distributed gateway quota. Deployments
with multiple workers/replicas must also enforce the same or stricter limit at
their gateway (or use a shared rate-limit store).
"""

from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException

from services.api.users.auth import get_current_user
from services.api.users.models import UserInDB


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("Rate limit and window must be positive.")
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            requests = self._requests[key]
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= self.limit:
                retry_after = max(1, math.ceil(requests[0] + self.window_seconds - now))
                raise HTTPException(
                    status_code=429,
                    detail="Límite temporal de consultas de IA alcanzado.",
                    headers={"Retry-After": str(retry_after)},
                )
            requests.append(now)

            # Bound stale identity keys in long-lived development processes.
            if len(self._requests) > 10_000:
                stale = [
                    identity
                    for identity, timestamps in self._requests.items()
                    if not timestamps or timestamps[-1] <= cutoff
                ]
                for identity in stale:
                    self._requests.pop(identity, None)

    def clear(self) -> None:
        """Clear counters; intended for deterministic tests and shutdowns."""
        with self._lock:
            self._requests.clear()


model_inference_limiter = SlidingWindowRateLimiter(limit=10, window_seconds=60)


def require_model_inference_capacity(
    user: UserInDB = Depends(get_current_user),
) -> None:
    """Limit combined authenticated inference requests by stable user id."""
    model_inference_limiter.check(f"user:{user.id}")