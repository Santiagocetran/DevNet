# CI next steps, 5 of 5 — record `develop` pushes and complete the quality gates

**Base:** `develop` on `InfiniteZeroFoundation/DevNet` @ `b9411cf` (2026-09-24); public branch and Actions metadata checked the same day. `Plans/` itself is the separate `plans` worktree.
**Branch:** `ci/develop-push-observability`, cut from current upstream `develop` for the first PR. Later PRs use separate branches as described below.
**Origin:** [CI/CD proposal #74](https://github.com/InfiniteZeroFoundation/DevNet/discussions/74), merged [#103](https://github.com/InfiniteZeroFoundation/DevNet/pull/103) and [#118](https://github.com/InfiniteZeroFoundation/DevNet/pull/118), and the 2026-09-24 decision to preserve Umer's local merge/push workflow while recording CI on every landed `develop` revision.
**Status:** rev 1 — implementation order and acceptance criteria; no workflow changes made by this plan.

## 1. Decision and current state

The first two Phase 1 PRs shipped. `.github/workflows/ci.yml` runs on `pull_request` to `develop` only. Its Solidity, Python and Docs jobs feed one `CI OK` job. `forge lint` and `ruff` are advisory. The public Actions API showed 14 workflow runs, the latest on 2026-09-12, although `develop` had 25 later first-parent commits at this base and [#149](https://github.com/InfiniteZeroFoundation/DevNet/pull/149) merged into `develop` on 2026-09-22. The public branch API reports `develop` protected with required `CI OK`, enforced for `non_admins`.

**Preserve that enforcement policy.** Umer merges PRs locally and pushes the merge commits; the administrator bypass is intentional. This plan does not propose enabling “Do not allow bypassing,” changing his merge method, or claiming that a failing CI run prevents his push. A PR check remains a pre-merge signal; the new `push` run is a *post-landing detection and record* on the exact `develop` commit. Someone must act on a red push run; CI cannot retroactively reject it.

Success for the first PR means:

1. A PR targeting `develop` still gets one set of jobs and a `CI OK` result. A failed job makes `CI OK` fail; the existing branch rule continues to apply to non-admin merges.
2. A push to `develop`, including Umer's local merge commit, starts the same jobs against the pushed commit and records `CI OK` on that SHA.
3. PR and push runs never cancel one another. Rapid successive pushes to `develop` each complete a run for their pushed head SHA. A batch push containing multiple commits tests its final SHA; GitHub does not emit a separate push event for every commit in that batch.
4. A red post-merge run is triaged against the exact SHA before further promotion. The responsible maintainer records whether the failure is a regression or runner/tooling issue and pushes the fix through the usual workflow.

## 2. First PR — `develop` push coverage

### 2.1 Minimal workflow change

Change only `.github/workflows/ci.yml`:

```yaml
on:
  pull_request:
    branches: [develop]
  push:
    branches: [develop]

concurrency:
  group: ci-${{ github.event_name }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

The event name separates PR runs from push runs. The PR number keeps superseded updates to the same PR cancellable. On push, the absent PR number falls back to `refs/heads/develop`; conditional cancellation lets each push run finish even if the next push starts before it. This meets the request for a result on each pushed head SHA without multiplying PR runs. All jobs are already event-independent: checkout defaults to the event's revision, and `CI OK` reads `needs.*.result`. Keep the current read-only `contents` permission, action SHA pins, Foundry/Python pins, and all three existing jobs. Recheck GitHub Actions expression support with `actionlint` and a live run before merge.

### 2.2 Verification without disrupting `develop`

1. Before editing, record the current public workflow run count/latest run, public `develop` SHA, and current `CI OK` branch setting. Do not change protection.
2. Edit the YAML on a feature branch cut from fresh upstream `develop`. Validate YAML and Actions expressions with `actionlint` (install it only if absent); inspect the diff to confirm trigger and concurrency are the only behavior changes.
3. Open a PR targeting `develop`. Confirm Solidity, Python, Docs and `CI OK` appear and complete. No deliberate failing commit is needed on this implementation PR. Existing failed runs already demonstrate that `CI OK` propagates failures; if a new failure test is desired, use a disposable PR and close it afterward.
4. After Umer merges/pushes by his normal method, inspect the Actions run for the exact new `develop` SHA. Confirm `event=push`, all jobs ran, and `CI OK` reflects their results. This post-merge check is mandatory because a PR run alone cannot verify the new trigger.
5. If another `develop` push arrives before the first run finishes, confirm both push runs complete under conditional cancellation. If one is cancelled, fix the concurrency expression before considering the PR complete.
6. Record the outcome in the PR description or a follow-up comment: PR run URL, push run URL, head SHA, and any red job. The status should be investigated, not hidden by changing the required check.

**PR title:** `ci: run existing checks on every develop push`

**Rollback:** revert only the trigger/concurrency diff if push volume or runner limits become problematic. Existing PR checks continue to work. Do not weaken `CI OK` or branch protection as a rollback.

## 3. Complete Phase 1 quality gates in separate PRs

These plans already contain code-level steps and verification. Refresh their measurements against the then-current `develop` before implementing; their `87f6d19` baseline predates this plan.

| Order | PR / decision | Existing plan | Completion criterion |
|---|---|---|---|
| 2 | Configure narrow Ruff `E`/`F` rules, clear the baseline, remove `continue-on-error` from Ruff | [`ci-next-02-lint-promotion-plan.md`](ci-next-02-lint-promotion-plan.md) | Pinned Ruff exits 0; Python and `CI OK` go red on a real lint regression; Python test behavior is preserved. File the timestamp tracking item first for its cross-reference. |
| 3 | Format the Foundry tree and add blocking `forge fmt --check` | [`ci-next-04-forge-fmt-plan.md`](ci-next-04-forge-fmt-plan.md) | Formatter is idempotent; contract tests and compiled output remain equivalent; CI rejects an unformatted change. Can run alongside PR 2, then rebase. |
| 4 | Review the Solidity `block.timestamp` security finding | [`ci-next-03-timestamp-escalation-plan.md`](ci-next-03-timestamp-escalation-plan.md) | A Solidity reviewer records accept-with-rationale or fix, including short unbonding/jail windows on Optimism; no blanket suppression to make CI green. |
| 5 | Clear current `forge lint` warnings, then promote the gate | `ci-next-02` §3 and the archived Phase 1 plan §3.3 | Pinned Forge's JSON gate reports zero warning/error diagnostics, then `continue-on-error` is removed. `Solidity` and `CI OK` fail on a new diagnostic or parser/schema failure. Do the mechanical `unsafe-typecast` cleanup separately from the security decision. |

The Ruff and format work are independent of the new push trigger, but landing the trigger first yields a `develop`-SHA result for each later merge. The Forge lint promotion must wait for both the warning cleanup and the timestamp decision. Do not couple those into a broad formatting PR.

## 4. Small completeness PR — broaden the document check

The current Docs job checks `Documentation/` only. Running its existing script against `Documentation Developer` at this base checked 391 inline relative links and found four broken references in `Developer/ROADMAP.md` (lines 119, 125, 126 and 173); the `Documentation/`-only run checked 155 and passed. The helper itself documents syntax it cannot check, including reference-style links and fragment validity.

In a separate small PR, correct those four relative paths and change the Docs step to:

```yaml
python .github/scripts/check_doc_links.py Documentation Developer
```

Verify the combined command returns zero broken links, retain tests for the helper, and state its limited Markdown coverage in the PR. Expanding to still more roots or checking anchors should be a measured follow-up, not a claim this step validates every documentation link.

## 5. Phase 2 — scheduled integration, built in two increments

The excluded `tests/dincli/` suite needs a local chain, IPFS and Docker. Keep it off the fast PR gate initially. The test harness can start Hardhat/Anvil and IPFS, but Docker must be running externally, and the suite has sequential state-dependent cases. A passing Foundry/Hardhat unit run does not cover that interaction.

**Increment A: reproducible manual runner.** Document one command that provisions pinned versions of Node, Foundry, IPFS and Python dependencies, starts Docker, runs `pytest tests/dincli/ -m integration -v -x`, captures logs/artifacts, and tears down local processes on failure. Run it on a disposable runner or isolated container environment; never point it at the live devnet or use real wallet keys. Split or label tests that require remote services before scheduling them. Record runtime, disk use, failure modes and a passing baseline.

**Increment B: scheduled workflow.** GitHub schedules workflows from the repository's **default branch (`main`)**. A schedule added only to the `develop` copy of `.github/workflows/` will not run. Put the scheduled workflow on `main`, explicitly check out the `develop` ref to test the development code, and also provide `workflow_dispatch` for a manual dry run. Use read-only permissions and no network secrets. Upload bounded diagnostic artifacts on failure. Start informational while the runner is stabilized; make it an operational gate only after it is reliable and there is a clear owner for failures. Do not add it to `CI OK` while it remains scheduled-only, or required PR checks could wait for a job that never reports.

**Acceptance:** at least two scheduled runs on distinct days execute the intended `develop` SHA, provision all services from a clean runner, and produce a useful failure artifact. A red run has a documented triage owner and does not silently persist for weeks. Estimate runner minutes before increasing frequency.

## 6. Later coverage and maintenance

- **Dependency pin upkeep:** [`ci-next-01-dependabot-plan.md`](ci-next-01-dependabot-plan.md) is already detailed. Its config belongs on default-branch `main`, with version-update PRs targeting `develop`. Handle its documented security-update-to-`main` asymmetry before trusting those PRs to CI.
- **`main` promotion:** design a separate `develop` → `main` verification/promotion policy when releases require one. The current workflow intentionally has no `main` trigger; adding one as a side effect of the push PR would change Phase 1's scope without specifying the release path.
- **Deeper Solidity assurance:** after the fast gate is stable, add bounded fuzz/invariant jobs, static analysis and gas regression against a measured baseline. Each needs a failure policy and owner; `forge test` already exercises existing tests, so repeating it under another name adds little.
- **Runner/tool drift:** review pinned action, Foundry, Python and Ruff versions through explicit dependency PRs. Re-run lint baselines when upgrading Forge or Ruff because their diagnostics are part of the gate.

## 7. Delivery order and stop conditions

1. **Now:** PR for the `develop` push trigger and event-aware concurrency (§2). Do not adjust administrator bypass. Confirm the first real push run.
2. **Next:** the existing Ruff plan and `forge fmt` plan as separate reviewable PRs (§3); the docs-link expansion can land independently (§4).
3. **Security decision:** file and resolve the timestamp item, clear all Forge lint warnings, then make Forge lint blocking (§3).
4. **After fast CI is dependable:** manual integration runner, then default-branch scheduled workflow (§5). Dependabot and `main` promotion can proceed as separate tracks (§6).

Stop a promotion if its baseline is red on fresh `develop`, if a check can pass while selecting no tests, if a linter's rules/version differ from the plan's measured rules, or if a new required job does not report on the PR event. Fix the underlying problem and re-run the acceptance test; do not turn the check advisory merely to obtain a green badge.
