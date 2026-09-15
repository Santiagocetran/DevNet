# CI next steps, 2 of 4 — configure `ruff`, clear the backlog, make it blocking

**Base:** `develop` on `InfiniteZeroFoundation/DevNet` @ `87f6d19`
**Branch:** `ci/phase1-lint-cleanup`, cut from `develop`
**Origin:** `Plans/archive/ci-cd-phase1-plan.md` §3.3 — "PR 3 of 4" of the Phase 1 series. PR 1 (#103)
and PR 2 (#118) are merged; PR 3 (this) and PR 4 (`ci-next-04-forge-fmt-plan.md`) were never opened.
**Status:** rev 2 — rev 1's ruff measurements were confirmed correct in review; three factual errors
and one dangerous piece of guidance were not. Fixed here; see the changelog.

> **Rev 2 changelog.**
>
> - **`forge lint` promotion has more prerequisites than rev 1 claimed** (§3). Rev 1 said the
>   `block.timestamp` question was "the one thing gating `forge lint`". It is not.
>   `.github/scripts/forge_lint_gate.py` sets `FAIL_LEVELS = {"warning", "error"}` and fails on **any**
>   diagnostic at those levels — so the `unsafe-typecast` warnings block promotion just as hard. The
>   timestamp issue is the only unresolved *security decision*; it is not the only prerequisite.
> - **The `F841` guidance could have deleted live behaviour** (§4.3). Rev 1 called these "usually a
>   dead assignment". Inspection of all 14 sites shows the right-hand sides include
>   `build_and_send_tx(...)` — which **submits a transaction** — and `validate_gi_ET_curr_GI(...)`,
>   a guard. All 14 are `--unsafe-fixes`-only for exactly this reason. Replaced with a classification
>   rule.
> - **The archived baseline was misquoted** (§2). Rev 1 attributed 128/107/19 to the archived plan; the
>   plan records **126**/107/19 (§2.7, "`--select E,F --ignore E501` … 125 → **126** after PR 1"). The
>   128 came from PR #118's body.
> - **`bytes32` recount** (§3.2): 33 occurrences on 32 lines, 14 distinct. Rev 1's "32" was the line
>   count.
> - **Verification corrections** (§5): capture the pytest baseline *before* editing rather than
>   assuming it, and run the deliberate-failure test on a disposable branch instead of pushing a break
>   to the implementation PR.

> **This PR was designed in the archived plan and never executed.** §3.3 specifies the rule selection,
> the cleanup order, and the promotion rule. **Do not open a discussion asking whether to do it.** But
> rev 1 overstated this as "nothing here is a new decision" — this plan *does* revise the archived
> scope by separating the Solidity cleanup out of PR 3 entirely (§3), and that revision deserves normal
> review even though the underlying decoupling was approved.

---

## 1. What is wrong right now

`ci.yml` on `develop`, in the `python` job:

```yaml
- name: ruff (advisory)
  continue-on-error: true
  run: |
    python -m pip install ruff
    ruff check .
```

Two separate problems.

### 1.1 The step is advisory, which was always meant to be temporary

Correct on day one, and the reason Phase 1 could ship (archived plan §2.7): a blocking lint gate over
an existing backlog fails every PR including the good ones, and trains contributors to route around
CI. So it shipped honest — reports, doesn't block — with the cleanup scheduled as PR 3, which never
happened.

### 1.2 `ruff check .` has never been told which rules to apply

There is **no `[tool.ruff]` in `pyproject.toml`** and no `ruff.toml` / `.ruff.toml` in the tree.
(`CLAUDE.md` states this explicitly: "There is no `[tool.ruff]` config committed in `pyproject.toml`".)
So `ruff check .` runs ruff's own default selection.

Measured on `develop` @ `87f6d19`, `ruff==0.16.4` (the `PIP_CONSTRAINT` pin):

| What is running | Findings |
|---|---|
| **`ruff check .` — what CI runs today** | **615** |
| `ruff check . --select E,F --ignore E501` — what §3.3 step 3 intends | **133** |

The 615 includes rule families nobody agreed to: `I001` (37), `RUF010`, `PLW1510`, `SIM102`, `B008`,
`S110`, `TRY002`, `UP006`. Ruff 0.16.4's defaults are broader than the `E4`/`E7`/`E9`/`F` floor older
documentation describes — confirmed directly by running it on a two-line throwaway file, which
reported `I001`.

**The consequence:** PR #118's body states the ruff step reports **128** findings. The step as merged
prints ~**615**. The 128 figure describes the backlog under a configuration that was never committed,
because committing it was step 3 of the PR that never opened. Nobody erred; the step just didn't land.

**So the ordering is the opposite of how it looks. The cleanup is not big — the tool is shouting.**

---

## 2. Measured Python backlog

`ruff check . --select E,F --ignore E501`, ruff 0.16.4, `develop` @ `87f6d19`, at CI's scope (repo
root, no extra excludes — so including `cache_model_0/`, which ruff does not exclude by default):

| Rule | Count | Safe auto-fix |
|---|---|---|
| `F541` f-string without placeholders | 68 | yes |
| `F401` unused import | 44 | yes |
| `F841` unused variable | 14 | **no — unsafe only, see §4.3** |
| `E402` import not at top of file | 3 | no |
| `E722` bare `except:` | 3 | no |
| `F811` redefined while unused | 1 | yes |
| **Total** | **133** | **113 safe / 20 by hand** |

### 2.1 Drift against the archived baseline

| Source | Total | Auto | By hand |
|---|---|---|---|
| Archived plan §2.7 (Aug 2026, post-PR-1 projection) | **126** | 107 | 19 |
| PR #118 body | 128 | — | — |
| **Now, `87f6d19`** | **133** | **113** | **20** |

**The Python backlog is essentially static.** Three weeks and ~30 merged PRs added 7 findings. This is
a bounded job that costs the same whenever it is done — an argument for finishing it, not for urgency.

### 2.2 Scope note — `cache_model_0/`

Tracked, and ruff lints its Python; ~34 of the 615 unconfigured findings. **Do not exclude it.** The
archived plan §2.7 already settled this ("it *is* under test … so linting it is correct"), and it holds
the DP mechanism code that BL-23 and BL-24 are actively about. Silencing the linter over it right
before a DP specialist reads it is the wrong direction.

---

## 3. Solidity — out of scope for this PR, and the reason is not only the timestamp question

### 3.1 The gate fails on any warning

From `.github/scripts/forge_lint_gate.py`:

```python
FAIL_LEVELS = frozenset({"warning", "error"})
```

and the archived plan §2.7 records the gate's own output against the tree:

```
::error::forge lint reported 21 finding(s) at level(s) ['error', 'warning']
    17  warning[unsafe-typecast]
     4  warning[block-timestamp]
exit=1
```

So **removing `continue-on-error` requires the pinned Forge 1.7.1 run to emit zero warning/error
diagnostics** — both the `unsafe-typecast` findings and the `block.timestamp` ones, plus anything
added since (PR #118 reported 37 findings, up from 21).

Rev 1's "the one thing gating `forge lint`" was wrong. The correct statement, which should also be
used in the PR body and in the issue from plan 3:

> The timestamp question is the only unresolved **security decision** blocking promotion. It is not
> the only remaining lint finding. Promotion additionally requires a clean pinned-Forge run.

### 3.2 The Solidity backlog is growing while the check is passive

I could not run `forge` in this environment, so I have no current finding count. Measured by grep,
the underlying surface:

| Surface | Archived plan (Aug) | Now @ `87f6d19` |
|---|---|---|
| `bytes32("…")` in `foundry/test/` | 17 occurrences, 7 distinct | **33 occurrences on 32 lines, 14 distinct** |
| `block.timestamp` in `foundry/src/` | 4 findings in 1 file | **19 occurrences across 5 files** |

**Occurrences are not lint findings** — `forge lint` flags a subset. Treat these as direction, not
count: the watched surface has roughly doubled in three weeks.

### 3.3 What this PR does about it

Nothing, deliberately. It leaves the `forge lint` step exactly as merged and adds a comment naming
both prerequisites (§4.5). The Solidity cleanup — `unsafe-typecast` suppressions per archived plan §8
decision 1, plus whatever else a current run reports — is its own PR, and it is **not blocked** by the
timestamp question. Only the final `continue-on-error` removal is.

---

## 4. Changes

### 4.1 Add the rule selection to `pyproject.toml`

Appended after `[tool.pytest.ini_options]`:

```toml
[tool.ruff]
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F"]
ignore = ["E501"]
```

Verbatim from archived plan §3.3 step 3. `target-version` matches `requires-python = ">=3.12"` and
`ci.yml`'s `python-version: '3.12'`. `E501` is ignored deliberately — enforcing it reflows a large
amount of unrelated code for no correctness benefit.

**This is deliberately the narrow floor, not a claim that import ordering is worthless.** Someone may
reasonably want `I`. Say so in the PR body and let that argument happen at review; widening later is a
three-character diff.

### 4.2 Clear the 113 safe auto-fixes

```bash
python -m ruff check . --select E,F --ignore E501 --fix
```

**Never `--unsafe-fixes`.** See §4.3 — here it is not a style preference, it deletes behaviour.

Read the diff properly. The 44 `F401` removals deserve real attention: an import may exist for a
re-export or an import side effect, and ruff cannot tell. Anything intentional gets `# noqa: F401`
with a reason, not a silent restore.

### 4.3 The 20 by hand — `F841` first, because it is the dangerous one

**All 14 `F841` fixes are `--unsafe-fixes`-only, and inspecting every site shows why.** The right-hand
sides are effectful:

```
dincli/cli/modelownerd/gi.py:224     tx_receipt = build_and_send_tx(...)   # SUBMITS A TRANSACTION
dincli/cli/modelownerd/gi.py:252     tx_receipt = build_and_send_tx(...)
dincli/cli/modelownerd/model.py:260  tx_receipt = build_and_send_tx(...)
dincli/cli/aggregator.py:221,373     ref_gi = ctx.obj.validate_gi_ET_curr_GI(...)   # A GUARD
dincli/cli/auditor.py:337,551        ref_gi = ctx.obj.validate_gi_ET_curr_GI(...)
dincli/cli/modelownerd/gi.py:354     ref_gi = ctx.obj.validate_gi_ET_curr_GI(...)
dincli/cli/task.py:177               target_gi = ctx.obj.validate_gi_ET_curr_GI(...)
dincli/cli/auditor.py:116            DinCoordinator_contract = ...
dincli/cli/client.py:106             taskAuditor_contract = ...
dincli/cli/modelownerd/lms.py:82     taskAuditor_contract = ...
dincli/cli/modelownerd/lms_evaluation.py:83  task_auditor_Contract = ...
dincli/cli/task.py:304               taskCoordinator = ...
```

Deleting the statement at `gi.py:224` would remove a chain transaction. Deleting `ref_gi = …` would
remove a validation guard that raises on a GI mismatch. **Classify each RHS before touching it:**

1. **Effectful call, result genuinely unused** (`build_and_send_tx`, `validate_gi_ET_curr_GI`) → keep
   the call, drop the binding. `build_and_send_tx(...)` as a bare expression statement.
2. **Intentionally ignored unpacked value** → rename to `_`.
3. **Pure construction with no effect** (the `*_contract` lookups — verify each; contract resolution
   in `DinContext` may cache or fetch) → delete the statement only after establishing the call itself
   is unnecessary.
4. **When in doubt, `# noqa: F841` with a one-line reason.** A documented suppression beats a deleted
   transaction.

Then run targeted tests for every touched validation and transaction path — not just the full suite.

**The remaining 6:**

- **3 × `E402`.** Usually a deliberate late import dodging a circular dependency or an expensive
  module. If deliberate, `# noqa: E402` + reason beats restructuring.
- **3 × `E722` bare `except:`.** Narrow to `except Exception:` at minimum — a bare `except:` also
  catches `KeyboardInterrupt` and `SystemExit`, so in a long-running `dind` process Ctrl-C gets
  swallowed by an error handler.

### 4.4 Promote the `ruff` step

```yaml
      - name: ruff
        run: |
          python -m pip install ruff
          ruff check .
```

`continue-on-error: true` removed, `(advisory)` dropped from the name. `ruff` stays pinned via
`PIP_CONSTRAINT` — which matters more now, since a ruff release adding a rule to `E`/`F` could
otherwise turn PRs red with nobody changing anything. Per `ci-next-01` §4.2, whether Dependabot covers
that pin is verified on its first run; until then, treat it as hand-managed.

### 4.5 Leave `forge lint` alone, and name both prerequisites

No change to the step. Add above it:

```yaml
      # Advisory until a pinned Forge 1.7.1 run emits zero warning/error diagnostics
      # (forge_lint_gate.py fails on any of either). Two things stand in the way:
      #   1. the unsafe-typecast findings in test/ — cleanup, no decision needed
      #   2. the block.timestamp findings in src/DinValidatorStake.sol — an open
      #      security decision, issue #<N> / BL-25
      # Only (2) is a judgement call; (1) is just work. Archived Phase 1 plan 3.3 step 5.
```

**`#<N>` is a placeholder.** File BL-25 and its issue (`ci-next-03`) **before** opening this PR and
replace every occurrence — there are placeholders here and in §6.

---

## 5. Verification

1. **Capture the baseline first, before any edit:**
   ```bash
   pytest -m "not integration" -q | tail -3    # record this number
   ruff check . | tail -2                       # expect ~615
   ```
   "Expect the same pass count as before" is worthless without the before count actually written down.
2. **Config applies.** After §4.1, `ruff check .` and `ruff check . --select E,F --ignore E501` must
   report the *same* count. If the bare invocation still reports ~615, the `[tool.ruff]` block is not
   being picked up.
3. **Clean.** `ruff check .` exits 0, "All checks passed".
4. **Tests match the baseline.** Re-run the §5.1 command; the pass count must be identical. A drop
   means a fix was wrong — most likely an `F401` removal that was doing import-time setup, or an
   `F841` statement deletion that removed a call.
5. **Import smoke test for the `F401` churn**, since unit tests may not import every touched module:
   ```bash
   python -c "import dincli.main"
   dincli --help
   ```
6. **Targeted tests for the `F841` paths** — every module in the §4.3 list that has test coverage,
   run by name.
7. **Prove the gate blocks — on a disposable branch, not this one.** Push a branch with a deliberate
   unused import, open a throwaway PR, confirm `Python` and `CI OK` both go red, then close and delete
   it. Rev 1 suggested pushing a break to the implementation PR and "dropping" the commit; that either
   rewrites the branch under reviewers or leaves a break/revert pair in the history. For the real PR, a
   local failure plus reading `ci-ok`'s `needs:` list is enough.
8. **`forge lint` is still advisory** — the Solidity job stays green with findings present.

---

## 6. PR body outline

> **Title:** `ci: configure ruff, clear the E/F backlog, make it blocking (CI/CD Phase 1, PR 3 of 4)`
>
> PR 2 (#118) shipped both lint checks advisory over an existing backlog, deliberately — a blocking
> gate on day one fails every PR including the good ones. This is the scheduled cleanup for the Python
> half.
>
> **Configuration first, because that is most of the apparent problem.** `pyproject.toml` has never had
> a `[tool.ruff]` section, so `ruff check .` runs ruff 0.16.4's full default selection — import
> sorting, `SIM`, `PL`, `B`, `TRY` and more — printing ~615 findings today. Under the selection this
> PR adds (`select = ["E","F"]`, `ignore = ["E501"]`, from Phase 1 plan §3.3 step 3) it is 133, of
> which 113 are safe auto-fixes.
>
> For the record: #118's body cites 128. That was the archived plan's projection (126) under this
> configuration — which was never committed, because committing it was step 3 of the PR that never
> opened. Same pile, described under settings that weren't in the tree.
>
> **Contents:** rule selection added · 113 safe auto-fixes (`--fix`, never `--unsafe-fixes`) · 20 by
> hand.
>
> **A note on the 14 `F841`s**, because they are not cosmetic: the unused bindings include
> `tx_receipt = build_and_send_tx(...)`, which *submits a transaction*, and
> `ref_gi = validate_gi_ET_curr_GI(...)`, which is a guard. Ruff classifies all 14 fixes as unsafe for
> exactly that reason. Each was classified by hand — effectful calls kept as bare expressions, bindings
> dropped; nothing deleted without establishing the call was unnecessary. Targeted tests for the
> affected validation and transaction paths are in the verification notes.
>
> **The rule selection is deliberately the narrow floor.** If anyone wants `I` (import sorting) or
> more, that is a fair argument and a three-character diff — raise it here.
>
> **`forge lint` stays advisory.** `forge_lint_gate.py` fails on any warning or error, so promotion
> needs a clean pinned-Forge run — which means both the `unsafe-typecast` cleanup (just work, no
> decision) and the `block.timestamp` findings in `src/DinValidatorStake.sol` (an open security
> decision: #<N> / BL-25). Phase 1 plan §3.3 step 5 decoupled the two promotions precisely so nobody
> would be tempted to close a security question quickly to turn a light green. The Solidity cleanup is
> its own PR and is not blocked by #<N>; only the final `continue-on-error` removal is.
>
> Worth noting the Solidity surface drifts while that check is passive: `bytes32("…")` literals in
> `test/` have gone from 17 occurrences (7 distinct) to 33 on 32 lines (14 distinct) since August.

---

## 7. What this does not do

- **PR 4, `forge fmt`** — now planned in `ci-next-04-forge-fmt-plan.md`. Independent; lands either
  side of this.
- **The Solidity lint cleanup** (`unsafe-typecast` et al.) — its own PR, unblocked, see §3.3.
- **Promote `forge lint`** — needs both prerequisites in §3.1.
- **Fix the 4 broken links in `Developer/`** (`ROADMAP.md` 119, 125, 126, 173 — `../design/` should be
  `design/`). Measured: 230 links checked there, 4 broken. The doc-link step only covers
  `Documentation/` today. Extending it plus the fixes is its own small PR — archived plan §7.
