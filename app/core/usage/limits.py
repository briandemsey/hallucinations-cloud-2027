"""Spending guard for the free, open detector.

Three limits, all held in memory (one server process on Render):
- per visitor per minute
- per visitor per day
- all visitors per day (the ceiling on what one day can cost)

Counters reset when the service restarts. That errs on the generous side for
visitors and is bounded by the daily ceiling and by the account's own
monthly spend limit at the provider.
"""

import threading
import time
from collections import defaultdict, deque


class Limiter:
    def __init__(self, per_minute: int, per_day: int, global_per_day: int, clock=time.time):
        self.per_minute = per_minute
        self.per_day = per_day
        self.global_per_day = global_per_day
        self._clock = clock
        self._lock = threading.Lock()
        self._day = None
        self._minute_hits: dict[str, deque] = defaultdict(deque)
        self._day_hits: dict[str, int] = defaultdict(int)
        self._global = 0

    def _roll(self, now: float) -> None:
        day = int(now // 86400)
        if day != self._day:
            self._day = day
            self._day_hits.clear()
            self._minute_hits.clear()
            self._global = 0

    def allow(self, visitor: str) -> tuple[bool, str]:
        now = self._clock()
        with self._lock:
            self._roll(now)
            if self._global >= self.global_per_day:
                return False, "busy"
            if self._day_hits[visitor] >= self.per_day:
                return False, "daily"
            hits = self._minute_hits[visitor]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False, "minute"
            hits.append(now)
            self._day_hits[visitor] += 1
            self._global += 1
            return True, ""

    def spend_global(self, n: int = 1) -> bool:
        """Count checks made by the service itself (the self test) against the day's ceiling."""
        with self._lock:
            self._roll(self._clock())
            if self._global + n > self.global_per_day:
                return False
            self._global += n
            return True

    def used_today(self) -> int:
        with self._lock:
            self._roll(self._clock())
            return self._global
