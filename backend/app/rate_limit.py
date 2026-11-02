"""Limitation des tentatives de connexion (anti brute-force). En mémoire : 1 seul worker.
En production multi-workers, remplacer par Redis."""
import threading
import time
from collections import defaultdict, deque


class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, window_s: int = 900):
        self.max_attempts = max_attempts
        self.window_s = window_s
        self._fails: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _purge(self, key: str, now: float) -> deque[float]:
        q = self._fails[key]
        while q and now - q[0] > self.window_s:
            q.popleft()
        return q

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._purge(key, time.monotonic())) >= self.max_attempts

    def register_failure(self, key: str) -> None:
        with self._lock:
            self._purge(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)


login_limiter = LoginRateLimiter()
