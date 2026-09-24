# CI next steps, 5 of 5 — record `develop` pushes and complete the quality gates

**Base:** `develop` on `InfiniteZeroFoundation/DevNet` @ `b9411cf` (2026-09-24); public branch and Actions metadata checked the same day. `Plans/` itself is the separate `plans` worktree.
**Branch:** `ci/develop-push-observability`, cut from current upstream `develop` for the first PR. Later PRs use separate branches as described below.
**Origin:** [CI/CD proposal #74](https://github.com/InfiniteZeroFoundation/DevNet/discussions/74), merged [#103](https://github.com/InfiniteZeroFoundation/DevNet/pull/103) and [#118](https://github.com/InfiniteZeroFoundation/DevNet/pull/118), and the 2026-09-24 decision to preserve Umer's local merge/push workflow while recording CI on every landed `develop` revision.
**Status:** rev 3 — final Astra audit corrections incorporated; the first PR is ready to implement against a refreshed `develop` head. No workflow changes made by this plan.

> **Rev 3 changelog (2026-09-24, final Astra audit).**
>
> - Add a non-bypass actor test that proves a failed `CI OK` actually blocks the protected PR merge route, while preserving Umer's administrator bypass (§2.2).
> - Make the integration runner generate its own local `.env` and deterministic dev keys. The current fixture copies an untracked developer `.env`; `.env.example` comments out the keys required by bootstrap (§5).
> - Require startup helpers to own and stop processes even when readiness fails before they return a handle. An outer fixture `try/finally` alone cannot clean up that case (§5).

> **Rev 2 changelog (2026-09-24, Astra audit).**
>
> - **BLOCKER:** the rev 1 push group used `github.ref`. GitHub keeps only one pending run in a concurrency group by default, so a third rapid push could replace the second even with `cancel-in-progress: false`. Use the unique `github.run_id` for pushes and verify three overlapping runs (§2).
> - Specify missing-run detection, skip-instruction policy, and who triages a red or absent run (§1–2).
> - Make the integration harness preserve failure logs, clean up after setup failures, initialize isolated IPFS, pin/record the worker environment, and reject unexpected test skips before scheduling (§5).
> - Record an immutable tested `develop` SHA in the default-branch scheduled workflow, separately from the event's `main` SHA (§5).
> - Tighten formatting equivalence and reconcile ordering with the older Dependabot plan (§3, §6–7; companion revisions in `ci-next-04` and `ci-next-01`).

## 1. Decision and current state

The first two Phase 1 PRs shipped. `.github/workflows/ci.yml` runs on `pull_request` to `develop` only. Its Solidity, Python and Docs jobs feed one `CI OK` job. `forge lint` and `ruff` are advisory. The public Actions API showed 14 workflow runs, the latest on 2026-09-12, although `develop` had 25 later first-parent commits at this base and [#149](https://github.com/InfiniteZeroFoundation/DevNet/pull/149) merged into `develop` on 2026-09-22. The public branch API reports `develop` protected with required `CI OK`, enforced for `non_admins`.

**Preserve that enforcement policy.** Umer merges PRs locally and pushes the merge commits; the administrator bypass is intentional. This plan does not propose enabling “Do not allow bypassing,” changing his merge method, or claiming that a failing CI run prevents his push. A PR check remains a pre-merge signal; the new `push` run is a *post-landing detection and record* on the exact `develop` commit. Someone must act on a red push run; CI cannot retroactively reject it.

Success for the first PR means:

1. A PR targeting `develop` still gets one set of jobs and a `CI OK` result. A failed job makes `CI OK` fail. The required-check rule blocks a **non-bypass** actor from merging that failed PR; Umer's administrator bypass remains intentional.
2. Each **normal** push to `develop`, including Umer's local merge commit, starts the same jobs against that push's head SHA and records `CI OK` there. A batch push containing multiple commits tests its final SHA; GitHub does not emit a separate event for each commit in that batch. GitHub's [skip instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs) can suppress a push workflow, so the team convention is to avoid them on `develop` and check for an absent run after every push.
3. PR and push runs never cancel one another. Rapid successive pushes each retain their own run; superseded updates to one PR may cancel one another.
4. The merging maintainer owns the first check of the pushed SHA and its run. Name a backup maintainer in the implementation PR. A red or missing run is investigated before the next promotion and within one working day; record the SHA, run URL or absence, cause, and fix/re-run outcome. This is detection and response, not a change to Umer's ability to push.

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
  group: ${{ github.workflow }}-${{ github.event_name }}-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

The workflow and event names separate this group from other workflows and from PR/push runs. The PR number keeps superseded updates to one PR cancellable. On push, the absent PR number falls back to the **unique run ID**, so no later push can replace a pending earlier run. This matters because [GitHub's default concurrency queue holds only one pending run per group](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency); `cancel-in-progress: false` alone would not retain every push. All jobs are already event-independent: checkout defaults to the event's revision, and `CI OK` reads `needs.*.result`. Keep the current read-only `contents` permission, action SHA pins, Foundry/Python pins, and all three existing jobs. Validate the expression with `actionlint` and live runs before merge.

### 2.2 Verification without disrupting `develop`

1. Before editing, record the current public workflow run count/latest run, public `develop` SHA, and current `CI OK` branch setting. Do not change protection.
2. Edit the YAML on a feature branch cut from fresh upstream `develop`. Validate YAML and Actions expressions with `actionlint` (install it only if absent); inspect the diff to confirm trigger and concurrency are the only behavior changes.
3. In a **disposable fork/test repository**, run three quick pushes while the first is still running. Confirm all three push runs remain queued/running and complete, with distinct groups. Also update one PR twice to confirm the old PR run is cancelled, and overlap a PR and push to confirm they do not cancel each other. This synthetic test must not create artificial pushes or failing commits on Umer's `develop` branch.
4. In that disposable repository, configure required `CI OK` protection matching `develop` and use an account with write access but **no administrator/rules bypass**. Make a required job fail, confirm `CI OK` fails, and verify that actor cannot merge the PR. Fix the job and verify merge eligibility returns. A red workflow alone does not prove enforcement. Record the test actor's role and rule setting; if no suitable actor is available, mark this acceptance item **unverified** instead of claiming it passed. Do not change production branch protection or test Umer's bypass.
5. Open the real implementation PR targeting `develop`. Confirm Solidity, Python, Docs and `CI OK` appear and complete. Any fresh deliberate failure test belongs in the disposable test repository.
6. After Umer merges/pushes by his normal method, inspect the Actions run for the exact new `develop` SHA. Confirm `event=push`, all jobs ran, and `CI OK` reflects their results. This post-merge check is mandatory because a PR run alone cannot verify the new trigger.
7. Check that the pushed SHA has an Actions run at all. If missing, check for a skip instruction, disabled/held workflow, or event-delivery problem. Record the exact SHA as untested, fix the cause, and run that SHA manually in an isolated checkout if an equivalent dispatch path exists; a normal follow-up push tests its **new** SHA and does not retroactively cover the missed one. Do not treat the earlier PR run as proof for the landed SHA. Investigate a red run under the ownership/window in §1.
8. Record the outcome in the PR description or a follow-up note: PR run URL, push run URL, head SHA, and any red or missing job. Do not hide a failure by changing the required check.

**PR title:** `ci: run existing checks on every develop push`

**Rollback:** revert only the trigger/concurrency diff if push volume or runner limits become problematic. Existing PR checks continue to work. Do not weaken `CI OK` or branch protection as a rollback.

## 3. Complete Phase 1 quality gates in separate PRs

These plans already contain code-level steps and verification. Refresh their measurements against the then-current `develop` before implementing; their `87f6d19` baseline predates this plan.

| Order | PR / decision | Existing plan | Completion criterion |
|---|---|---|---|
| 2 | Configure narrow Ruff `E`/`F` rules, clear the baseline, remove `continue-on-error` from Ruff | [`ci-next-02-lint-promotion-plan.md`](ci-next-02-lint-promotion-plan.md) | Pinned Ruff exits 0; Python and `CI OK` go red on a real lint regression; Python test behavior is preserved. File the timestamp tracking item first for its cross-reference. |
| 3 | Format the Foundry tree and add blocking `forge fmt --check` | [`ci-next-04-forge-fmt-plan.md`](ci-next-04-forge-fmt-plan.md) | Formatter is idempotent; tests pass; ABI, storage layout and executable runtime output are compared under identical tool settings with metadata handled explicitly. Equal bytecode sizes alone are insufficient. CI rejects an unformatted change. Can run alongside PR 2, then rebase. |
| 4 | Review the Solidity `block.timestamp` security finding | [`ci-next-03-timestamp-escalation-plan.md`](ci-next-03-timestamp-escalation-plan.md) | A Solidity reviewer records accept-with-rationale or fix, including short unbonding/jail windows on Optimism; no blanket suppression to make CI green. |
| 5 | Clear current `forge lint` warnings, then promote the gate | `ci-next-02` §3 and the archived Phase 1 plan §3.3 | Pinned Forge's JSON gate reports zero warning/error diagnostics, then `continue-on-error` is removed. `Solidity` and `CI OK` fail on a new diagnostic or parser/schema failure. Do the mechanical `unsafe-typecast` cleanup separately from the security decision. |

File the timestamp tracking item **before** the Ruff PR so its cross-reference is real; the security review and resolution can proceed independently. The Ruff and format work are independent of the new push trigger, but landing the trigger first yields a `develop`-SHA result for each later merge. The Forge lint promotion must wait for both the warning cleanup and the timestamp decision. Do not couple those into a broad formatting PR.

## 4. Small completeness PR — broaden the document check

The current Docs job checks `Documentation/` only. Running its existing script against `Documentation Developer` at this base checked 391 inline relative links and found four broken references in `Developer/ROADMAP.md` (lines 119, 125, 126 and 173); the `Documentation/`-only run checked 155 and passed. The helper itself documents syntax it cannot check, including reference-style links and fragment validity.

In a separate small PR, correct those four relative paths and change the Docs step to:

```yaml
python .github/scripts/check_doc_links.py Documentation Developer
```

Verify the combined command returns zero broken links, retain tests for the helper, and state its limited Markdown coverage in the PR. Expanding to still more roots or checking anchors should be a measured follow-up, not a claim this step validates every documentation link.

## 5. Phase 2 — scheduled integration, built in two increments

The excluded `tests/dincli/` suite needs a local chain, IPFS and Docker. Keep it off the fast PR gate initially. The test harness can start Hardhat/Anvil and IPFS, but Docker must be running externally, and the suite has sequential state-dependent cases. A passing Foundry/Hardhat unit run does not cover that interaction.

**Increment A: reproducible manual runner and harness repair.** Implement the runner before a scheduled workflow:

1. On an isolated runner, recursively check out Foundry submodules; install both `foundry/` and `hardhat/` npm trees with `npm ci`; provision pinned Node, Forge, IPFS and Python dependencies; and start Docker. Pin or record the worker image built from `dincli/docker/worker/Dockerfile` (`python:3.12-slim` currently floats). Match the host packages mounted into that container to its Python 3.12 ABI.
2. Create a task-specific `IPFS_PATH`, run `ipfs init`, start the daemon, and make the readiness probe fail promptly if it never answers. Today `conftest.py` starts `ipfs daemon` without initialization and only warns after a failed probe (`_ensure_ipfs_running`).
3. Generate an isolated local-test `.env` from the tracked `.env.example` plus dev keys derived from the **public test mnemonic already used by `foundry/anvil.sh`**. Generate keys for the account indexes the selected suite uses: 0–1 for bootstrap, clients 2–10, aggregators 11–22 and auditors 50–58. The `workdir` fixture currently copies `DEVNET_ROOT/.env` unconditionally, but that file is untracked and the example's `ETH_PRIVATE_KEY_0/1` lines are commented out. Replace that prerequisite with generation of the test file in the isolated workdir, or have the runner create a temporary root `.env` and prove it is removed afterward. Check the derived addresses against the local chain. Never commit the generated file or upload it with diagnostics. Acceptance starts from a checkout with **no existing `.env`, wallet/config directories or injected private keys**.
4. Set `PYDIN_PYTHON`, `TORCHENV_PYTHON`, `TORCHENV_SITE_PACKAGES`, `NPX_BIN`, `FORGE_BIN`, `IPFS_BIN`, `DIN_TEST_TMPDIR` and `PLATFORM_DEPLOY_TOOLCHAIN` explicitly. `constants.py` already permits overrides; this prevents a runner from accidentally using conventional developer paths. Start with `PLATFORM_DEPLOY_TOOLCHAIN=foundry`, the harness default. A separate run can later assess Hardhat deployment parity.
5. Repair `tests/dincli/conftest.py` so process teardown runs even if compile/startup fails before its `yield` (`try/finally` around fixture provisioning), **and** each startup helper owns its process immediately after `Popen`. Today Anvil/Hardhat helpers can raise on readiness timeout before returning a handle, leaving the outer fixture's handle as `None`; a fatal IPFS readiness check would have the same risk. On helper failure, terminate and wait for the spawned process or its process group, close its log handle, and verify its listener is gone. Separate uploadable results/service logs from disposable `DIN_TEMP` state: current teardown deletes all of `DIN_TEMP`, including `results/`. Preserve logs through upload, then remove disposable state. Test controlled compile failure, **post-spawn/pre-return readiness failure**, and test-body failure; confirm logs survive and no service process or port remains in each case.
6. Run `pytest tests/dincli/ -m integration -v -x` and record collected, passed, failed and skipped counts plus which critical stages executed. The artifact fixtures can skip whole modules if compiled artifacts are missing; an unexpectedly skipped deploy, registration or GI stage is a failed integration run, not a green result. Split or label tests that require remote services before scheduling. Capture runtime, disk use and a passing clean-run baseline.

Use a disposable runner or isolated container environment and local dev accounts; do not point the suite at the live devnet or use real wallet keys.

**Increment B: scheduled workflow.** [GitHub schedules workflows from the repository's default branch](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), which is `main`. A schedule added only to `develop` will not run. Put the workflow on `main`. At job start, resolve the current `develop` SHA once, explicitly check out **that SHA**, and propagate it to every job. Record both the schedule event's `github.sha` (`main` workflow revision) and the checked-out `develop` SHA in the run summary and artifacts; checkout does not change event metadata. Provide `workflow_dispatch` with an optional, validated 40-hex SHA input so a failed run can be replayed against the same code later; pass the input as action data rather than interpolating it into shell commands. Use read-only permissions and no network secrets. Upload bounded diagnostics on failure. Start informational while the runner is stabilized; make it an operational gate only after reliability and triage ownership are established. A scheduled-only check cannot supply `CI OK` for each PR, so keep it outside that required result.

**Acceptance:** the manual runner starts with no developer `.env` or private keys, generates only deterministic local dev accounts, survives controlled provisioning/readiness/test failures with logs retained and spawned processes stopped, and executes every critical stage without unexpected skips. At least two scheduled runs on distinct days execute and record their immutable `develop` SHA, provision all services from a clean runner, and produce a useful failure artifact when forced to fail. A red run has a named primary and backup triage owner with a response window. Estimate runner minutes before increasing frequency.

## 6. Later coverage and maintenance

- **Dependency pin upkeep:** [`ci-next-01-dependabot-plan.md`](ci-next-01-dependabot-plan.md) is already detailed. It originally recommended Dependabot first; the 2026-09-24 decision puts push coverage first because recent `develop` revisions have no recorded run. Dependabot remains independent and can follow without waiting for lint or integration. Its config belongs on default-branch `main`, with version-update PRs targeting `develop`. Handle its documented security-update-to-`main` asymmetry before trusting those PRs to CI.
- **`main` promotion:** design a separate `develop` → `main` verification/promotion policy when releases require one. The current workflow intentionally has no `main` trigger; adding one as a side effect of the push PR would change Phase 1's scope without specifying the release path.
- **Deeper Solidity assurance:** after the fast gate is stable, add bounded fuzz/invariant jobs, static analysis and gas regression against a measured baseline. Each needs a failure policy and owner; `forge test` already exercises existing tests, so repeating it under another name adds little.
- **Runner/tool drift:** review pinned action, Foundry, Python and Ruff versions through explicit dependency PRs. Re-run lint baselines when upgrading Forge or Ruff because their diagnostics are part of the gate.

## 7. Delivery order and stop conditions

1. **Now:** PR for the `develop` push trigger and unique push-run concurrency (§2). Do not adjust administrator bypass. Prove the concurrency expression in a disposable fork, then confirm the first real push run.
2. **File the timestamp tracking item early** so the Ruff PR has its real cross-reference. Its security resolution is independent of Ruff cleanup but required before Forge lint promotion (§3).
3. **Next:** the existing Ruff and `forge fmt` plans as separate reviewable PRs (§3); the docs-link expansion and Dependabot can land independently (§4, §6).
4. **Solidity lint:** clear all Forge lint warnings and resolve the timestamp decision, then make Forge lint blocking (§3).
5. **After fast CI is dependable:** repair and prove the manual integration runner, then add the default-branch scheduled workflow (§5). Design `main` promotion separately (§6).

Stop a promotion if its baseline is red on fresh `develop`, if a check can pass while selecting no tests **or skipping a critical integration stage**, if a linter's rules/version differ from the plan's measured rules, or if a new required job does not report on the PR event. Fix the underlying problem and re-run the acceptance test; do not turn the check advisory merely to obtain a green badge.
