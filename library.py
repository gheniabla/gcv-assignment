"""
library.py — a small library-management module with five planted bugs.

Each bug targets an area where LLMs (and many humans) routinely stumble:

    Bug 1 — LibraryStats.record_checkout       concurrent mutation / shared state
    Bug 2 — RateLimiter.allow                  timing-sensitive boundary condition
    Bug 3 — parse_query                        small DSL / operator precedence
    Bug 4 — merge_branch_events                cross-source merge with ties
    Bug 5 — HoldQueue.try_put                  check-then-act under load

Do not read the tests in tests/ until after you've drafted your Stage C analysis
for each bug — they contain the reproducers and will give away too much too early.

Run the acceptance suite with:
    pytest tests/

A clean green run (0 failed) is the deliverable for the code portion of the
assignment.
"""

from __future__ import annotations

import heapq
import threading
import time
from collections import deque
from typing import Iterable, Optional


# -------------------------------------------------------------------
# Bug 1  (difficulty: medium — shared dict across threads)
# -------------------------------------------------------------------
class LibraryStats:
    """Per-branch checkout counters, intended to be safe under concurrent use.

    Example
    -------
    >>> s = LibraryStats()
    >>> s.record_checkout("downtown")
    >>> s.record_checkout("downtown")
    >>> s.count("downtown")
    2
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def record_checkout(self, branch: str) -> None:
        """Increment the checkout counter for `branch`."""
        with self._lock:
            current = self._counts.get(branch, 0)
        self._counts[branch] = current + 1

    def count(self, branch: str) -> int:
        with self._lock:
            return self._counts.get(branch, 0)


# -------------------------------------------------------------------
# Bug 2  (difficulty: medium — boundary of a time window)
# -------------------------------------------------------------------
class RateLimiter:
    """Sliding-window rate limiter.

    Allows up to `max_requests` requests in any `window_seconds`-second window.
    A request made at time `t` is considered to be in the window up to, but not
    including, time `t + window_seconds` — i.e. the window is the half-open
    interval `(t - window_seconds, t]`.

    `now` may be injected for deterministic testing; otherwise `time.monotonic`
    is used.

    Example
    -------
    >>> rl = RateLimiter(max_requests=1, window_seconds=1.0)
    >>> rl.allow(now=0.0)
    True
    >>> rl.allow(now=0.5)
    False
    >>> rl.allow(now=1.0)    # t=0 request falls out here
    True
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()

    def allow(self, now: Optional[float] = None) -> bool:
        if now is None:
            now = time.monotonic()
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        if len(self._timestamps) < self.max_requests:
            self._timestamps.append(now)
            return True
        return False


# -------------------------------------------------------------------
# Bug 3  (difficulty: subtle — a small DSL with two operators)
# -------------------------------------------------------------------
def parse_query(query: str, catalog: list) -> list:
    """Filter `catalog` by a tiny boolean query language.

    Grammar
    -------
        expr := or_expr
        or_expr  := and_expr (' OR ' and_expr)*
        and_expr := term (' AND ' term)*
        term := 'author:' <substring>     (case-insensitive substring on author)
              | 'year:' <integer>         (exact year match)

    Precedence: AND binds tighter than OR (as in SQL and Python).

    So `author:sagan OR author:hawking AND year:2001` means
    `author:sagan  OR  (author:hawking AND year:2001)` —
    **not** `(author:sagan OR author:hawking) AND year:2001`.

    Example
    -------
    >>> catalog = [
    ...     {"title": "Cosmos", "author": "Carl Sagan", "year": 1980},
    ...     {"title": "A Brief History", "author": "Stephen Hawking", "year": 1988},
    ...     {"title": "Universe in a Nutshell", "author": "Stephen Hawking", "year": 2001},
    ... ]
    >>> [b["title"] for b in parse_query("author:sagan", catalog)]
    ['Cosmos']
    """

    def _match_term(book: dict, term: str) -> bool:
        field, _, value = term.partition(":")
        if field == "author":
            return value.lower() in book["author"].lower()
        if field == "year":
            return book["year"] == int(value)
        raise ValueError(f"unknown field in query: {field!r}")

    and_groups = [clause.split(" AND ") for clause in query.split(" AND ")]
    out = []
    for book in catalog:
        if all(
            any(_match_term(book, t) for t in group.split(" OR "))
            for group in query.split(" AND ")
        ):
            out.append(book)
    return out


# -------------------------------------------------------------------
# Bug 4  (difficulty: subtle — tiebreaker in a merge)
# -------------------------------------------------------------------
def merge_branch_events(events_a: list, events_b: list) -> list:
    """Merge two timestamp-sorted event streams into one sorted stream.

    Each event is a dict with at least keys `timestamp` (number) and `branch`
    (str). The two input lists are already individually sorted by timestamp.

    On a timestamp tie between streams, events from `events_a` come before
    events from `events_b` (stable merge).

    Example
    -------
    >>> a = [{"timestamp": 1.0, "branch": "A", "isbn": "x"}]
    >>> b = [{"timestamp": 2.0, "branch": "B", "isbn": "y"}]
    >>> [e["branch"] for e in merge_branch_events(a, b)]
    ['A', 'B']
    """
    merged = heapq.merge(
        ((e["timestamp"], e) for e in events_a),
        ((e["timestamp"], e) for e in events_b),
    )
    return [e for _, e in merged]


# -------------------------------------------------------------------
# Bug 5  (difficulty: intermittent — surfaces under concurrent load)
# -------------------------------------------------------------------
class HoldQueue:
    """Non-blocking bounded FIFO for hold requests, with a write-ahead log.

    Every accepted hold is durably appended to `log_path` before it lands in
    the in-memory queue, so a crash never leaves an item in memory that the
    log doesn't know about. The queue is advertised as safe for concurrent
    callers and must never grow beyond its declared capacity.

    `try_put` returns True if the item was accepted, False if the queue was
    already full.

    Example
    -------
    >>> import tempfile, os
    >>> log = tempfile.NamedTemporaryFile(delete=False).name
    >>> q = HoldQueue(capacity=2, log_path=log)
    >>> q.try_put("isbn-1")
    True
    >>> q.try_put("isbn-2")
    True
    >>> q.try_put("isbn-3")
    False
    >>> q.size()
    2
    >>> os.unlink(log)
    """

    def __init__(self, capacity: int, log_path: str) -> None:
        self.capacity = capacity
        self.log_path = log_path
        self._items: list[str] = []
        self._lock = threading.Lock()

    def try_put(self, isbn: str) -> bool:
        if len(self._items) >= self.capacity:
            return False
        with open(self.log_path, "a") as f:
            f.write(f"{isbn}\n")
        with self._lock:
            self._items.append(isbn)
            return True

    def size(self) -> int:
        with self._lock:
            return len(self._items)

    def drain(self) -> list[str]:
        with self._lock:
            items = list(self._items)
            self._items.clear()
            return items


# -------------------------------------------------------------------
# Helper — not buggy, just used by tests
# -------------------------------------------------------------------
def concat_events(*streams: Iterable[dict]) -> list[dict]:
    """Concatenate several event iterables into one list (preserves order)."""
    out: list[dict] = []
    for s in streams:
        out.extend(s)
    return out
