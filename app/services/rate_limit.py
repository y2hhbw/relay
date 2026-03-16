import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    def __init__(self, limit: int = 3, window_seconds: float = 60.0):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, account_id: str, service_key: str, now: float | None = None) -> bool:
        key = (account_id, service_key)
        current = now if now is not None else time.time()
        cutoff = current - self.window_seconds
        events = self._events[key]

        while events and events[0] <= cutoff:
            events.popleft()

        if len(events) >= self.limit:
            return False

        events.append(current)
        return True
