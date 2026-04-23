"""Acceptance tests for library.py.

These are the graders, not the GCV Stage V tests. They tell you *whether* each
bug is fixed, not *why* it's broken — the diagnosis is the whole point of GCV.

Run with:
    pytest tests/ -v

Each test class targets one bug. A clean run means all 5 bugs fixed.

The concurrency tests tighten CPython's GIL switch interval inside a
try/finally so that bugs of the "check then act" / "read-modify-write" style
surface reliably on 3.10+. The setting is restored on the way out.
"""
from __future__ import annotations

import sys
import threading

import pytest

from library import (
    HoldQueue,
    LibraryStats,
    RateLimiter,
    merge_branch_events,
    parse_query,
)


# =====================================================================
# Bug 1 — LibraryStats (concurrent mutation / shared state)
# =====================================================================
class TestLibraryStats:
    def test_single_branch_single_thread(self):
        s = LibraryStats()
        for _ in range(50):
            s.record_checkout("downtown")
        assert s.count("downtown") == 50

    def test_separate_branches_single_thread(self):
        s = LibraryStats()
        s.record_checkout("a")
        s.record_checkout("b")
        s.record_checkout("a")
        assert s.count("a") == 2
        assert s.count("b") == 1

    def test_unknown_branch_returns_zero(self):
        s = LibraryStats()
        assert s.count("ghost") == 0

    def test_concurrent_same_branch_no_lost_updates(self):
        """The whole point — under contention, no increments may be lost."""
        s = LibraryStats()
        N_THREADS = 32
        N_PER_THREAD = 500
        barrier = threading.Barrier(N_THREADS)

        def worker() -> None:
            barrier.wait()
            for _ in range(N_PER_THREAD):
                s.record_checkout("downtown")

        old_interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        try:
            threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        finally:
            sys.setswitchinterval(old_interval)

        assert s.count("downtown") == N_THREADS * N_PER_THREAD


# =====================================================================
# Bug 2 — RateLimiter (timing-sensitive boundary)
# =====================================================================
class TestRateLimiter:
    def test_allows_under_limit(self):
        rl = RateLimiter(max_requests=3, window_seconds=1.0)
        assert rl.allow(now=0.0) is True
        assert rl.allow(now=0.1) is True
        assert rl.allow(now=0.2) is True

    def test_blocks_at_limit(self):
        rl = RateLimiter(max_requests=2, window_seconds=1.0)
        assert rl.allow(now=0.0) is True
        assert rl.allow(now=0.5) is True
        assert rl.allow(now=0.9) is False

    def test_request_falls_out_exactly_at_window_edge(self):
        # A request made at t=0 with a 1s window should fall out at t=1.0 exactly:
        # the docstring says the window is (t - window, t], so a 1.0-second-old
        # request is OUT, not IN.
        rl = RateLimiter(max_requests=1, window_seconds=1.0)
        assert rl.allow(now=0.0) is True
        assert rl.allow(now=0.5) is False
        assert rl.allow(now=1.0) is True

    def test_window_rolls_correctly_across_many_requests(self):
        rl = RateLimiter(max_requests=2, window_seconds=1.0)
        assert rl.allow(now=0.0) is True
        assert rl.allow(now=0.5) is True
        assert rl.allow(now=0.9) is False
        assert rl.allow(now=1.0) is True   # t=0 falls out
        assert rl.allow(now=1.5) is True   # t=0.5 falls out

    def test_default_now_uses_monotonic_clock(self):
        rl = RateLimiter(max_requests=10, window_seconds=60.0)
        assert rl.allow() is True


# =====================================================================
# Bug 3 — parse_query (DSL operator precedence)
# =====================================================================
CATALOG = [
    {"title": "Cosmos",                  "author": "Carl Sagan",      "year": 1980},
    {"title": "A Brief History of Time", "author": "Stephen Hawking", "year": 1988},
    {"title": "Universe in a Nutshell",  "author": "Stephen Hawking", "year": 2001},
    {"title": "The Elegant Universe",    "author": "Brian Greene",    "year": 1999},
]


class TestParseQuery:
    def test_author_substring_case_insensitive(self):
        out = parse_query("author:sagan", CATALOG)
        assert {b["title"] for b in out} == {"Cosmos"}

    def test_year_equals(self):
        out = parse_query("year:1988", CATALOG)
        assert {b["title"] for b in out} == {"A Brief History of Time"}

    def test_pure_and(self):
        out = parse_query("author:hawking AND year:2001", CATALOG)
        assert {b["title"] for b in out} == {"Universe in a Nutshell"}

    def test_pure_or(self):
        out = parse_query("author:sagan OR author:greene", CATALOG)
        assert {b["title"] for b in out} == {"Cosmos", "The Elegant Universe"}

    def test_and_binds_tighter_than_or(self):
        # "author:sagan OR author:hawking AND year:2001" must parse as
        #     author:sagan  OR  (author:hawking AND year:2001)
        # → Cosmos (matches sagan) PLUS Universe-in-a-Nutshell (hawking + 2001).
        # The 1988 Hawking book must NOT match.
        out = parse_query(
            "author:sagan OR author:hawking AND year:2001", CATALOG
        )
        assert {b["title"] for b in out} == {
            "Cosmos",
            "Universe in a Nutshell",
        }


# =====================================================================
# Bug 4 — merge_branch_events (tiebreaker / cross-source merge)
# =====================================================================
class TestMergeBranchEvents:
    def test_disjoint_timestamps(self):
        a = [
            {"timestamp": 1.0, "branch": "A", "isbn": "x"},
            {"timestamp": 3.0, "branch": "A", "isbn": "y"},
        ]
        b = [{"timestamp": 2.0, "branch": "B", "isbn": "z"}]
        out = merge_branch_events(a, b)
        assert [e["timestamp"] for e in out] == [1.0, 2.0, 3.0]

    def test_one_side_empty(self):
        b = [{"timestamp": 1.0, "branch": "B", "isbn": "z"}]
        assert merge_branch_events([], b) == b

    def test_both_empty(self):
        assert merge_branch_events([], []) == []

    def test_tie_prefers_branch_a(self):
        a = [{"timestamp": 1.0, "branch": "A", "isbn": "x"}]
        b = [{"timestamp": 1.0, "branch": "B", "isbn": "y"}]
        out = merge_branch_events(a, b)
        assert [e["branch"] for e in out] == ["A", "B"]

    def test_many_ties_keep_branch_ordering(self):
        a = [{"timestamp": 1.0, "branch": "A", "isbn": f"a{i}"} for i in range(4)]
        b = [{"timestamp": 1.0, "branch": "B", "isbn": f"b{i}"} for i in range(4)]
        out = merge_branch_events(a, b)
        assert len(out) == 8
        a_positions = [i for i, e in enumerate(out) if e["branch"] == "A"]
        b_positions = [i for i, e in enumerate(out) if e["branch"] == "B"]
        assert max(a_positions) < min(b_positions)


# =====================================================================
# Bug 5 — HoldQueue (check-then-act across an I/O syscall under load)
# =====================================================================
class TestHoldQueue:
    def test_accepts_until_full(self, tmp_path):
        q = HoldQueue(capacity=3, log_path=str(tmp_path / "log"))
        assert q.try_put("a") is True
        assert q.try_put("b") is True
        assert q.try_put("c") is True
        assert q.try_put("d") is False
        assert q.size() == 3

    def test_drain_empties_queue(self, tmp_path):
        q = HoldQueue(capacity=3, log_path=str(tmp_path / "log"))
        q.try_put("a")
        q.try_put("b")
        drained = q.drain()
        assert drained == ["a", "b"]
        assert q.size() == 0

    def test_refill_after_drain(self, tmp_path):
        q = HoldQueue(capacity=2, log_path=str(tmp_path / "log"))
        q.try_put("a")
        q.try_put("b")
        q.drain()
        assert q.try_put("c") is True
        assert q.try_put("d") is True
        assert q.size() == 2

    def test_never_exceeds_capacity_under_load(self, tmp_path):
        q = HoldQueue(capacity=5, log_path=str(tmp_path / "log"))
        N = 60
        barrier = threading.Barrier(N)

        def worker(i: int) -> None:
            barrier.wait()
            q.try_put(f"isbn-{i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert q.size() == 5

    def test_accepted_count_matches_final_size(self, tmp_path):
        q = HoldQueue(capacity=5, log_path=str(tmp_path / "log"))
        N = 60
        barrier = threading.Barrier(N)
        accepted: list[int] = []
        accepted_lock = threading.Lock()

        def worker(i: int) -> None:
            barrier.wait()
            if q.try_put(f"isbn-{i}"):
                with accepted_lock:
                    accepted.append(i)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(accepted) == q.size()
        assert q.size() == 5
