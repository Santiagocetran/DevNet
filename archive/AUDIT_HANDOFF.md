# Audit Handoff — task_300626_3 (Validator Readiness: Keystore Security + Filecoin Adapter)

**Purpose of this file:** a neutral, factual summary of everything implemented on `feat/validator-readiness`, for an independent agent (no prior context) to audit fresh. This is a handoff document, not a self-assessment — verify the claims below rather than trust them. This file is untracked; delete or leave it out of the PR once the audit is done.

---

## 1. Source of truth

- **Task spec:** `Developer/tasks/task_300626_3.md` — read this in full first. It defines two independent parts (Part 1: keystore security, Part 2: Filecoin/Lighthouse adapter) with explicit deliverable checklists.
- **Related design doc:** `Developer/discussion/add-filecoin-support.md` (strategic case for Filecoin storage, provider comparison — written before implementation, some assumptions in it were found to not hold, see §6 below).
- **Planning/audit trail (`plans` branch, fork-only):** `Plans/archive/part1-keystore-security.md`, `Plans/archive/part1-keystore-fixes.md`, `Plans/archive/part1-keystore-summary.md`, `Plans/archive/part2-filecoin-lighthouse.md`, `Plans/archive/part2-implementation-summary.md`, `Plans/archive/pr-description-draft.md`. These document the iterative plan → implement → audit → fix cycle this work went through (two full review rounds, each surfacing real bugs that were then fixed and re-verified). Useful context on *why* things ended up the way they did, but don't take their "everything checks out" conclusions at face value — re-derive them.

## 2. Branch / commit state

- Branch: `feat/validator-readiness`, based on `develop` (base branch per the task spec).
- Remote: `origin` = `git@github.com:Santiagocetran/DevNet.git` (a fork, not upstream `InfiniteZeroFoundation/DevNet`). Nothing pushed yet as of this handoff.
- 7 commits since `develop` (`d6851e2`), in this order:
  1. `feat(wallet): in-memory password cache, --keystore import, named multi-account store, list-accounts`
  2. `feat(wallet): wire --wallet CLI flag through DinContext`
  3. `docs(wallet): add burner-wallet + keystore-migration guides, env templates, and production-key callouts`
  4. `test(wallet): add connect-wallet regression + new-path coverage`
  5. `feat(ipfs): add Lighthouse (Filecoin) provider adapter + IPFS_PROVIDER env var + provider-scoped API keys (D6/D7)`
  6. `docs(ipfs): document the lighthouse provider; fix stale three-provider references`
  7. `test(ipfs): add Lighthouse provider tests + regression coverage for provider selection and API-key scoping`
- Commits 1–2 are flagged `needs-security-review` per the task spec (Umer must review keystore-related changes before merge — this has **not** happened yet).
- History was rewritten once (commits were originally tangled — Part 1 and Part 2 changes got mixed into the same commits by an earlier pass) and re-verified to produce a tree byte-identical to the previously-tested state before finalizing. Worth spot-checking that the commit boundaries above actually hold (e.g. `git show <commit> --stat` for each) rather than assuming.

## 3. What was implemented — Part 1 (keystore security)

**Files:** `dincli/cli/system.py`, `dincli/cli/utils.py`, `dincli/cli/context.py`, `dincli/cli/core.py`, `dincli/main.py`, new `Documentation/guides/wallet-setup.md` + `keystore-migration.md`, `/.env.example` + `hardhat/.env.example`, docker node docs/env template, production-keystore callouts across `setup.md`/`GettingStarted.md`/`common.md`/`Model-workflow.md`/`DINCLI_Containerizaton_Guide.md`/`DEVELOPMENT_SETUP.md`, new `tests/test_connect_wallet.py`.

**Functionality:**
- `dincli system connect-wallet --keystore <path>`: imports a standard eth-account JSON keystore, decrypts to derive/verify the checksummed address, stores original keystore bytes verbatim (`source: "imported"`).
- `dincli system connect-wallet --name <name>`: named multi-account keystores at `CONFIG_DIR/wallets/wallet_<name>.json`, shared wrapper schema `{version, address, keystore, source, name}`. Legacy `CONFIG_DIR/wallet.json` still loads as `"default"` when no named default exists (named default wins if both are present).
- `--wallet <name>` (top-level CLI flag) / `DIN_WALLET_NAME` env / config `wallet_name` (settable via new `dincli system set-wallet <name>`): runtime account selection, resolved through `DinContext.resolved_wallet_name`. Precedence: `--wallet` → env → config → `"default"`.
- `dincli system list-accounts`: enumerates named wallets + legacy fallback without decrypting.
- Account-name validation (`^[A-Za-z0-9_-]{1,64}$`) is enforced inside `wallet_path_for_name()` itself (the lowest-level function every wallet path resolves through), not just at CLI parsing — intended to make path-traversal-via-name impossible regardless of call site.
- Password handling: on-disk `CONFIG_DIR/.session` plaintext cache **removed**, replaced with an in-memory, per-process, TTL-based cache (`_PASSWORD_CACHE`, default 900s via `DIN_PASSWORD_TTL`). This is an intentional behavior change — passwords are no longer cached across separate CLI invocations; only `DIN_WALLET_PASSWORD` env avoids re-prompting across commands. Stale `.session` files from old installs are auto-deleted on load.
- Atomic writes for wallet files (temp file + `os.replace` + explicit `chmod 0o600`) so permissions end up correct even when overwriting a pre-existing loose-permission file; `wallets/` directory created at `0o700`.

**Explicit design deviations from the task's literal wording** (documented in the PR draft, flagged for confirmation, not silently done): `--account` stays an `int` (dev key index) rather than being overloaded to accept a name; cross-invocation password caching is fully removed rather than "moved to memory with equivalent convenience."

## 4. What was implemented — Part 2 (Filecoin/Lighthouse adapter)

**Files:** new `dincli/services/ipfs_lighthouse.py`, `dincli/services/ipfs.py` (dispatch), `dincli/cli/utils.py` (`SUPPORTED_IPFS_PROVIDERS`, `resolve_ipfs_config`), `dincli/cli/system.py` (`configure_ipfs`, `todo()` diagnostics), `Documentation/guides/ipfs.md`, `CLAUDE.md`, `Documentation/ReadMe.md`, `Documentation/setup.md`, new `tests/test_ipfs_lighthouse.py`, extended `tests/test_ipfs_config.py`.

**Functionality:**
- New first-class provider `"lighthouse"` (alongside existing `env`/`filebase`/`custom`), not implemented via the generic dynamic-module `custom` path that the discussion doc's prose suggested — this was a deliberate choice, documented as such.
- `upload_via_lighthouse`: `POST https://upload.lighthouse.storage/api/v0/add`, `Authorization: Bearer <key>`, multipart field `file`, extracts CID from the **nested** `{"data": {"Hash": ...}}` response shape (Filebase's equivalent is a flat `{"Hash": ...}` — verify this distinction is actually handled correctly, it's an easy copy-paste mistake).
- `retrieve_via_lighthouse`: unauthenticated `GET https://gateway.lighthouse.storage/ipfs/<cid>`. **See finding in §6 — this does not currently work.**
- `IPFS_PROVIDER` env var added as a generic fallback for provider selection (config wins if set) — applies to all providers, not just Lighthouse.
- API keys changed from one shared `config["ipfs_api_key"]` field to per-provider `config["ipfs_api_key_<provider>"]`, with back-compat: legacy flat key still resolves for `filebase` only; `LIGHTHOUSE_API_KEY` env var is a fallback for `lighthouse` only. This was a fix for a bug found during review — the original design let switching providers silently reuse another provider's stored key.

## 5. Test results (reproduce these, don't trust them as reported)

```bash
python -m ensurepip --upgrade   # this repo's .venv ships without pip
python -m pip install -e .
python -m pip install pytest
python -m pytest tests/test_connect_wallet.py tests/test_ipfs_config.py tests/test_ipfs_lighthouse.py -v
python -m pytest   # full suite
```
Last known result: 61 passed (the three files above); full suite 68 passed, 1 pre-existing failure unrelated to this work (`tests/test_dintoken.py::test_stake_uses_requested_amount`), 1 skipped, 134 errors that are pre-existing and environment-specific (require a path under `/home/azureuser`, unrelated to this branch).

## 6. Known open findings — already surfaced, not yet resolved

1. **Lighthouse retrieval is confirmed payment-gated, live-tested against a real account.** `GET https://gateway.lighthouse.storage/ipfs/<cid>` returns `HTTP 402 Payment Required`, identically with and without the uploading account's own API key attached. A generic public IPFS gateway (`ipfs.io`) also failed for the same CID ("no providers found"). Upload works and matches documentation exactly; **retrieval currently does not work at all** for this account. This contradicts both the discussion doc's framing of Lighthouse as providing "a fast retrieval gateway" and the task's own stated assumption ("retrieval can fall back to the standard IPFS HTTP gateway"). Not flagged as a code bug — the adapter matches Lighthouse's documented contract; this is a platform/billing characteristic. Being raised with Umer/Abraham directly (WhatsApp + PR description) as an architectural question, not something resolved in this branch.
2. **No PR has been opened yet**, so the task's required Umer security review of commits 1–2 has not happened.
3. **Minor, cosmetic:** `connect-wallet --name <invalid>` raises a raw unhandled `ValueError` rather than the clean `console.print` + `typer.Exit(1)` pattern used everywhere else in that function (including the newer `set-wallet` command's equivalent check). Exit code is still non-zero either way; not a functional bug, just an inconsistency.
4. **Not independently verified in this pass, worth a fresh look:** the `configure_ipfs` CLI-layer validation for the per-provider-key fix (item 4 in §4) was manually exercised once and behaved correctly, but has no automated test at the CLI layer — only the underlying `resolve_ipfs_config()` resolution logic is test-covered.

## 7. Suggested angles for the fresh audit

- Read the actual diffs (`git show <commit>` for each of the 7) rather than this summary — confirm the commit boundaries described in §2 are real and nothing bleeds across them.
- Run the test suite yourself; don't trust §5's numbers without reproducing them.
- Check whether the nested-vs-flat JSON response handling (§4) is actually correct by reading `dincli/services/ipfs_lighthouse.py` directly.
- Check whether the name-validation-at-the-boundary claim in §3 actually holds by tracing `wallet_path_for_name()`'s callers.
- Form your own view on whether the Lighthouse retrieval finding (§6.1) should block merge, independent of how it's framed here.
