# Assignment — Debug a Library with GCV (LLM-weak edition)

**Prerequisites:** Python 3.10+, `pip install -r requirements.txt`,
Claude Code installed, the `gcv` skill installed at `~/.claude/skills/gcv/SKILL.md`.

**Deliverables:**
1. A fixed `library.py` where `pytest tests/ -v` ends with **24 passed, 0 failed**.
2. A written report `REPORT.md` (template in this repo — fill it in).

**Due:** see course site.
**Honor pledge:** see the `## Honor pledge` section at the bottom of this file.

---

## The scenario

You've been handed a small Python module, `library.py`, that powers part of a
library-management system. Five units of code, five planted bugs:

| # | Symbol | What it does | LLM-weak area this targets |
|---|---|---|---|
| 1 | `LibraryStats` | Per-branch checkout counters | Concurrent mutation / shared state |
| 2 | `RateLimiter` | Sliding-window rate limiter | Timing-sensitive boundary conditions |
| 3 | `parse_query` | Tiny boolean DSL over a catalog | Custom protocols / operator precedence |
| 4 | `merge_branch_events` | Merge two sorted event streams | Cross-source merge with ordering ties |
| 5 | `HoldQueue` | Bounded FIFO with a write-ahead log | Intermittent I/O race surfacing under load |

Each function/class has **exactly one** behavioural bug — not a style issue,
not a "could be cleaner". A real bug that causes the acceptance tests to fail.
The bugs were chosen to live in areas that LLMs (and many humans) routinely
get wrong: thread-safety across an I/O syscall, off-by-one at a window edge,
inverted operator precedence in a parser, a missing tiebreaker in a heap merge,
a check-then-act under contention.

Your job: find them, fix them, document your process.

---

## The rules

### Must-do

- **Use the `gcv` skill for every bug.** Not "use Claude." Specifically
  invoke the skill with phrasing like *"use gcv to fix the LibraryStats bug
  in library.py"*. The skill walks you through Ground → Constrain → Verify,
  including the confirmation gate where it asks which cause(s) to fix.
- **Engage with Stage C honestly.** If Claude lists three causes and you just
  reflexively pick #1 every time, you're not learning anything and it will
  show in your report. For these five bugs in particular — concurrency,
  timing, DSL precedence — the "obvious" fix is often subtly wrong.
- **Stage V writes the test before the fix.** This is non-negotiable. If
  Claude jumps to the fix without writing a failing test first, stop it and
  send it back.
- **One bug at a time.** Don't try to fix all five in a single GCV session.
  Each bug gets its own cycle. Commit after each green suite so your git
  history mirrors your debugging sequence.

### Must-not-do

- Don't read `tests/test_library.py` before drafting your Stage C analysis
  for each bug. The tests will give away the "what" and rob you of the "why."
  Use them to **verify** fixes, not to **find** the bugs.
- Don't change the test files. The acceptance tests are the grading rubric.
- Don't fix bugs outside GCV. "I just saw it and patched it" is not a valid
  entry in the report.
- Don't have Claude write the whole report for you. See honor pledge below.

---

## Workflow

```bash
# Clone and set up
git clone <your-repo-url>
cd <repo>
pip install -r requirements.txt

# Baseline: confirm you see 8 failing tests
pytest tests/ -v
# Expected: 16 passed, 8 failed — good, now you know what you're solving

# Open in your editor
code .        # VS Code
# or
claude        # Claude Code terminal session
```

Then, for each bug in turn:

```bash
# Start with bug 1 — inside Claude Code:
>  use gcv to fix the LibraryStats bug in library.py.
>  don't read the tests/ folder until i tell you to.

# Work through G, C, V with Claude. At the Stage C gate, THINK.
# Don't rubber-stamp the recommendation. Your report depends on this.

# Once the GCV session is done, run the acceptance tests:
pytest tests/test_library.py::TestLibraryStats -v
# Expected for bug 1: 4 passed

# Commit and move on:
git add library.py tests/
git commit -m "Fix bug 1 (LibraryStats) via GCV"
```

Repeat for bugs 2, 3, 4, 5. Suggested order: **1 → 2 → 3 → 4 → 5**, but the
five are independent — you can tackle them in any order.

### A note on Bug 5

Bug 5 is a concurrency bug whose failing tests rely on a real I/O syscall
yielding the GIL. They are deterministic on CPython 3.10+ but you may see
slightly different `q.size()` values across runs (e.g. 50 instead of 56 out of
60). The relevant assertion — `q.size() == 5` — fires either way. If a Stage
V test you write yourself looks intermittent, that's a sign you've isolated
the right cause: the fix should make `q.size()` exactly equal to `capacity`
on every run.

### Final check

```bash
pytest tests/ -v
# Expected: 24 passed
```

If any test still fails, you have unfinished work. If the count is right but
you didn't follow GCV for every bug, your report will reveal that and
you'll be marked down — so just do it right the first time.

---

## The report (`REPORT.md`)

Fill in the template at `REPORT.md` (already in this repo). It has **five
questions per bug** plus a short reflection section. Be concrete. One-line
answers are fine when one line is the honest answer, but the reflection at
the end needs actual prose.

The single most important question is **"did you agree with Claude's
recommendation, and why or why not?"** This is where Stage C pays off. If
every answer is "yes, I went with #1," that's a sign you weren't engaging.
At least once across the five bugs, you should find yourself either:
- Picking a different cause than Claude recommended, or
- Asking Claude to `redo` the Stage C analysis, or
- Selecting multiple causes, or
- Realizing after Stage V that the wrong cause was picked.

The bugs in this version of the assignment were specifically chosen because
LLMs tend to hand-wave their causes. Pay particular attention to:
- **Bug 1**: Claude may suggest "add a lock" without noticing one is already
  declared and just used wrong.
- **Bug 2**: Claude may suggest "reset the deque" or "use absolute time"
  rather than fixing the inequality. The real bug is one character.
- **Bug 3**: Claude may "fix" precedence by adding parens instead of changing
  the split order.
- **Bug 4**: Claude may suggest replacing `heapq.merge` with `sorted()` —
  which works but loses the streaming semantics. The minimal fix is a
  tiebreaker tuple.
- **Bug 5**: Claude may move the check inside the lock but still leave the
  I/O outside it — partially fixing the race but leaving a smaller window.

If none of those moments happened, the assignment was too easy for you — say
so in the reflection, and back it up with a specific bug where the analysis
felt trivial and why.

---

## Grading rubric (100 points)

| Area | Points | What we're looking for |
|---|---:|---|
| Acceptance tests pass | 40 | `pytest tests/` reports 24 passed, 0 failed |
| GCV followed for every bug | 20 | Git history + report show G, C, V for each; test before fix |
| Report quality | 25 | Specific, concrete, shows engagement with Stage C's gate |
| Reflection | 10 | Honest take on what GCV helped with and where it felt like overhead |
| Code hygiene | 5 | Minimal fixes, no unrelated changes, reasonable commit messages |

**Automatic 0 on the report portion** if we detect the report was
LLM-generated in a way that doesn't match your actual session. See honor
pledge.

---

## End-of-semester Oral Defence

A randomly-selected subset of students will be asked to defend this assignment
in a 10–15 minute oral viva at the end of the semester. The questions below
are the **pool we draw from** — not every question will be asked, but every
question is fair game. Bring your `library.py`, your `REPORT.md`, and your
git log to the viva. You may not bring Claude Code.

If you wrote the report yourself and engaged honestly with Stage C, these
questions are easy. If you let Claude do the thinking for you, they are not.

### General — methodology

1. Walk us through the GCV cycle in your own words. What does each stage
   prevent that "just ask Claude to fix it" doesn't?
2. Why does Stage V demand the failing test be written *before* the fix?
   What goes wrong if you write the fix first and the test second?
3. The skill asks you to rank three causes at Stage C. Why three? Why not
   one (the most likely) or ten (be exhaustive)?
4. Show us a commit where you picked something other than Claude's #1
   recommendation. Talk us through why.
5. Were any of your Stage V tests *weaker* than the corresponding acceptance
   test? Why is that OK (or not OK)?

### Bug 1 — `LibraryStats`

6. The class already declares `self._lock`. The bug isn't "no lock" — what
   is it exactly, and why is releasing the lock between the read and the
   write enough to lose updates?
7. Suppose someone "fixes" this by changing `self._counts.get(branch, 0)` to
   `self._counts.setdefault(branch, 0)`. Does that fix the bug? Why or why not?
8. Could you reproduce the lost-update bug with only 2 threads and 1
   increment each? If yes, sketch the schedule. If no, explain why N has to
   be larger.
9. Why does the test set `sys.setswitchinterval(1e-6)`? Would the test still
   fail reliably without it? How would you find out?

### Bug 2 — `RateLimiter`

10. Show us the one-character difference between the buggy version and the
    fix. Now justify the choice from the docstring's wording.
11. The docstring describes the window as the half-open interval
    `(t - window_seconds, t]`. If the spec instead said `[t - window_seconds, t)`,
    which inequality would be correct and why?
12. The test injects `now` directly. Why is that better than mocking
    `time.monotonic`? What would be lost if we tested against the real clock?
13. Would this bug ever surface in production if requests were never sent at
    *exactly* the boundary? Argue both sides.

### Bug 3 — `parse_query`

14. State, in plain English, the operator-precedence convention that the
    docstring requires. Why is it standard (SQL, Python, C) to give AND
    higher precedence than OR?
15. Construct a query that returns the *same* result regardless of whether
    the bug is present. Now construct one that returns *different* results.
    What property distinguishes the two?
16. Claude may have suggested "fix this by adding parentheses." Why is that
    not a fix?
17. The grammar in the docstring is recursive (`expr := or_expr`,
    `or_expr := and_expr ...`). The buggy implementation uses string
    splitting. What category of inputs would break *any* split-based
    implementation, even a correct one?

### Bug 4 — `merge_branch_events`

18. What's the *exact* exception raised on a tie, and why does Python raise
    it for dicts but not for, say, ints?
19. The fix adds a tuple element like `(timestamp, 0, i, event)`. Explain
    each of the four positions. What would go wrong if you swapped the `0`
    and the `i`?
20. Could you fix this with `sorted(a + b, key=lambda e: e["timestamp"])`?
    Is that better or worse than the heap-merge fix? Be specific about
    tradeoffs (memory, stability, streaming).
21. The docstring promises "branch A first on a tie." Why is that not
    automatically guaranteed by `heapq.merge`?

### Bug 5 — `HoldQueue` (the one most likely to come up)

22. Walk us through the exact sequence of CPython events that lets two
    threads both pass `if len(self._items) >= self.capacity` before either
    appends. Be specific about where the GIL is released.
23. Why does pure `list.append` not race in CPython, but check-then-append
    does?
24. We tried this same bug *without* the write-ahead log and the race didn't
    reproduce on CPython 3.12. Why does adding `open()/write()` make the
    race deterministic?
25. Suppose you "fix" the bug by moving the `if len(...) >= capacity` check
    inside the lock but leave the `open()` outside. Does the bug fully go
    away? Argue carefully.
26. Suppose you "fix" the bug by replacing the `Lock` with an `RLock`. Does
    that change anything? Why or why not?
27. If we removed the GIL (free-threaded Python, PEP 703), would your fix
    still be correct? What additional concerns would matter?
28. The acceptance test asserts `q.size() == 5` exactly. Could a
    *correctly-fixed* implementation ever produce `q.size() < 5` under load?
    What would have to be true?

### Cross-cutting

29. Of the five bugs, which one would have been hardest to find by reading
    the code top-to-bottom (without GCV, without tests)? Defend your pick.
30. Which bug is the one most likely to ship to production undetected? Why?
31. If you had to add a sixth bug to this assignment in another LLM-weak
    area, what would you pick and why?
32. Show us your worst-quality commit message and explain what you'd do
    differently next time.

---

## Honor pledge

You *will* use Claude Code for the debugging — that's the point of the
assignment. But:

- **The report is yours.** It's a record of *your* decisions and *your*
  reasoning, not Claude's. Using Claude to polish grammar or check clarity
  is fine. Using Claude to write the answers is not.
- **Git history should mirror your work.** If your commits all land in one
  push five minutes before the deadline with messages like "fix everything,"
  we'll have questions.
- **If you got stuck, say so in the report.** "I got stuck on Bug 5 because I
  didn't realize `open()` releases the GIL, and asked Claude to redo Stage C
  twice before I understood the I/O angle" is worth more than a fabricated
  clean narrative.

By submitting, you confirm the fixes and the report represent your own work
under the rules above.
