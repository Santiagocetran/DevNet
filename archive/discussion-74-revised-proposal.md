# Proposal: CI/CD Phase 1 — automated checks on every PR to `develop`

*Revised after actually running every proposed check against `develop`. Findings and adjustments are in "What we learned by testing it" below.*

## Why this matters

DevNet is open source and takes contributions continuously. Right now every check is manual and documented only in prose (`CLAUDE.md`), which means:

- **Contributors can't self-verify.** Someone opening their first PR has no way to know they broke a Solidity test until a maintainer notices.
- **Regressions surface at review time**, not at push time — the most expensive possible moment, paid in maintainer attention.
- **Reviewers spend time on things a machine should catch**, instead of on design and correctness.
- **"It works on my machine" is currently unfalsifiable.** Our checks pass locally in part because of tooling that happens to be installed on a particular laptop. CI is the only thing that makes "this works" a shared fact rather than a personal one.

The good news: **the checks already exist and they are fast.** Measured on `develop` today — 162 Solidity tests in ~7s, 32 Hardhat tests in ~3s, 259 Python tests in ~30s. The whole gate is roughly a minute of compute per PR. We are not proposing new infrastructure; we are proposing to stop running the existing tests by hand.

This proposal covers **Phase 1 only**: one workflow that runs when a PR is opened or updated against `develop`. Heavier work is deliberately deferred (see *Out of scope*).

## Phase 1 checks

Every check below is something a contributor is already expected to run locally.

| Check | What it protects |
|---|---|
| Foundry build + test | The contracts compile and all 162 tests pass — including the proxy storage-layout safety check, which is cheap to run and expensive to skip |
| Hardhat build + test | The secondary toolchain and its upgrade tests stay working |
| Python unit tests | `dincli` behaves, using the fast suite only (the live-chain integration suite is excluded — see *Out of scope*) |
| Doc-link check | Cross-references in `Documentation/` don't rot as the doc tree gets reorganized |
| Solidity lint *(advisory)* | Surfaces Solidity smells; not blocking yet, see below |
| Python lint *(advisory)* | Enforces the PEP 8 standard `CONTRIBUTING.md` already claims; not blocking yet, see below |

## What we learned by testing it

We ran all of these against `develop` before proposing them. Three things worth reporting:

**1. Three setup steps are non-obvious, and skipping any one makes CI fail for reasons unrelated to the contributor's code.** The Solidity dependencies are git submodules; one test suite needs a Node package installed first (without it, it fails intermittently); and the Python tests need PyTorch, which isn't declared as a dependency anywhere. They're now explicit prerequisites rather than surprises — and that last one is telling: our Python tests pass locally today only because PyTorch happens to be installed globally on one contributor's machine. Exactly the class of problem CI exists to expose.

**2. Two of the checks aren't ready to block merges yet, so they go in as advisory.**
- Solidity lint reports 21 existing findings, and as currently configured it *cannot actually fail* — it would be a check that always passes, which is worse than no check because it manufactures false confidence.
- Python lint reports **593 findings** across the codebase. That's a real cleanup effort, not a footnote, and it deserves its own PR rather than being smuggled in behind a workflow.

Both are valuable. Both should land as informational now and be promoted to blocking once the cleanup lands. It also found a genuine latent bug (stray invalid characters in `dincli/cli/system.py`) — evidence the linter earns its keep.

**3. One check was dropped as redundant.** A separate upgrade-validation job is unnecessary — the main Solidity test run already covers it.

The doc-link check, for reference, finds exactly **1 broken link out of 155** today (`Documentation/README.md` → `technical/ARCHITECTURE.md`), which we'd fix in the same PR.

## Recommendation on the trial-period question

Rather than running everything informationally for a while, **split by readiness**:

- **Required from day one:** Foundry, Hardhat, Python tests, doc links. These are green today. Making them advisory would just teach contributors that CI is noise.
- **Advisory until cleaned up:** the two lint checks. Making them required today would block every PR on 593 pre-existing findings and teach contributors to fight CI.

The principle either way: a gate is only worth having if passing it means something.

## Three details worth agreeing on now

- **Make one summary check the required one.** If individual jobs are required *and* skipped on unrelated PRs, a docs-only PR waits forever for checks that never run.
- **No secrets needed.** Confirmed: nothing here uses an RPC endpoint or API key, which keeps PRs from forks safe by default.
- **Two companion fixes** belong in the same PR: `.gitignore` doesn't cover the artifacts CI will generate, and `CLAUDE.md` has drifted from the real Python version requirement.

## Out of scope (future discussion)

- The `tests/dincli/` end-to-end suite — real value, but needs Docker, IPFS, and a running chain. Belongs on a nightly schedule, not a PR gate.
- Fuzz/invariant tests, Slither/Aderyn static analysis, gas-snapshot regression. Static analysis would repeat the lint problem at higher volume — worth doing deliberately, later.
- A stricter pre-merge gate via merge queue.
- Any `develop` → `main` promotion or deployment automation. The project is devnet-only; Phase 1 protects `develop` and nothing else.

## Open question

Any objection to adding a narrow `ruff` config? To be clear about scope: narrow means an explicit small rule set, not the linter's defaults, plus a cleanup PR landing before the check goes blocking. Roughly 85% of the current findings are auto-fixable.

cc @umermjd11 @robertocarlous @abrahamnash
