# CI next steps, 4 of 4 — `forge fmt`, as its own PR

**Base:** `develop` on `InfiniteZeroFoundation/DevNet` @ `87f6d19`
**Branch:** `ci/phase1-forge-fmt`, cut from `develop`
**Origin:** `Plans/archive/ci-cd-phase1-plan.md` §3.4 — "PR 4 of 4" of the Phase 1 series. Independent
of PR 3; needs only PR 2 (#118, merged).
**Status:** rev 2 — corrected the compiled-output verification after the 2026-09-24 Astra audit.
This plan exists because PR 4 was carried in the archived Phase 1 plan and had no successor:
`ci-next-02` covers PR 3 and merely *mentioned* that PR 4 was unopened. **Every file-count estimate
below is unmeasured** — `forge` was not installed in the environment this was written in. The archived
plan's measurement (§3.4, Aug 2026) was `forge fmt --check` exiting 1 across **20 files**.
Re-measure before opening (§3 step 1).

> **Rev 2 changelog (2026-09-24, Astra audit).** The rev 1 `forge build --sizes` check was described as
> evidence of semantic equivalence. Equal sizes can hide changed code, while a whitespace-only change
> can change Solidity's embedded metadata and raw bytecode hash. §3 now requires a source-diff review,
> unchanged ABI/storage layout, and a runtime-bytecode comparison that accounts for metadata and
> link/immutable references. A size table remains a diagnostic, not proof.

---

## 1. Why this is a separate PR, not a commit inside PR 3

Archived plan §3.4 gives two reasons and both still hold:

1. **A mechanical reformat landing beside a semantic cleanup makes the semantic half unreviewable.**
   PR 3 (`ci-next-02`) touches many of the same files by hand — including 14 `F841` sites where the
   distinction between "dropped a binding" and "deleted a transaction" is the entire review. Burying
   that in a 20-file whitespace diff is how a real change gets waved through.
2. **If the reformat needs reverting, it should not take the cleanup with it.**

PR 3 and PR 4 are order-independent; whichever lands second absorbs a trivial rebase.

---

## 2. Scope

Two commits, deliberately in this order:

1. **The reformat.** `forge fmt` across `foundry/`. Zero semantic change.
2. **The gate.** Add a `forge fmt --check` step to the `solidity` job in `.github/workflows/ci.yml`.

Splitting them means a reviewer can `git show` the second commit in isolation and see the whole
functional change in four lines.

### 2.1 The step

Placed after `forge build` and before `forge test` — formatting is the cheapest possible check, and
failing early on it saves a runner from compiling and testing a tree nobody will merge:

```yaml
      - name: forge fmt --check
        working-directory: foundry
        run: forge fmt --check
```

**Blocking from the start, with no advisory period.** This is deliberately different from how
`ci.yml` treats `forge lint` and `ruff`, and the difference is justified: the archived plan's advisory
period (§2.7) existed because those backlogs could not be cleared inside the workflow PR. This one is
cleared *by commit 1 of this very PR*, so there is no backlog left to be advisory about. A check that
is green the moment it is introduced can block immediately.

### 2.2 What `forge fmt` reformats

Per the archived plan: bare `uint` → `uint256` and similar. The config lives in `foundry.toml`; there
is no `[fmt]` section there today, so `forge fmt` applies its defaults. **Decide this explicitly**
(§5): accepting the defaults is fine and is the recommendation, but it should be a choice someone made
rather than something that happened.

### 2.3 Scope boundary — `hardhat/`

`forge fmt` formats the Foundry tree. `hardhat/` has its own `.sol` files and is the secondary
toolchain (CLAUDE.md). **Out of scope.** Do not point `forge fmt` at it; if Hardhat-side formatting is
wanted, that is Prettier + `prettier-plugin-solidity` and a different PR.

---

## 3. Verification

1. **Measure first, before formatting anything:**
   ```bash
   cd foundry && forge fmt --check
   ```
   Record the file count and exit status. The archived plan measured 20 files in August; it will have
   drifted. This number goes in the PR body.
2. **Reformat, then prove it is semantically inert.** This is the one thing that actually matters in
   this PR:
   ```bash
   forge build
   forge test          # expect: identical pass count to the pre-format run
   ```
   Capture the pre-format `forge test` count first so "identical" is checkable rather than asserted.
3. **Check the source and compiled interface under identical settings.** Use isolated pre-format and
   post-format worktrees with the same pinned Forge/solc versions, submodule commits, npm lockfiles and
   `foundry.toml`. Review the complete source diff for lexical/whitespace-only changes. Compare each
   changed contract's ABI and normalized storage layout. Compare executable deployed runtime bytecode
   after decoding/removing compiler metadata and accounting for link and immutable references; do not
   strip a guessed fixed number of trailing bytes. Investigate any remaining difference before calling
   the format semantically inert. A `forge build --sizes` table can help diagnose a difference, but
   **equal sizes are not an equivalence test**. Raw bytecode hashes may change solely because Solidity
   embeds source-dependent metadata.
4. **Idempotence.** Run `forge fmt` a second time; it must produce no diff. If it does, the formatter
   and the config disagree and the gate will flap.
5. **The gate passes on the formatted tree** and fails on an unformatted one — test the failure on a
   **disposable branch** (introduce bad spacing, confirm `Solidity` and `CI OK` both go red, close it).
   Do not push a deliberate break to the implementation PR.
6. **PR 3 rebases cleanly on top**, or vice versa, whichever lands second.

---

## 4. PR body outline

> **Title:** `ci: forge fmt the foundry tree and gate on it (CI/CD Phase 1, PR 4 of 4)`
>
> `forge fmt --check` currently exits 1 across N files (bare `uint` vs `uint256` and similar). Taking
> the debt now is right — it only grows — and it is the last piece of the Phase 1 series from
> discussion #74.
>
> **Two commits:** the mechanical reformat, then the four-line workflow step. Reviewing the second in
> isolation shows the entire functional change.
>
> **Deliberately separate from PR 3** (the ruff cleanup): a mechanical reformat landing beside a
> semantic cleanup makes the semantic half unreviewable, and PR 3 has 14 hand-classified `F841` fixes
> that need actual reading. Order-independent; whichever lands second rebases trivially.
>
> **Blocking immediately, no advisory period** — unlike `forge lint` and `ruff`, this backlog is
> cleared by commit 1 of this same PR, so there is nothing left to be advisory about.
>
> **Semantic inertness:** the complete source diff is formatting-only; tests pass with the same count;
> ABI and normalized storage layout are unchanged; executable deployed runtime bytecode matches after
> accounting for metadata and link/immutable references. `hardhat/` is untouched — different
> toolchain, different formatter.

---

## 5. Decisions

1. **Accept `forge fmt`'s defaults, or add a `[fmt]` section to `foundry.toml`?** Recommend accepting
   the defaults — a project-specific formatting config is a standing tax paid by every contributor and
   this repo has no stated reason to want one. But record it as a decision in the PR body rather than
   letting the absence of a config pass unremarked. Low stakes; a reviewer's preference settles it.

---

## 6. Relationship to the rest of the series

| | Plan | Blocked by |
|---|---|---|
| PR 1 | merged as #103 | — |
| PR 2 | merged as #118 | — |
| PR 3 | `ci-next-02-lint-promotion-plan.md` | BL-25 + issue filed (for the cross-reference only) |
| **PR 4** | **this** | **nothing** |

With this plan written, the archived Phase 1 plan has **no remaining unclaimed scope** — every one of
its four PRs is either merged or has a live successor plan. See `ARCHIVE.md` §1.
