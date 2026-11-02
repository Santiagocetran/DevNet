# PR #305: reconciliation after PR #261

**Base:** upstream `develop` at `cf80216` (PR #254 after #261), PR #305 at `2c1fa4c`.
**Branch:** `fix/pr305-post261`, isolated checkout `/tmp/devnet-pr305-reconcile`.
**Origin:** PR #305 / issue #224; user-requested Astra audit and implementation.
**Status:** rev 4 — P2 pairing fix implemented and independently rechecked by Astra; persistent IPFS publication and remote CI/reviews outstanding. Historical #254 metadata race remains unfixed.

> Rev 4 changelog — the independent Astra implementation audit reproduced both mixed official task generations: a guarded coordinator with an old auditor cannot start GIs; an old coordinator with a guarded auditor bypasses disable. Add a pure `taskProtocolVersion()` getter (version 1) to the guarded coordinator, require version 1 for four-argument auditors and unversioned legacy coordinators for legacy auditors, reject unknown versions, and preserve model-ID checks. Missing-code checks and all generation rejection precede constructor invocation, transactions, saved addresses and pairing. No new storage or changes to GI guard semantics. Regenerate bytecode/ABIs/CIDs and recheck the coordinator size budget.

> Rev 3 changelog — implementation and focused Astra recheck completed. The full Python suite and live CLI smoke pass. Full Foundry reports 526 passed / 1 inherited metadata-test failure; that failure passes alone and is consistent with competing process-wide environment overrides in #254. Local offline IPFS receipts prove integrity only; durable network publication and independent retrieval remain a release blocker. No remote PR changes are authorized by this record.

> Rev 2 changelog — Astra confirmed the core approach and identified missing current-Foundry deployment examples, incomplete getter error handling, ambiguous bootstrap publication scope, missing second-registry-read failure coverage, and an overly broad live CLI lifecycle test. These are corrected below. **Resolved merge blocker:** newly fetched develop includes PR #254 and created an additional BACK_LOG conflict; its completed BL-33 row is preserved. Artifact equality will run in Solidity CI after compilation. Plan files stay on the fork-only `plans` worktree and out of the implementation PR.

## Recommendation and verified baseline

Merge current upstream `develop` into the existing PR branch, preserve #305's constructor compatibility logic and #261's model-ID safety requirement, adapt the inherited tests, and refresh the reference artifacts together with their manifest CIDs. A textual conflict resolution alone is insufficient: it can leave failing tests and a reference deployment path that still deploys contracts without the new guard.

Inspected local Git objects matching the live GitHub PR metadata:

| Ref | Commit | Finding |
|---|---|---|
| `develop` / PR #261 merge | `d6f537bcbf7f03f453f9cea32e940bf7d6fa1065` | #261 merged on November 2; working tree was clean at analysis start |
| PR #261 head | `698c216ec03d60541a21e9fcc754b0032abb5398` | Foundry reference artifacts, manifest metadata/CIDs, deployment IDs and mismatch guard |
| PR #305 head | `2c1fa4c542fdcd7f53d53a4e0262c8e890b2a189` | Five commits including two develop merges; guard, CLI compatibility, error handling and backlog correction |
| Merge base | `74a845c9e7328e28fca95f1cdc6ff595bbea17ae` | Three-way inspection shows conflict markers only in `dincli/cli/modelownerd/deploy.py` |

GitHub reports #305 open and `mergeable: false`. Local `git merge-tree <base> <develop> <pr-head>` confirms the CLI conflict. The initial analysis left `develop` unchanged. Implementation uses the isolated branch above. A fresh fetch advanced upstream to `cf80216` (PR #254); its deployment verification and script changes must be retained. Merging that tip initially conflicted in both `deploy.py` and `Developer/BACK_LOG.md`; the resolved local merge is `1b09d10`.

Sources: [PR #261](https://github.com/InfiniteZeroFoundation/DevNet/pull/261), [PR #305](https://github.com/InfiniteZeroFoundation/DevNet/pull/305), [issue #224 decisions](https://github.com/InfiniteZeroFoundation/DevNet/issues/224#issuecomment-6406239550), and [issue #246 approval amendments](https://github.com/InfiniteZeroFoundation/DevNet/issues/246#issuecomment-6171486901).

## What needs reconciliation

### 1. Deployment conflict: preserve behavior from both branches

#261 requires `--model-id`, directly constructs the two-argument coordinator and three-argument auditor, and reads the selected coordinator's `modelId()` before deploying an auditor. #305 supports five explicit constructor signatures, including its new four-argument auditor. It also validates missing stake/registry configuration, validates uint256 IDs, and turns a coordinator-call revert into an actionable `BadParameter`.

Use #305's constructor dispatch as the final design. Taking #261's deployment code wholesale loses the registry constructor argument and cannot deploy the new auditor. Keeping two independent mismatch guards risks duplicate reads, inconsistent errors and applying a model-ID requirement to legacy contracts that expose no such getter.

The three-way output also leaves two `model_id` parameters in one tentative auditor signature if its hunks are combined mechanically. Resolve the complete function signature and control flow, then check syntax.

### 2. An inherited regression test will break after a naive resolution

`tests/test_task_auditor_model_id_guard.py`, introduced by #261, supplies a deployable `SimpleNamespace` with a `constructor` but no `abi`. #305's `_task_constructor_args` inspects `contract.abi` first. A stdlib-only reproduction using the actual helper AST and #261's fixture shape raises:

```text
AttributeError: 'types.SimpleNamespace' object has no attribute 'abi'
```

After fixing that fixture, the mismatch test still expects `typer.Exit(1)`, whereas #305 raises `typer.BadParameter`. Preserve the requirement tested by #261—reject an immutable ID mismatch before any transaction—while updating the fixture and exception expectation to the reconciled implementation.

This is an independently reproduced helper/fixture incompatibility, not a claim that pytest was run. The current `.venv` lacks pytest and the previous `/tmp/iz-ci-diagnostics-tests` environment is absent.

### 3. Reference artifacts would silently remain on the older contracts

Direct JSON inspection gives:

| Artifact | #261 cache and develop bundled ABI | #305 bundled ABI |
|---|---:|---:|
| Coordinator | 202 entries; `(address,uint256)` | 201 entries; same constructor |
| Auditor | 155 entries; `(address,address,uint256)` | 160 entries; `(address,address,uint256,address)` |

Both `cache_model_0/abis` files contain deployment bytecode. Their ABIs exactly equal the pre-#305 bundled ABIs. #305 does not modify these cache files or the manifest. Its compatibility helper will accept the older auditor artifact, so a reference deployment can succeed while deploying a pair without the guard. The coordinator bytecode also matters: changing only the auditor artifact would retain the old coordinator's direct pool check.

Refresh **both** reference artifacts from the reconciled build, not just their ABI arrays. Refresh the manifest CIDs in the same change. `context.py::_resolve_task_contract_artifact_path` resolves manifest-relative paths and calls `ensure_file_exists`; an old CID can restore the old artifact into a cache. Existing pinning/retrieval evidence from #261 proves availability of the old bytes only.

### 4. Several earlier review observations are already resolved or outdated

- Commit `dfc5bd2` already catches `ContractLogicError` from `modelId().call()` and preserves unrelated errors. Keep it; do not implement the old suggestion again.
- Commit `6970f5d` already marks BL-34 resolved, including the existing-deployment caveat. Keep that row while retaining develop's BL-25/BL-27 completion references to #261.
- Workflow extraction discussed in an earlier review is already on develop; it is absent from the current 32-file PR diff. Preserve current `ci.yml` and `full-gi.yml`, including `merge_group` and manual-only Full GI behavior.
- The recorded approval from `umeradl` is currently `DISMISSED`; the `robertocarlous` review is still `CHANGES_REQUESTED`, although its requested backlog correction is committed. A fresh review is necessary.
- Current [MAINTAINING §4.2](../Developer/MAINTAINING.md#42-review-depth) requires a peer plus a second sign-off from `umeradl`, `abrahamnash`, or their routed security reviewer for contract changes. Its mechanism section requires `umeradl`'s GitHub approval for this author's mechanism PR. It explicitly says Abraham's GitHub response is not something these PRs wait for. Apply those current rules instead of repeating the older review's mandatory-Abraham wording.

## Implementation sequence

### Step 1 — synchronize in an isolated checkout

1. Refresh upstream `develop` and the PR head; record their full SHAs and compare them with this baseline. Reassess if either changed.
2. Create an isolated worktree for `fix/model-disable-224`. Merge upstream `develop` into that branch, consistent with its existing history. Avoid rewriting its published history solely to resolve this overlap.
3. Resolve `deploy.py` deliberately; retain all unrelated develop changes. Inspect the final PR diff against upstream develop so already-merged CI work is not reintroduced.

### Step 2 — settle the CLI contract

Keep one `_task_constructor_args` implementation with exact type-signature matching:

| Role | Constructor types | Arguments | Preflight |
|---|---|---|---|
| Legacy coordinator | `address` | stake | stake configured |
| Current coordinator | `address,uint256` | stake, model ID | stake configured; valid uint256 ID |
| Legacy auditor | `address,address` | stake, coordinator | stake configured; no model-ID getter call |
| Previous Foundry auditor | `address,address,uint256` | stake, coordinator, model ID | valid ID; matching coordinator ID |
| Guarded auditor | `address,address,uint256,address` | stake, coordinator, model ID, registry | same ID check; canonical registry configured |

Keep `--model-id` optional at parser level for legacy support and mandatory for signatures that require it. Describe it as an anticipated registry ID: constructor IDs select stake floors; registration assigns the authoritative ID later. This PR does not solve issue #223's allocation race.

Use one minimal `modelId` ABI, one getter read and one mismatch check for ID-bearing auditors. Keep #261's explanation that the IDs are immutable and pairing is one-shot. Extend #305's narrow conversion to `(ContractLogicError, BadFunctionCallOutput)` around the getter call only, with exception chaining. The second exception covers empty/malformed getter output and addresses without code; do not wrap transport failures or contract-object creation errors indiscriminately. All preflight rejection must precede constructor invocation, transaction submission, environment writes and pairing.

Retain the deployment receipt handling, saved address keys and `setDINTaskAuditorContract` transaction. No alternate registry flag or automatic pairing retry is required.

### Step 3 — reconcile regression coverage

Adapt `tests/test_task_auditor_model_id_guard.py` to supply a three-argument auditor ABI and expect `BadParameter` on mismatch. Keep both original behavioral cases. Strengthen the matching case to assert exact constructor arguments and the deployment/pairing transactions; `len(sent) >= 1` alone does not prove correct wiring.

Keep #305's `tests/test_model_disable_deployment.py`, which already covers constructor signatures, missing/invalid IDs, registry requirements, both ID-bearing auditor shapes, mismatches, getter reverts, unrelated exceptions and the legacy path. Add getter tests for both error classes and both ID-bearing auditor shapes, with no side effects. Add command-level cases for missing stake and missing registry that assert zero deployment side effects, plus coordinator deployment assertions if not otherwise covered. Use keyword arguments in new command tests to avoid dependence on Python parameter order.

Add a focused artifact consistency check that compares each generated cache ABI and bytecode with its Foundry build output, and each bundled ABI with that same output. Add it to the Solidity CI job immediately after `forge build`; do not make the ordinary Python job depend on pre-existing Foundry artifacts. Preserve all current jobs and triggers. This catches a materially different deployment that ABI-only comparison misses.

### Step 4 — regenerate artifacts and publish matching content

Build with the repository's pinned Foundry version (`v1.7.1` in current CI), solc 0.8.28, Cancun, via-IR and optimizer enabled at 200 runs. Install the locked Foundry npm dependencies before running tests that invoke upgrades validation through FFI.

From the reconciled checkout root, use the existing export command for both contracts:

```bash
dincli system dump-abi --artifact foundry/out/DINTaskCoordinator.sol/DINTaskCoordinator.json --bytecode --output cache_model_0/abis
dincli system dump-abi --artifact foundry/out/DINTaskAuditor.sol/DINTaskAuditor.json --bytecode --output cache_model_0/abis
```

Regenerate `dincli/abis/DINTaskCoordinator.json` and `DINTaskAuditor.json` from the same outputs, preserving the bundled files' existing ABI-only convention. Validate content, not hard-coded entry counts.

Pin the exact final cache files through the configured IPFS provider. Record the returned CIDs and receipts, then update only the corresponding manifest artifact CIDs. Preserve #261's Foundry compilation metadata and manifest-relative artifact paths. Leave the existing Anvil address values unchanged: this is an artifact update, not a redeployment. Document that those example addresses do not establish that an existing deployed pair has the new behavior.

Publication scope is the checked-in `cache_model_0` artifacts and manifest. `cache-default-artifacts` independently reads `din_info.json`'s historical `default_manifest` and `default_abis` CIDs; this reconciliation does not publish or update that bootstrap configuration. Document this boundary and track bootstrap refresh separately. Do not claim all default bootstrap downloads now carry the guard.

Fetch both new CIDs through `ensure_file_exists` into an empty temporary cache with no CID-store shortcut. Compare retrieved bytes with the final committed files. Record provider, CID, byte size and hashes. Do not substitute locally computed CIDs for pinning/retrieval evidence, or commit new bytes under old CIDs. If artifact availability cannot be verified, report it as an unfinished acceptance item. Offline local pinning/retrieval proves content integrity but does not establish public availability: persistent network pinning and retrieval from an independent node are required before the new CIDs are merge-ready.

### Step 5 — reconcile documentation and scope

Preserve the current contract semantics:

- Both `startGI` overloads reach the view guard before score, GI or state mutation.
- Registry reverse lookup by auditor supplies the checked ID; constructor `modelId` remains the stake-floor parameter.
- Unregistered models, disabled models and failed registry reads cannot start a GI, even with a funded pool.
- In-flight work, slashing, settlement and claims continue. Reenable restores start eligibility.
- There is no GI abort, refund mechanism, registry upgrade or S6 behavior/storage change.

Update the executable deployment examples in `Documentation/public/workflows/model-workflow.md` and `Documentation/public/roles/model-owner.md` to use current Foundry outputs and matching `--model-id` values. Remove obsolete “dincli lags” caveats in the coordinator/auditor contract docs; distinguish supported legacy artifacts from guarded current contracts.

Retain BL-34's resolution and #261's BL-25/BL-27 completion; retain PR #254's completed BL-33 row. Update BL-31/BL-35 status text to acknowledge that #305 supplies their parked-S6 and non-refundable-fee documentation, rather than leaving “docs pending.” Preserve unrelated backlog rows and develop's S5 documentation correction.

Keep canonical-registry enforcement at registration/slasher authorization as a separately tracked follow-up, as agreed in the [review](https://github.com/InfiniteZeroFoundation/DevNet/pull/305#issuecomment-6522860877). An immutable address and `code.length` check do not establish canonicality. The follow-up should specify approval and slasher checks, legacy behavior, and bypass limits of CLI-only enforcement. Do not silently broaden this reconciliation into a registry upgrade.

## Validation and acceptance

Run the two deployment test modules first, then the complete non-integration Python suite. Run a clean Foundry build, the full Foundry suite and `.github/scripts/contract_size_gate.py` from `foundry/`. Add a real-registry test where `modelDisabled` fails after successful reverse lookup, checking unchanged score/GI/state for both overloads. Existing kill-switch tests must still cover atomic rejection, reenable, unregistered/failed registry reads, invalid wiring, caller restriction and in-flight completion. Historical “524 passed” and the earlier 1,189-byte coordinator margin are prior evidence, not current results; record fresh counts and sizes. The size gate requires at least 1,024 bytes of runtime margin.

Run the existing documentation checker and diff/syntax checks. Complete same-build ABI/bytecode parity and fresh IPFS retrieval checks. Have a reviewer verify immutable/storage implications: task pairs are non-upgradeable, the new registry reference is immutable, and the registry source change is NatSpec-only.

Exercise the actual reconciled CLI on a local Anvil chain with freshly built Foundry artifacts and isolated configuration:

| Case | Required result |
|---|---|
| Missing/out-of-range current model ID, missing stake/registry | Clear failure before any deployment or pairing transaction |
| Matching IDs, canonical registry | Both deployments succeed; getter values match; coordinator points to auditor |
| Mismatched IDs or incompatible coordinator getter | Clear preflight failure; no auditor deployment |
| Live CLI smoke scope | Constructor dispatch, pairing, exact getter values and rejected deployments consume no transaction nonce |
| Regenerated cache artifacts | Deploy and behave like direct Foundry artifacts |
| Supported legacy artifact pair | Still deploys; explicitly documented as lacking the new guard |

Use the real-registry Foundry lifecycle suite for enabled/disabled/unregistered funded starts, atomic failures and disable-during-GI completion/settlement/claims. A full training/aggregation reproduction through the CLI is not a new reconciliation deliverable.

The current Full GI harness selects **Hardhat task artifacts** via `tests/dincli/constants.py:ARTIFACT_BASE`; changing platform deployment toolchain does not change that selection. Its task deployment commands omit `--model-id`, which remains valid for the legacy signatures under the proposed CLI. Therefore a green Full GI run alone does not verify the new Foundry pair. Use the explicit Foundry smoke above. Fixing toolchain selection or historical platform `proxyAdmin` failures belongs to the integration-harness work unless a newly introduced regression is demonstrated. Report exactly which flow ran and any failures/skips.

## Delivery and completion criteria

Prefer three reviewable commits on #305: synchronization/CLI/tests; generated artifacts/manifest CIDs with evidence; documentation/status cleanup. Generated files must come from the final reconciled source.

Update the PR description to remove the pending #261 dependency, describe the cache refresh, record final head/base SHAs and validation evidence, and retain the redeployment/canonical-wiring caveats. Obtain fresh Solidity, Python, Docs and `CI OK` results and eligible reviews. The outstanding changes-requested review needs an explicit fresh verdict. Use current §4.2 approval rules and merge-queue validation rather than repeatedly syncing solely because develop advanced.

After merge, verify the landed develop SHA and checks. Issue #224 can be closed only after a peer checks all three decision deliverables against develop and records any separately tracked follow-up. This plan authorizes no production deployment or issue/PR mutation by itself.

Initial analysis performed: live PR/issue/review inspection; local three-way conflict inspection; contract/CLI/test/resolver source review; JSON constructor/ABI/bytecode inspection; helper/fixture incompatibility reproduction. Not performed: reconciled implementation, full pytest/Foundry suites, live Anvil or IPFS verification. Those are implementation acceptance steps above.

## Implementation record (2026-11-02)

- Astra audit completed; six corrections incorporated in rev 2.
- Isolated branch `fix/pr305-post261` at `/tmp/devnet-pr305-reconcile`; current upstream `cf80216` reconciled and saved in local merge commit `1b09d10`. CLI and backlog conflicts resolved.
- CLI preserves constructor dispatch and immutable-ID checking; catches empty/malformed getter output as well as contract reverts. Inherited test fixtures updated. Added command preflight coverage, second registry-read failure coverage, current Foundry documentation examples and a post-build artifact gate.
- First targeted run after these changes: 48 deployment/artifact-check tests passed. Full Python and Foundry validation underway.
- No implementation push, GitHub comment, approval, issue closure or production action performed. IPFS artifact availability remains to be verified for final regenerated bytes.

### Rev 3 validation and outstanding work

- 721 non-integration Python tests passed (133 integration tests deselected). Initial sandbox run had 720 passes and a local-socket permission failure; the authorized unsandboxed rerun passed completely. Latest deployment/artifact-check run: 48 passed.
- Clean Foundry v1.7.1 / solc 0.8.28 build passed. Full suite: **526 passed, 1 failed, 0 skipped** (527 total). Failure: `DeployPlatformScriptTest.test_writeDeployments_writesImplAndCodehashMetadata`, inherited unchanged from upstream #254, could not find `test-impl-metadata.json` while the parallel upgrade suite wrote `test-upgrade-metadata.json`. The two suites both mutate `DEPLOYMENTS_NETWORK`; isolated retry passes. This is strong evidence of a pre-existing shared-environment race, not a claim of a green full suite. It needs a separate fix or baseline disposition before merge.
- RewardEngine real-registry suite: 40 passed, including both registry-read failures, both start overloads and disable-during-GI completion/claims.
- Contract-size gate passed: coordinator 23,387 runtime bytes / 1,189 margin; auditor 21,885 runtime bytes / 2,691 margin. Artifact gate passed for both cached ABI/creation-bytecode files and both bundled ABI files.
- Actual Typer commands, real artifact loader and real `build_and_send_tx` exercised on isolated Anvil. Foundry/cache deployments, exact IDs, canonical configured registry, one-shot pairing and all rejection cases passed. Public development accounts only. Legacy Hardhat pair also checked without model-ID/registry arguments.
- Documentation checker: 294 relative links passed; whitespace/syntax checks passed. Focused Astra implementation recheck found no new code blockers.
- New cache artifact CIDs were pinned in an isolated offline Kubo v0.43.1 repo and fetched through real `ensure_file_exists` into an empty cache; exact bytes matched. **This is local integrity evidence only.** The manifest's new CIDs remain work-in-progress until persistently pinned on a reachable provider and independently retrieved. `cache-default-artifacts` bootstrap defaults remain unchanged.
- No production deployment, GitHub comment/review, remote branch push or issue closure performed. Do not describe this branch as merge-ready yet.

Detailed evidence and follow-up scope: [implementation summary](pr-305-post-261-reconciliation-summary.md).

Local implementation commit: `1b09d10` (`fix/pr305-post261`), unpushed. Temporary deployment outputs are preserved under `/tmp/pr305-evidence/generated-deployments`; reusable npm dependency symlink is `/tmp/pr305-tools/npm-dependencies`.

Final local implementation head: `33d5f83` after whitespace-only cleanup of `deploy.py`; merge commit remains `1b09d10`. Implementation worktree is clean. Final diff against upstream passes whitespace checks and the artifact gate still passes. Temporary Anvil and offline Kubo services have been stopped; evidence and local pin repository remain in `/tmp`.

### Rev 4 acceptance

- Regression tests for both official mixed-generation directions, including the two-argument legacy auditor, must show no constructor, transaction, environment write or pairing side effects. Unknown versions reject; transport errors do not select a legacy fallback.
- Live actual Typer/loader/transaction-builder smoke must reject mixed pairs without consuming nonce or changing `.env`, then allow the still-unpaired coordinator to pair with its matching auditor. Check direct Foundry, refreshed cache, previous Foundry and legacy Hardhat pairs.
- A pure coordinator capability getter changes no storage; full contract build, ABI/creation-bytecode parity and size gate must pass. RewardEngine real-registry lifecycle tests must remain green. Known global-environment metadata race stays separate.
- New manifest CIDs require fresh local integrity verification again and remain unavailable for merge until persistent IPFS publication and independent retrieval.

### Rev 4 implementation progress

- Added coordinator `taskProtocolVersion() == 1` and CLI generation preflight. Also reject mixing the two legacy families: a two-argument auditor cannot satisfy the later model-ID coordinator's reward-pool interface. Supported matching legacy deployments still succeed.
- 62 focused Python tests pass. Actual Typer/loader/builder live smoke passes all 16 cases, including eight rejected mixed pairings with unchanged nonce and `.env`, and successful matching direct/cache/previous-Foundry/Hardhat pairs. Evidence: `/tmp/pr305-version-evidence/results.json`.
- Clean Foundry build, regenerated artifact parity, size gate and all 294 relative documentation links pass. Coordinator runtime 23,425 B, margin 1,151 B; pure getter leaves all 43 storage entries unchanged (slot, offset, label and recursively normalized types compared against pre-version compiler output).
- Regenerated coordinator reference artifact pinned and freshly retrieved locally; new CID `bafybeif7fay4vgal4vb6ojsspc4e6muyyujuveyutszlf7z4mfb5uxkteu`, SHA-256 `e6287cbf75f984fd705c3d6937b02f31a1cee1c7b868e765a3b08f522129cbd6`, 104,022 bytes. Auditor artifact unchanged. These remain offline integrity receipts, not persistent publication.
- Initial incremental Foundry run exposed duplicate build-info files consumed by upgrades validation. Generated outputs were moved aside and a clean rebuild completed; final full-suite results follow below. No production code change was made to mask that build-state issue.

Local fix commit: `e8e7349` (`fix/pr305-post261`), unpushed. Astra independently rechecked the fix: original P2 addressed, no concrete new defect, 62 targeted tests and actual artifact gate pass. Final Python: 735 passed / 133 integration tests deselected. All 16 live cases pass. Temporary Anvil and Kubo services stopped. Clean full Foundry suite is finishing; final result follows.

### Rev 4 final validation

Clean full Foundry suite: **527 passed / 0 failed / 0 skipped** across 40 suites, including both metadata-writing suites and the invariant suite (`/tmp/pr305-version-clean-foundry.log`). This supersedes the preparatory incremental-build failures. It does not claim to fix the historical #254 shared-environment race, which remains separate.

Final local head: `e8e7349`; implementation worktree clean; no implementation push. Python **735 passed**, targeted **62 passed**, live CLI **16 cases passed** with all **8 mixed pairs rejected without transactions or address writes**. Exact artifacts, coordinator storage layout, size gate and 294 documentation links pass. Astra independently rechecked the P2 fix and found no concrete new defect. Remaining acceptance: persistent IPFS publication/independent retrieval and remote CI/eligible reviews.

Temporary services are stopped. Generated deployment test files are retained in `/tmp/pr305-version-evidence/generated-deployments`; reusable npm dependency symlink is `/tmp/pr305-version-evidence/npm-dependencies` (restore to `foundry/node_modules` or use locked `npm ci` for future FFI tests).
