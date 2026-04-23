# GCV Skill — Proposed Improvements

**Baseline:** `skill/SKILL.original.md` (the version provided).
**My version:** `skill/SKILL.md`.

The baseline skill is already well-structured. The proposed changes are
additive — no existing section was deleted, no existing instruction was
reversed. They close concrete gaps I hit while designing and verifying the
five-bug assignment in this repo.

## Why these changes at all

Two of the five assignment bugs (`LibraryStats`, `HoldQueue`) are
concurrency bugs. While building the acceptance test for `HoldQueue`, I
discovered a sharp real-world limitation: a `check-then-act` TOCTOU race
in pure-Python, no-syscall code does **not** reproduce on CPython 3.12
even under 500 threads with `sys.setswitchinterval(1e-6)` — the GIL
serializes the whole critical section. I had to restructure the bug to
include an `open()` syscall between the check and the act before the race
fired reliably (I verified 8/8 baseline runs after that change; before it,
0/10 runs reproduced).

A student doing Stage V on that bug will hit exactly this wall, and
nothing in the baseline skill warns them or gives them a way out of it.
The additions below are designed to fail fast and fail informatively when
a student encounters the same situation.

---

## Changes, grouped by stage

### Stage G — "Environment matters more than you think"

**What I added:** a short paragraph telling students to capture Python
build (CPython/PyPy, free-threaded or not), OS, CPU count, and any
I/O dependencies when the bug is timing/concurrency/I/O-shaped.

**Why:** On a free-threaded build (PEP 703, 3.13t+), several of these bugs
surface *without* `setswitchinterval` tricks. On PyPy, the GIL semantics
are different. A student who doesn't record their environment can't
usefully compare notes with a TA, and a "works on my machine" Stage V
test is worse than no test.

### Stage C — "Causes-collapse check" and "Domain-specific prompts"

**What I added:** two new subsections.

1. **Causes-collapse check.** Before committing to a ranking, explicitly
   ask: "would two of these lead to the same fix?" If yes, they're one
   cause — merge them and push harder. This is the most common Stage C
   failure mode I observed while testing the skill against the assignment
   bugs: the LLM lists three ways to phrase "add a lock" and calls it a
   day.
2. **Domain-specific prompts.** A short checklist of questions per
   category (concurrency, timing, DSL, merge/sort, I/O, aliasing). These
   aren't exhaustive, they're *anchor questions* — the kind of thing
   that surfaces a genuine third cause when the first two are variants
   of the same idea.

**Why:** The baseline skill's "push harder" hint lists categories but not
the *questions to ask within them*. For the five bugs in this
assignment, those questions are exactly what distinguishes a real
root-cause from a plausible-but-wrong one. Bug 3 (DSL precedence) in
particular: an LLM will often propose "fix by adding parentheses" as
cause #1 and "make the split case-insensitive" as cause #2, missing the
actual split-order bug entirely. The DSL prompt — *"Is operator precedence
encoded in the grammar or in the order of string operations?"* — points
directly at it.

### Stage V — "Determinism under concurrency, timing, and I/O"

**What I added:** a new subsection after the minimum-quality bar,
covering:

- What "deterministic" means for a concurrency test (fail 10/10, not
  9/10).
- Concrete techniques: `Barrier`, `setswitchinterval` inside
  try/finally, GIL yield-point awareness, injected time, exact-boundary
  floats.
- **The GIL yield-point rule.** This is the single biggest addition. If
  there is no syscall / `sleep` / contended-lock-acquire between the
  racing operations, CPython's GIL will serialize them and the race
  won't reproduce, no matter how many threads you throw at it. The
  skill should tell students to check for a yield point *first* rather
  than blindly raising thread count.
- A one-liner shell snippet for smoke-testing the failing test 10x.

**Why:** This directly addresses the wall I hit while building Bug 5.
Without this guidance, a student will write a "race" test that passes
10/10 times on buggy code and conclude the bug isn't a race — when in
fact it is, they just can't provoke it from pure Python. The rule "find
a yield point, or inject one into the test" is what unblocks them.

### Stage V — "Fix-scope audit (before you commit)"

**What I added:** a short checklist of common diff-drift patterns: check
moved inside lock but I/O left outside, inequality flipped at one boundary
but not the other, algorithm replaced when only a tiebreaker was missing,
lock-scope broader than needed.

**Why:** For the assignment's Bug 5, the minimal fix is "put both the
check AND the `open()` inside the lock." A naive fix puts only the check
inside — which closes a smaller race but not the one Stage C identified.
The audit catches this. For Bug 4, a common "fix" replaces `heapq.merge`
with `sorted(a+b)` — that passes tests but silently loses the streaming
memory profile. The audit surfaces that too.

### New guardrail — "A flaky Stage V test is a failed Stage V test"

**What I added:** one bullet in the Guardrails list.

**Why:** The baseline skill says tests must be deterministic but doesn't
say what to do when a supposedly-failing test only fails *sometimes*.
Students' default reaction is to raise thread counts; the right reaction
is to return to Stage C because "surfaces only sometimes" is information
about the bug. The guardrail names this failure mode so students don't
silently accept a flaky red as a working contract.

### Final report — "Repro reliability" line

**What I added:** one line in the Verify block of the final report,
applicable only for timing/concurrency/I/O bugs.

**Why:** Reviewers need to know the test's red-run reliability to judge
whether the fix is actually protecting against regressions. Hiding that
data behind "it passes now" loses a crucial signal.

### New worked-example block — "Shape of a concurrency Stage V test"

**What I added:** a short Python block showing the canonical shape of a
concurrency test: `Barrier`, `setswitchinterval` + try/finally, exact
equality assertion, plus a note about the 10x smoke-test.

**Why:** The baseline's worked example is single-threaded. A student's
first concurrency test is where the baseline abstractions ("deterministic
test") meet the concrete reality (`Barrier` / `setswitchinterval` /
yield-point rules). Showing the shape saves them from half an hour of
cargo-cult copy-paste from Stack Overflow.

---

## What I deliberately did NOT change

- **The three-stage structure** (G, C, V) and the confirmation gate. These
  are the core of the methodology; changing them would change what the
  skill *is*, not improve it.
- **The template for listing three causes.** The template's discipline —
  likelihood tag, "why plausible", distinguishing evidence — is load-bearing.
  Reformatting it would fragment skill output across different runs.
- **The worked example.** I added a second shape-only block for
  concurrency, but the original single-threaded worked example stays
  intact because it's still the cleanest illustration of the rhythm.
- **The guardrails already present.** I only appended; no existing
  guardrail was softened or removed.

---

## Verification that the improvements survive first contact

I walked through each of the five assignment bugs mentally against the
improved skill:

- **Bug 1 (LibraryStats):** Stage C's domain prompt for concurrency
  ("are there operations *between* two `with lock:` blocks that mutate
  state?") points directly at the release-between-read-and-write bug.
  Stage V's determinism subsection tells the student to verify 10/10
  reds before fixing, which rules out false-positive "fixed" reports.
- **Bug 2 (RateLimiter):** Stage C's timing prompt asks which inequality
  applies at the boundary, and whether the spec uses open or half-open
  intervals — the bug is exactly that mismatch.
- **Bug 3 (parse_query):** Stage C's DSL prompt — *precedence in grammar
  vs string-operation order* — directly names the bug's structure.
- **Bug 4 (merge_branch_events):** Stage C's merge prompt asks whether
  tiebreaking values form a total order; the bug is that they don't
  (dict comparison raises TypeError). Fix-scope audit warns against the
  "replace with sorted(a+b)" over-fix.
- **Bug 5 (HoldQueue):** Stage C's concurrency prompt asks *"what yields
  the GIL?"*, which surfaces `open()` as the race-enabling syscall.
  Stage V's yield-point rule prevents the student from giving up when
  pure-Python contention tests don't reproduce the race. Fix-scope audit
  catches the "moved check inside lock but left I/O outside" partial fix.

Each improvement was motivated by a concrete gap I hit, and each
applies to at least one of the five bugs.
