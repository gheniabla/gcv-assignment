# GCV Assignment Report (LLM-weak edition)

**Name:**
**Date:**
**Git commit sha at submission:**

---

## Setup

- Python version I used: `3.__`
- OS / CPU (matters for Bug 5's concurrency tests):
- Did the baseline `pytest tests/` show the expected 16 passed / 8 failed? (yes/no — if no, what you saw)
- Approximate time spent on the whole assignment:
- Which bug took the longest, and why?

---

## Bug 1 — `LibraryStats` (concurrent mutation)

**1. What was the observable failure?** (one sentence — what input, what happened, what should have happened)

**2. What three causes did Stage C rank?** (summarize each in one line)
1.
2.
3.

**3. What did Claude recommend, and what did you pick?**
- Recommendation:
- Your selection: (e.g. `1`, `2`, `1,2`, `redo`, `skip`)
- If you picked the same as the recommendation: why did you trust it here?
- If you picked differently: what in the analysis made you override it?

**4. What did the failing test look like?** (paste the test function body)

```python

```

**5. What was the minimal fix?** (paste the diff or a 1-2 line summary)

```

```

---

## Bug 2 — `RateLimiter` (timing boundary)

**1. What was the observable failure?**

**2. What three causes did Stage C rank?**
1.
2.
3.

**3. What did Claude recommend, and what did you pick?**
- Recommendation:
- Your selection:
- Why:

**4. Failing test:**

```python

```

**5. Minimal fix:**

```

```

---

## Bug 3 — `parse_query` (DSL precedence)

**1. What was the observable failure?**

**2. What three causes did Stage C rank?**
1.
2.
3.

**3. What did Claude recommend, and what did you pick?**
- Recommendation:
- Your selection:
- Why:

**4. Failing test:**

```python

```

**5. Minimal fix:**

```

```

---

## Bug 4 — `merge_branch_events` (cross-source merge)

**1. What was the observable failure?**

**2. What three causes did Stage C rank?**
1.
2.
3.

**3. What did Claude recommend, and what did you pick?**
- Recommendation:
- Your selection:
- Why:

**4. Failing test:**

```python

```

**5. Minimal fix:**

```

```

---

## Bug 5 — `HoldQueue` (I/O race under load)

**1. What was the observable failure?** (Specifically: what value did `q.size()` take, and how reproducible was it across runs?)

**2. What three causes did Stage C rank?**
1.
2.
3.

**3. What did Claude recommend, and what did you pick?**
- Recommendation:
- Your selection:
- Why:

**4. Failing test:** (paste your Stage V test, not the acceptance test)

```python

```

**5. Minimal fix:** (was it sufficient to move only the check inside the lock, or did you have to put the I/O inside too? Why?)

```

```

---

## Cross-cutting questions

**Which bug's Stage C analysis felt the most useful — where ranking three
causes actually changed your thinking versus confirming the first one?**
(Pick one bug and explain in 2-4 sentences. If none felt that way, say so
honestly and explain why not.)

**Did you ever use `redo`, `skip`, or a multi-cause selection at the gate?**
(yes/no — if yes, which bug and what happened)

**Was there a moment during Stage V where the failing test failed for the
*wrong* reason (wrong traceback, ImportError, typo, or — for Bug 5 — a flaky
test that passed on some runs and failed on others)?** What did you do? (If
not, say "no.")

**For the concurrency bugs (1 and 5): did you write a Stage V test that
fails 100% of the time on the buggy code, or did you accept a test that fails
"most of the time"? How did you decide it was reliable enough?**

---

## Reflection (this is the section we actually read carefully)

**In 200-400 words:** What did GCV add to your debugging that you wouldn't
have gotten from "ask Claude to fix this bug"? Where did it feel like useful
discipline, and where did it feel like overhead? Be concrete — reference
specific bugs.

These five bugs were chosen to live in areas where LLMs are notoriously
weak: thread-safety, timing edges, DSL precedence, cross-source ordering,
intermittent I/O races. Did you notice Claude struggling on any of them in a
way you wouldn't have expected for the original (single-threaded, pure
function) bug set? Pick one moment and describe it.

If you came into this thinking "I debug fine without frameworks," has your
view changed? Not looking for a particular answer — looking for evidence you
engaged with the question.

---

## Honesty

- Did you read the tests before drafting Stage C for any bug? (yes/no — "yes
  once, for bug X, because ___" is an acceptable answer)
- Did you use Claude for anything in this report besides spell/grammar check?
  (yes/no — if yes, what)
- Anything else we should know? (got stuck somewhere, used a debugger outside
  of GCV, teammate helped with a concept, the I/O race in Bug 5 didn't
  reproduce on your machine and you needed a workaround, etc.)
