# Issue #265 — correct transaction information on the local network

**Base:** local `develop` @ `5f610c79063eef622acbe3a0997930a5d5204c14`, inspected 2026-10-21.
**Branch:** this document belongs to the fork-only `plans` worktree. Proposed implementation branch: `fix/265-local-transaction-info`, based on refreshed upstream `develop`, never on `plans`.
**Origin:** [issue #265](https://github.com/InfiniteZeroFoundation/DevNet/issues/265), finding 2 and Umer's response in [discussion #260](https://github.com/InfiniteZeroFoundation/DevNet/discussions/260), and the user's request for an implementation plan following the investigation.
**Status:** rev 2 — Astra audit incorporated; implementation authorized by the user on 2026-10-21 using Sol 6.1 subagents at low reasoning effort. Validation results will be recorded after implementation.

> **Rev 2 changelog (2026-10-21, Astra audit).** No blockers found. Clarified exact hash-format compatibility, the remaining post-broadcast error path for malformed/unreadable configuration, and shared console capture for the transaction regression. Run the transaction-flow regression against the original implementation along with the display tests. Production changes and tests may be authored in parallel in separate files; preserve baseline evidence before accepting the combined fix.

**Outcome.** Local transactions print their hash without the incorrect Optimism Sepolia link. Networks with a configured explorer retain their links. Missing explorer metadata must not interrupt receipt checking after broadcast.

**Decisions and questions.** No user clarification is required. The maintainer's response specifies removing `local.explorer` and supporting hash-only output when no explorer is configured. An explicitly configured local explorer remains supported. The helper treats an absent or omitted network as lacking display metadata; this does not change RPC or chain-ID validation. Preserve current hash formatting, labels, function signature, and caller behavior.

**Evidence and failure mechanism.**

- `dincli/config/din_info.json:9` assigns the OP Sepolia explorer to local chain ID 1337.
- `dincli/cli/utils.py:1145` implements `print_tx_info`; its direct dictionary indexing raises when the network or explorer key is missing. Empty and null explorer values generate unusable links.
- `build_and_send_tx` broadcasts at `utils.py:1005`, prints at line 1007, then waits for the receipt at line 1008. An exception from printing reaches the transaction-failure handler before receipt checking. Removing the config key alone would introduce this failure on local transactions.
- `system send-eth` has the same ordering at `dincli/cli/system.py:892–894` and directly uses the shared print helper.
- Buy and stake route through `build_and_send_tx`; existing `tests/test_dintoken.py` mocks that helper, so those tests do not cover explorer formatting or this receipt-checking regression.
- `load_din_info` reads packaged JSON. `system import-deployments` updates deployment fields while preserving other metadata; neither loader nor importer needs modification.
- Investigation executed the unchanged helper body with stubbed config and console, confirming these display failures. Full module imports were unavailable because the checkout's virtual environment lacks `rich`; dependency and test execution remain implementation work.

**Expected behavior.**

| Input/configuration | Expected output |
|---|---|
| Bundled local entry | Hash only |
| Bundled `sepolia_op_devnet` entry | Hash and existing explorer URL |
| Local entry with an explicitly configured explorer | Hash and configured explorer URL |
| Missing explorer key, empty string, or JSON null | Hash only |
| Unknown network or omitted network argument | Hash only |
| `print_url=False` | Hash only; do not load explorer metadata |
| Explorer base ending in `/` | One `/` before `tx/<hash>` |

**Implementation sequence.**

1. Prepare the implementation checkout.
   - Refresh upstream `develop`, inspect changes affecting the three target files, and record the new base SHA if it differs.
   - Create `fix/265-local-transaction-info` from that base. Preserve unrelated local work and keep all `Plans/` content out of the upstream diff.
   - Use an isolated Python 3.12+ environment with the project's declared dependencies and test dependencies; follow the existing CPU PyTorch setup if needed for the full suite. Do not modify dependency declarations for this issue.

2. Add regression tests in `tests/test_tx_info.py`.
   - Capture `dincli.cli.utils.console` using a Rich `Console` backed by `StringIO`, a wide output width, and disabled color. Assert visible text, not ANSI sequences or markup implementation details.
   - Cover each row of the expected-behavior table. Parameterize missing/empty/null cases and network lookup fallbacks to keep the suite small.
   - Exercise the real packaged config for local and OP Sepolia behavior; use the original loader and do not save or modify package config. Assert local has no bundled explorer and OP Sepolia retains its configured base.
   - Verify a custom local explorer is honored; do not encode a blanket local-network prohibition.
   - Verify `print_url=False` does not call `load_din_info` by supplying a loader stub that raises if called.
   - Exercise string, `bytes`, and Web3-style `HexBytes` hash inputs against existing formatting behavior. Strings remain unchanged; byte-like inputs retain their current `.hex()` rendering. Plain `bytes` produce no `0x`, and `HexBytes.hex()` behavior depends on the installed dependency version. Assert the exact expected hash and matching URL suffix; do not introduce `_hex0x` normalization in this issue.
   - Include the transaction-flow regression specified in step 4 in this baseline run. Run this file against the original implementation and record the expected failures before accepting the combined fix. If authors work in parallel, use a temporary isolated copy of the original production files for this baseline; do not revert another agent's edits.

3. Correct the configuration and output helper together.
   - Remove the `explorer` key from only the `local` JSON entry. Preserve addresses, chain IDs, CIDs, and the OP Sepolia explorer.
   - Keep the current hash conversion and print the hash unconditionally.
   - Return immediately when `print_url` is false.
   - Resolve optional display metadata using safe lookups, conceptually `load_din_info().get(network, {}).get("explorer")`.
   - Return without printing a URL if the explorer is absent, empty, or null. For a configured base, remove a trailing slash before appending `/tx/<hash>`.
   - Add a concise docstring describing hash-only fallback. Retain the public signature and output labels.
   - Do not add a broad exception handler. Unreadable/malformed configuration and invalid metadata types retain existing exception behavior, including the existing post-broadcast error path; this change guarantees fallback for absent metadata only. General URL validation, arbitrary wrong JSON types, and automatic explorer-to-chain verification are outside scope.

4. Add one transaction-flow regression in the same test file.
   - Use the real `build_and_send_tx` and real `print_tx_info`, with minimal mocked context, contract function, account, and Web3 calls. Use a local entry without an explorer. Return the same captured Rich console from the fake context that is patched into `utils.console`: the two functions otherwise obtain their consoles differently.
   - Make broadcast return a known hash and receipt waiting return a status-1 receipt.
   - Assert broadcast occurs once, receipt waiting receives that hash, the original receipt is returned, success is printed, and neither an explorer URL nor the transaction-failure message appears.
   - Keep the fixture isolated; no real wallet, RPC, funds, deployment, or package-config writes. No duplicate integration fixture is needed for every buy/stake caller.

5. Validate and prepare one focused PR.
   - Run `python -m pytest tests/test_tx_info.py -q`.
   - Run `python -m pytest tests/test_dintoken.py tests/test_chain_id_validation.py tests/test_batch_seed_lock.py -q` for nearby regressions.
   - Run `python -m pytest -m "not integration" -q`, matching the Python CI selection. Record failures and distinguish environmental limitations from code failures.
   - Run `git diff --check` and inspect the final diff. The expected implementation diff is the JSON config, shared helper, and new test file only.
   - PR description: explain the incorrect local link, hash-only fallback, and continued receipt checking; include actual validation results and `Fixes #265`.

**Acceptance criteria.**

- Bundled local transactions display the hash and no public explorer URL.
- OP Sepolia and explicitly configured local explorers retain working `/tx/<hash>` links.
- Missing/empty/null explorer values and absent network metadata produce hash-only output without an exception.
- `print_url=False` still suppresses metadata loading and link output.
- A successful broadcast followed by missing explorer metadata still reaches receipt checking and returns success.
- No transaction submission, signing, retry, receipt, chain-validation, or hash-format behavior is changed.
- Focused and non-integration Python checks pass in the prepared environment; no Solidity, ABI, workflow, or dependency changes are introduced.

**Scope boundaries and rollout.** This is a single small PR; no contract deployment or state migration is needed. Leave `bridge-eth`'s Ethereum Sepolia L1 explorer unchanged. Do not add explorer configuration commands, relocate packaged configuration, repair unrelated transaction handling, or implement other findings from discussion #260. Existing manually retained configurations containing a wrong explorer are not automatically migrated; this fix corrects the repository's bundled default and trusts explicitly supplied metadata. No test can establish an arbitrary configured explorer's chain correctness without an additional verification design.
