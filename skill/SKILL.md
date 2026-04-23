---
name: gcv
description: Systematic bug-fixing workflow using the Ground-Constrain-Verify (GCV) methodology with pytest. Use this skill whenever the user wants to debug, fix, or investigate a bug in Python code — especially when they mention "GCV", "ground constrain verify", "debug this", "fix this bug", "why is this failing", or are working in a directory named like `bug1`, `bug2`, `bugs/`, `repro/`, or a `demo/bug*` path. Also trigger when the user pastes a traceback and asks for a fix. This skill enforces evidence-gathering, three-cause root-cause ranking, an interactive confirmation gate between analysis and fix (the user picks which cause(s) to fix — the model proposes, the user decides), and a failing-test-first fix via pytest. Every bug fix produced under this skill has a pytest contract.
---

# GCV: Ground → Constrain → Verify

A disciplined bug-fixing loop. The goal is to replace the default *"Fix this"* → *LLM guesses plausible patch* → *maybe works* pipeline with a grounded, evidence-driven, test-backed process.

Do the three stages **in order**. Do not jump ahead to a fix.

---

## Stage G — Ground

Collect evidence before proposing anything. If you have not read the buggy file yet, you are not ready to move past G.

Required evidence — gather all of it:

1. **The buggy source file(s)** — read them with `cat` / `view`. Do not rely on the user's paraphrase or your own assumptions.
2. **The exact reproduction command** — how to trigger the bug (e.g. `python buggy.py`, `pytest test_foo.py::test_bar`).
3. **The observed failure** — the traceback verbatim, or the actual output alongside the expected output.
4. **Relevant context** — Python version, key dependency versions, input data if the bug is data-dependent.

Concretely, in a bug directory:

```bash
ls                          # see what files exist
cat *.py                    # read the buggy code
cat README* 2>/dev/null     # any instructions from the user
pytest -x 2>&1 | head -50   # reproduce and capture the failure
```

If reproduction requires input the user has not provided, ask. Do not invent inputs to make the traceback "fit" a familiar bug.

### Environment matters more than you think

For bugs where the repro depends on scheduling, timing, or I/O, **also record**:

- Python version *and build* — CPython vs PyPy, free-threaded (PEP 703) vs default, debug vs release.
- OS and CPU count — thread scheduling differs across macOS, Linux, and Windows.
- Any filesystem / socket / subprocess dependencies the code touches.

A test that fails on your laptop may pass on CI, and vice versa. Writing these down up front prevents hours of "why doesn't it repro for me?" later.

**End Stage G with an Evidence Summary** — 3–5 lines, no speculation:

```
Evidence Summary
- Repro:       pytest -x
- Observed:    ZeroDivisionError in average() at line 14 when items == []
- Expected:    average([]) should return 0.0
- Python:      3.11 (CPython, default GIL)
- Inputs:      items=[] (edge case)
```

---

## Stage C — Constrain

Force root-cause analysis. Skipping this is where most LLM-driven debugging goes wrong — the model grabs the most common fix for the surface symptom and misses the actual cause.

**List exactly three plausible causes, ranked by likelihood, each with distinguishing evidence.** Use this template verbatim:

```
## Possible causes

1. <cause>  — likelihood: high
   - Why plausible: <what in the evidence points here>
   - Distinguishing evidence: <a specific check, print, or test that would confirm or rule this out>

2. <cause>  — likelihood: medium
   - Why plausible: ...
   - Distinguishing evidence: ...

3. <cause>  — likelihood: low
   - Why plausible: ...
   - Distinguishing evidence: ...

## Recommended
<which cause(s) you would fix and why, based on the evidence>
```

Discipline to hold yourself to:

- **All three causes must be genuinely plausible.** If #2 and #3 are filler, the exercise has failed. Push harder — think about upstream callers, data assumptions, concurrency, floating-point, mutation of shared state, version mismatches, off-by-one on the *other* boundary, etc.
- **Distinguishing evidence must be concrete** — a specific check you can actually run, not "look at it more carefully."
- If a one-line probe (e.g. `print(type(x))`, `pytest -vv`, adding a `breakpoint()`) would rule causes in or out cheaply, run it before committing to a root cause.

### Causes-collapse check

Before you commit to the ranking, ask: **"would two of these causes lead to the same code change?"** If yes, they're one cause phrased two ways — merge them and push harder for a genuinely distinct third. Three causes that all collapse to `add a lock` is one cause wearing three hats.

### Domain-specific prompts

Use these to widen the search when your first two causes are obvious variants of each other. LLMs tend to anchor on the most common fix for the symptom; these categories surface second- and third-order causes:

- **Concurrency / shared state.** Where is the lock acquired? Where is it released? Are there operations *between* two `with lock:` blocks that mutate state? What yields the GIL (`open`, `read`, `write`, socket I/O, `time.sleep`, contended `threading.*.acquire`, C extensions)? Is the lock being re-created per call instead of per instance?
- **Timing / boundaries.** Which of `<`, `<=`, `>`, `>=` is at the boundary, and does the spec use open or half-open intervals? What's the behavior *exactly at* the cutoff — not just before or after? Is time read once per call or multiple times?
- **Parsers / DSLs.** Is operator precedence encoded in the grammar or in the order of string operations? What happens with nested operators, with operators appearing inside literals, with whitespace variations, with empty sub-expressions?
- **Cross-source merges / sorting.** What's the tiebreaker when the sort key ties? Is the underlying comparison total — do the tiebreaking values define an order, or can comparing them crash (dicts, sets, mixed types)?
- **I/O / external calls.** Does the call release the GIL? Can it partially succeed (write some bytes, then fail)? What's the retry/idempotency story? Is the file handle reused across calls?
- **State aliasing.** Mutable default arguments, shared class-level lists, objects captured in closures, generators re-consumed after exhaustion.

You do not need to consult every category for every bug. Pick the two closest to the symptom and walk through their questions.

### Confirmation gate — STOP and ask the user

**Do not proceed to Stage V on your own.** After presenting the three causes and your recommendation, ask the user which cause(s) to fix and wait for their answer. The pause is the point — it forces a conscious decision about scope rather than letting the model silently pick.

Ask with this prompt, verbatim in spirit (phrasing can vary):

> Which cause(s) should I fix?
> - **`1`** / **`2`** / **`3`** — fix just that one
> - **`1,2`** or **`all`** — fix multiple (I'll use separate tests and a separate commit for each)
> - **`redo`** — none of these look right, let me reconsider the analysis
> - **`skip`** — don't fix anything, just leave the analysis
>
> *(My recommendation: `<N>`, because `<one-line reason>`.)*

Rules for handling the answer:

- **Single cause (`1`, `2`, or `3`)** — proceed to Stage V for that cause only. Do not silently fix the others "while you're there," even if they're trivial.
- **Multiple causes (`1,2` or `all`)** — handle them as separate V cycles in sequence: test for cause A, fix A, green suite → test for cause B, fix B, green suite. One commit per cause. This keeps the diffs reviewable and the test-to-fix mapping clean.
- **`redo`** — return to Stage C with a fresh attempt. Something in your causes or recommendation didn't match the user's mental model; treat that as real signal, not pushback. Ask what's off before re-listing.
- **`skip`** — stop here. Write the analysis to disk (e.g. `gcv_analysis.md` in the bug directory) so the work isn't lost, and end the session. Do not apply a fix.
- **Anything else** — treat as a free-form instruction and respond to it directly. The user may narrow scope ("just #1, and only for the empty-list input"), widen it ("fix #1 and add the bounds check from #3 as an xfail"), or ask a clarifying question. Answer and re-ask the gate.

Do not infer consent. A user saying "looks good" or "makes sense" is commentary on the analysis, not approval to proceed — re-ask the gate explicitly.

---

## Stage V — Verify (test first, then fix)

**Write the failing pytest test BEFORE writing the fix.** The test is the contract the fix must satisfy.

Order of operations — do not reorder:

1. **Write the test.** Create or extend `test_<module>.py` in the bug directory (or `tests/` if one exists). The test must reproduce the bug — it should fail against the *current*, unfixed code, and fail for the reason identified in Stage C. Not a generic smoke test.
2. **Run pytest and confirm the test fails the way you predicted.** If it passes on unfixed code, or fails for a different reason, your root cause is wrong — go back to Stage C.
3. **Apply the minimal fix.** No refactors, no stylistic cleanup, no "while I'm here" changes — those muddy the test-to-fix relationship.
4. **Run pytest again.** The new test must pass, and no previously-passing test may break. Run the whole suite in the bug directory, not just the new test.
5. **If step 4 fails**, do not paper over it. Either the fix is wrong or the fix broke something — return to Stage C with the new evidence.

### pytest conventions this skill uses

- **Filename:** `test_<thing>.py` — pytest's default discovery.
- **Function name:** name it for the observable behavior under bug, not the internal mechanism.
  - Good: `test_average_of_empty_list_returns_zero`
  - Bad:  `test_fix_for_line_14`, `test_bug1`
- **Exception behavior:** use `pytest.raises`.
  ```python
  with pytest.raises(ValueError, match="empty"):
      parse("")
  ```
- **Floating-point:** use `pytest.approx`.
- **Multiple bug-triggering inputs:** use `@pytest.mark.parametrize`.
- **Stateful bugs:** use a fixture to set up the exact state the bug requires, so the repro is readable.
- **Run from the bug directory:** `pytest -x -vv` during the debug loop; drop `-x` for the final run so you see the full picture.

### Minimum test quality bar

A GCV test must:

- **Fail before the fix** for the specific reason in Stage C (not an import error, not a syntax error — the actual bug).
- **Pass after the fix.**
- **Be deterministic** — no reliance on wall-clock time, network, or unseeded randomness.
- **Name the behavior, not the bug number** — so the test stays readable once the bug is a memory.

### Determinism under concurrency, timing, and I/O

For bugs whose repro depends on scheduling or timing, "deterministic" means the test must fail **every single run** on the buggy code — not 9 times out of 10. A test that's occasionally lucky is worse than no test: it will hide the regression that re-introduces the bug, and it will waste a future debugger's afternoon on "is this flaky?".

Techniques to force determinism:

- **Threading races.** Use `threading.Barrier(N)` to release all N workers at the same instant. Pick N large enough that even one "lucky" interleave still yields a visible state violation — thread counts in the tens to low hundreds are usually sufficient, thousands is almost always overkill.
- **GIL-bound races that serialize in single-threaded CPython.** Before relying on raw thread contention, check whether there's a real GIL yield point between the racing operations. Without one, CPython's GIL may serialize the entire critical section and hide the race. Yield points include syscalls (`open`, `read`, `write`, `socket.*`), `time.sleep`, contended `threading.*.acquire`, and many C-extension calls. If the buggy code has none, cranking up thread count won't help; either the bug isn't really a race, or your test needs an injected yield.
- **Switch pressure.** `sys.setswitchinterval(1e-6)` inside a `try / finally` block tightens the GIL switch interval and increases the odds of an adversarial interleave. Restore the old value before the test returns so other tests aren't destabilized.
- **Timing boundaries.** Inject time. Don't sleep-and-hope. If the unit under test reads `time.monotonic()` or `time.time()`, give it a `now` parameter (or monkeypatch the clock) and pass *exactly* the boundary value in the test.
- **Floating-point boundaries.** Use `pytest.approx` for the numeric comparison, but feed the function the exact boundary input — not `boundary + 1e-9`.

Smoke-test the failing test: **run it 10 times in a row on the buggy code.** If even one run passes, either the test isn't exercising the bug hard enough or the root cause is wrong. Do not proceed to the fix until you see 10/10 reds.

```bash
for i in $(seq 1 10); do pytest -x tests/test_foo.py::test_race_case -q || true; done
```

### Fix-scope audit (before you commit)

Read the diff once more and ask: *"does this close exactly the cause I selected in Stage C, or a narrower / different one?"* Common drift to check for:

- The capacity check is moved inside the lock but a companion I/O operation is left outside → the race is smaller but still open.
- An inequality is flipped at the reported site but the opposite boundary (start vs end of window) still has the same bug.
- The cause said "missing tiebreaker" but the fix replaced the algorithm entirely (e.g. `heapq.merge` → `sorted`) — that works but loses properties the original had (streaming, memory profile, stability guarantees).
- A thread-safety fix that adds a broader lock than needed, serializing calls that could have stayed concurrent.

If the audit surfaces a mismatch, either tighten the fix or update Stage C to match what you actually fixed. The record should reflect what happened, not what you planned.

---

## Final report format

After the fix lands, deliver a terse report in this shape:

```
## Ground
- Repro:    <command>
- Observed: <one-line failure description>
- Expected: <one-line correct behavior>
- Env:      <Python version, OS, GIL mode — only if the bug is timing/concurrency/I/O>

## Constrain
- Causes ranked:  1) <a>  2) <b>  3) <c>
- Recommended:    <n>
- User selected:  <n>   (or: <n,m> if multiple)

## Verify
- Test added:     <path>::<test_name>
- Fix:            <1–3 sentences on what changed and why>
- Repro reliability: <e.g. "fails 10/10 runs on buggy code"> — only for timing/concurrency/I/O bugs
- Result:         <N passed, 0 failed>
```

If the user selected multiple causes, include one **Verify** block per cause — in the order they were fixed — so the test-to-fix mapping stays clear.

Keep it short. The user can read the diff; the report's job is to make the reasoning auditable.

---

## Guardrails (common failure modes to avoid)

- **Skipping G.** Writing a fix for code you haven't actually read is the single most common LLM debugging failure. Always cat the file.
- **Skipping C when the bug "looks obvious."** Obvious bugs are exactly where a second-order cause hides behind the first. Write all three causes even when you're sure.
- **Skipping the confirmation gate.** After Stage C, stop and ask. Don't silently pick your own recommendation and march on — the pause is the point. A user saying "looks good" is commentary, not consent.
- **Letting V degrade into a smoke test.** A test that just calls the function without asserting the buggy behavior is not a contract. The test must fail for the right reason before the fix.
- **A flaky Stage V test is a failed Stage V test.** If your failing test fails 7/10 runs, your root cause is wrong or your reproducer is too weak. Do not paper over this by raising thread count and hoping. Return to Stage C — *"the bug surfaces only sometimes"* is itself a clue, not noise. For GIL-bound races in particular, check whether there's actually a yield point between the racing operations.
- **Fix drift.** Keep the diff minimal and scoped to the selected cause(s). Separate PR/commit for cleanup.
- **Fix shrinkage.** The other direction of drift: the diff closes a narrower race than the one Stage C identified (check moved inside the lock, I/O left outside). Run the fix-scope audit.
- **Re-fitting the cause to the fix.** If Stage C picked cause A but the fix you're writing is really for cause B, stop and update Stage C honestly. The record should reflect what actually happened.

---

## Worked mini-example (shape, not content)

User prompt: *"fix the bug in demo/bug1"*

```
# Stage G
$ ls demo/bug1
buggy.py  test_buggy.py  README.md
$ cat demo/bug1/buggy.py
def average(items):
    return sum(items) / len(items)
$ pytest demo/bug1 -x
... ZeroDivisionError: division by zero

Evidence Summary
- Repro:    pytest demo/bug1 -x
- Observed: ZeroDivisionError in average() when items == []
- Expected: average([]) should return 0.0 (per README)
- Python:   3.11

# Stage C
1. No guard for empty list — likelihood: high
   - Why: division by len(items) with no length check; traceback points here
   - Distinguishing evidence: call average([]) directly, confirm ZeroDivisionError
2. items contains non-numeric → TypeError mis-surfacing — likelihood: low
   - Why: could explain some traceback shapes
   - Distinguishing evidence: traceback says ZeroDivisionError, not TypeError → ruled out
3. sum() on generator exhausted upstream — likelihood: low
   - Why: if items were a generator re-used elsewhere, len() would also fail differently
   - Distinguishing evidence: items is a list literal in the failing test → ruled out

Recommended: (1) — traceback + direct repro both point there; (2) and (3) ruled out above.

# Gate — ask the user
> Which cause(s) should I fix? `1` / `2` / `3` / `1,2` / `all` / `redo` / `skip`
> (My recommendation: `1`, because it's the only one the evidence supports.)

User: 1

# Stage V
# test first (expected to fail)
def test_average_of_empty_list_returns_zero():
    assert average([]) == 0.0

$ pytest demo/bug1::test_average_of_empty_list_returns_zero
FAILED — ZeroDivisionError  ✓ fails for the right reason

# minimal fix
def average(items):
    if not items:
        return 0.0
    return sum(items) / len(items)

$ pytest demo/bug1
3 passed
```

### Shape of a concurrency Stage V test

Concurrency tests need more scaffolding. The shape:

```python
def test_count_is_not_lost_under_contention():
    stats = LibraryStats()
    N_THREADS, PER_THREAD = 32, 500
    barrier = threading.Barrier(N_THREADS)

    def worker():
        barrier.wait()
        for _ in range(PER_THREAD):
            stats.record_checkout("downtown")

    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        ts = [threading.Thread(target=worker) for _ in range(N_THREADS)]
        for t in ts: t.start()
        for t in ts: t.join()
    finally:
        sys.setswitchinterval(old)

    assert stats.count("downtown") == N_THREADS * PER_THREAD
```

Notes on the shape:

- `Barrier` forces all workers to start at the same instant — no staggered-start luck that lets the first thread finish before the second begins.
- `setswitchinterval` is restored in a `finally` so an exception doesn't leak the setting into sibling tests.
- The assertion is *equality* to the exact expected total, not `>= some lower bound`. Any lost update fails loudly.
- Before trusting the test, run it ten times on the buggy code. If even one run passes, the reproducer is too weak or the root cause is wrong — back to Stage C.

---

This is the rhythm for every bug: evidence, three causes, failing test, minimal fix, green suite. For timing, concurrency, and I/O bugs, add: environment captured, determinism forced, fix scope audited.
