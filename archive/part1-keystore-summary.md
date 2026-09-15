# Part 1 — Keystore Security Implementation Summary

**Task:** `task_300626_3` (P3-T0.2b)  
**Branch:** `feat/validator-readiness`  
**Date:** 2026-07-01 (implementation) / 2026-07-02 (fixes)

---

## Summary of changes

### 1a — Docs & templates: plaintext-key audit + production callouts

**New files:**
- `/.env.example` — authoritative root template for RPC URLs, wallet keys, `DIN_WALLET_PASSWORD`, `DIN_WALLET_NAME`
- `hardhat/.env.example` — signpost template noting Hardhat reads `../.env`

**Modified files:**
- `dincli/docker/node/.env.example` — added key-management section pointing to encrypted keystore docs
- `dincli/docker/node/README.md` — updated file-tree diagram (`wallet.json` → `wallets/`, `.session` described as legacy-only); added dev-vs-prod key management subsection
- `Documentation/setup.md` — production keystore callout above `ETH_PRIVATE_KEY_<n>` section
- `Documentation/GettingStarted.md` — production keystore callout above private key env section
- `Documentation/common.md` — updated wallet management section with `--keystore`, `--name`, `list-accounts`
- `Documentation/Model-workflow.md` — production warning on `--account` usage
- `Documentation/guides/ipfs.md` — linked wallet-setup as prerequisite
- `Developer/DEVELOPMENT_SETUP.md` — linked wallet-setup as prerequisite
- `Documentation/technical/DINCLI_Containerizaton_Guide.md` — production keystore pointer

### 1b — Burner wallet setup guide

**New file:** `Documentation/guides/wallet-setup.md`
- Why dedicated burner wallets
- Generation: `eth-account` one-liner + OWS (`ows wallet create`)
- Funding: 10 DIN + ETH for gas (corrects "ETH to stake" → "DIN to stake")
- Tiers table: `.env` → encrypted keystore → `--keystore` → `DIN_WALLET_PASSWORD` → OWS delegation
- Links to `keystore-migration.md`

### 1c — Code: in-memory cache + --keystore + named accounts + --wallet

**1c-A — In-memory password cache (`dincli/cli/utils.py`):**
- Replaced on-disk `CONFIG_DIR/.session` cache with module-level `_PASSWORD_CACHE` dict
- TTL via `DIN_PASSWORD_TTL` env (default 900s)
- `_get_password(name)` lookup: env var → in-memory cache → `getpass`
- `_cache_password_in_memory(name, password)` — never touches disk
- `_cleanup_stale_session()` — removes old `.session` on load, dev-only notice
- **No cross-invocation persistence** (intentional — D1)

**1c-B — `--keystore <path>` import (`dincli/cli/system.py`):**
- New option on `connect-wallet`: `--keystore <path>`
- Reads standard eth-account JSON keystore, prompts for passphrase
- Validates by decrypting and deriving checksum address
- Stores as wrapped keystore with `source: "imported"`, original keystore preserved verbatim

**1c-C — Named multi-account + runtime `--wallet` selection:**
- **Storage:** `CONFIG_DIR/wallets/wallet_<name>.json` with shared wrapper schema
- **Wrapper schema:** `{"version":1, "address":"<checksummed>", "keystore":{...}, "source":"created|imported", "name":"<name>"}`
- **`_extract_keystore(data)`** normalizes wrapper + bare + demo forms before `Account.decrypt`
- **`load_account(name)`** resolves named → legacy fallback
- **Default precedence:** `wallets/wallet_default.json` wins over legacy `wallet.json`
- **Atomic writes** with `os.open(0o600)` + `os.replace` + defensive `os.chmod`
- **Name validation:** `^[A-Za-z0-9_-]{1,64}$`
- **Top-level `--wallet <name>`** flag in `dincli/main.py` + `GlobalOptionsGroup` in `core.py`
- **`DinContext.select_wallet(name)`** mirrors `select_network`
- **`DinContext.resolved_wallet_name`** resolution order: `--wallet` → `DIN_WALLET_NAME` env → config `wallet_name` → `"default"`
- **Active wallet name** surfaced in `get_en_w3_account_console`
- **`read_wallet`** and **`todo`** use active wallet resolution, not legacy `wallet.json`
- **`list-accounts`** command — enumerates `wallets/*.json` + legacy; dedup: named default hides legacy row

**1c-D — OWS integration feasibility:**
- Verified: OWS v1.0.0 has Python SDK (`open-wallet-standard`), CLI, MCP/REST/SDK interfaces
- Recommended document-only for now; `wallet-setup.md` uses OWS as keystore generation tool
- Signing delegation requires OWS running as a local service with scoped API tokens

### 1d — Keystore migration guide

**New file:** `Documentation/guides/keystore-migration.md`
- What changed (old `.env` → new encrypted keystores)
- Migration: `eth-account` → temp keystore → `dincli --keystore` import → delete temp
- Docker/wallet-name setup instructions
- Named wallet precedence documentation
- Runtime selection table
- `.session` cleanup instructions

### Tests

**New file:** `tests/test_connect_wallet.py`
- `TestUtilsFunctions`: name validation, path helpers, resolve precedence, extract keystore, password cache TTL/memory/invalidation, stale session cleanup, list accounts
- `TestAtomicWrite`: file creation, `0o600` permissions, overwriting loose-mode files, wallets dir `0o700`
- `TestConnectWalletKeystore`: valid import, wrong password, missing file, malformed JSON
- `TestConnectWalletNamedAccounts`: wrapper schema, name validation rejection
- `TestConnectWalletMutualExclusivity`: duplicate methods → exit 1
- `TestReadWallet`: named wallet resolution
- `TestTodoWalletAwareness`: named wallet in `todo`
- `TestLoadAccount`: named, legacy fallback, demo mode
- `TestCLICommands`: `list-accounts` empty, help exposes `--keystore`/`--name`

---

## Part 1 Fixes (2026-07-02)

Following an external audit (4 confirmed implementation-detail corrections) and
empirical test execution (12/35 `test_connect_wallet.py` tests failing), the
following fixes were applied per `Plans/archive/part1-keystore-fixes.md`.

### Fix A — Create `wallets/` dir before demo-mode save

**File:** `dincli/cli/system.py`
**Root cause:** Demo-mode write path opened `wallet_path_for_name(name)` for writing
without ensuring the parent `wallets/` directory existed, causing `FileNotFoundError`
on fresh installs.
**Fix:** Added `ensure_wallets_dir()` call immediately before the demo-mode
`open()` write.

### Fix B — Validate account names at the filesystem boundary

**Files:** `dincli/cli/utils.py`, `dincli/cli/context.py`, `dincli/cli/system.py`, `dincli/main.py`
**Root causes:**
1. `wallet_path_for_name()` had no validation — any caller (including `load_account()`, `resolve_wallet_path()`) could construct paths with unsafe names before touching the filesystem.
2. `get_active_account_name()` returned unvalidated strings from `--wallet`, `DIN_WALLET_NAME`, or config.
3. No clean error exit for invalid names at the CLI level.
4. `main.py` printed "Active Network" before calling `select_wallet()`, so an invalid `--wallet` would produce output before failing.
**Fixes:**
1. `wallet_path_for_name(name)` now calls `validate_account_name(name)` and uses the stripped result — the single boundary function all paths funnel through.
2. `get_active_account_name()` now validates via `validate_account_name()` before returning.
3. `DinContext.resolved_wallet_name` wraps the call in `try/except ValueError` → `sys.exit(1)` with red error.
4. `DinContext.select_wallet()` validates the incoming `--wallet` value immediately → `console.print` + `typer.Exit(1)`.
5. `read_wallet`, `todo`, `list_managed_accounts` in `system.py` switched from `get_active_account_name(ctx.obj)` to `ctx.obj.resolved_wallet_name` for centralized clean exit.
6. `main.py` reordered: `select_wallet()` runs before network resolution/print.

### Fix C — Persist unwrapped keystore on `--keystore` import

**File:** `dincli/cli/system.py`
**Root cause:** `inner_keystore = imported_ks` saved the outer raw keystore instead
of the extracted `inner_ks`, causing double-wrapping if the imported file was already
dincli-wrapped.
**Fix:** Changed to `inner_keystore = inner_ks` (line ~345).

### Fix D — Remove unverified OWS export command from docs

**File:** `Documentation/guides/wallet-setup.md`
**Root cause:** `ows wallet export --name ... --output ...` is not in OWS's published
CLI subcommand list (`create/list/info/sign/mnemonic`).
**Fix:**
- Kept `ows wallet create --name <name>` (confirmed in OWS CLI reference).
- Removed the unverified `export` command; replaced with a note to check
  `ows --help` / `https://docs.openwallet.sh/` for the current export surface.
- AES-256-GCM claim now cites `https://openwallet.sh/` as corroborated source.

### Fix E — Add `set-wallet` command; fix skip-list; update migration doc

**Files:** `dincli/cli/system.py`, `Documentation/guides/keystore-migration.md`
**Root causes:**
1. No command existed to persist `wallet_name` to config — `keystore-migration.md` incorrectly attributed this to `configure-network`.
2. `system()` callback's subcommand skip-list used underscored names (`read_wallet`, `show_index`) instead of the actual Click/Typer command names (`read-wallet`, `show-index`), forcing those commands through the account-resolution gate unnecessarily.
**Fixes:**
1. New `dincli system set-wallet <name>` command (mirrors `configure-network` pattern) — validates name, persists `wallet_name` to `config.json`.
2. Skip-list entries corrected to `"read-wallet"`, `"show-index"`; added `"set-wallet"`.
3. `keystore-migration.md` §6 table row updated to `dincli system set-wallet <name>`.

### Fix — `todo()` UnboundLocalError

**File:** `dincli/cli/system.py`
**Root cause:** The `else` block at line ~769 was misindented — paired with the outer
`if network:` instead of the inner `if get_env_key(...) is None:`, causing it to
reference `rpc_env_key` which was only defined inside the `if network:` branch.
**Fix:** Corrected the indentation so `else` pairs with the inner `if` check.

### Test fixes (12 previously-failing tests)

**File:** `tests/test_connect_wallet.py`

| Fix | Tests affected |
|---|---|
| Finding G — monkeypatch targets: `"getpass.getpass"` → `system_mod.getpass` / `utils_mod.getpass` | `test_keystore_import_valid`, `test_keystore_import_wrong_password`, `test_save_named_wrapper_schema`, `test_read_wallet_named_wallet`, `test_todo_shows_named_wallet`, `test_load_account_named_wallet`, `test_load_account_legacy_fallback` |
| `DummyCtxObj` missing `account` / `resolved_wallet_name` properties | `test_read_wallet_named_wallet` (all others indirectly) |
| `todo()` `UnboundLocalError` | `test_todo_shows_named_wallet` |
| `test_validate_account_name_invalid` length: `"abc" * 20` (60 chars, valid) → `"a" * 65` | `test_validate_account_name_invalid` |
| Cache tests: call `_cache_password_in_memory()` explicitly | `test_in_memory_password_cache`, `test_clear_memory_cache` |
| `CliRunner(mix_stderr=False)` unsupported kwarg | `test_list_accounts_command_empty` |
| Finding I — fixture teardown typo | `temp_config` fixture |

### New regression tests

**File:** `tests/test_connect_wallet.py`

| Test class | Tests |
|---|---|
| `TestFixARegression` | `test_demo_mode_creates_wallets_dir` — from-scratch bare directory (no pre-created `wallets/`), asserts no exception |
| `TestFixBRegression` | `test_wallet_path_for_name_rejects_escape` — direct unit test; `test_load_account_rejects_escape` — direct unit test; `test_cli_wallet_flag_invalid_name_exits` — CliRunner; `test_cli_set_wallet_rejects_invalid_name` — CliRunner |
| `TestFixCRegression` | `test_import_single_level_keystore` — verifies no nested keystore; `test_reimport_wrapped_keystore_not_double_wrapped` — re-imports a dincli-wrapped file, asserts single-level result |
| `TestFixERegression` | `test_set_wallet_persists_config` — verifies wallet_name is written to config.json |
| `TestSkipListRouting` | `test_read_wallet_no_wallet_reaches_command_body`, `test_show_index_no_wallet_reaches_command_body`, `test_set_wallet_no_wallet_reaches_command_body` — CliRunner-based tests confirming subcommands reach their bodies without falling into the account-resolution gate |

### Test results

```
tests/test_connect_wallet.py — 46 passed in 9.73s
Full suite: 46 passed (connect_wallet), 56 total passed (all tests),
            1 pre-existing failure (test_dintoken.py::test_stake_uses_requested_amount — unrelated),
            134 environment-specific errors (tests requiring /home/azureuser),
            3 warnings
```

---

## Files touched (Part 1 implementation + fixes)

**New (6):**
- `/.env.example`
- `hardhat/.env.example`
- `Documentation/guides/wallet-setup.md`
- `Documentation/guides/keystore-migration.md`
- `tests/test_connect_wallet.py`
- `Plans/archive/part1-keystore-summary.md` (this file)

**Modified (14):**
- `dincli/cli/utils.py` — in-memory cache + named-store helpers + `load_account(name=)` + `list_accounts` + Fix B (boundary validation in `wallet_path_for_name`, validation in `get_active_account_name`)
- `dincli/cli/system.py` — `--keystore` + `--name` + `list-accounts` + active wallet in `read_wallet`/`todo` + Fix A (`ensure_wallets_dir`), Fix C (`inner_keystore = inner_ks`), Fix E (`set-wallet`, skip-list fix), `todo()` UnboundLocalError fix
- `dincli/cli/context.py` — `wallet_name` + `resolved_wallet_name` + `select_wallet` + display + Fix B (try/except in `resolved_wallet_name`, validation in `select_wallet`)
- `dincli/main.py` — `--wallet` global option + Fix F (reorder `select_wallet` before network print)
- `dincli/cli/core.py` — `--wallet` in `GlobalOptionsGroup`
- `dincli/docker/node/.env.example` — key-mgmt note
- `dincli/docker/node/README.md` — file tree + dev-vs-prod section + `.session` legacy note
- `Documentation/setup.md` — production callout
- `Documentation/GettingStarted.md` — production callout
- `Documentation/common.md` — wallet management update
- `Documentation/Model-workflow.md` — production warning
- `Documentation/guides/ipfs.md` — wallet-setup link
- `Developer/DEVELOPMENT_SETUP.md` — wallet-setup link
- `Documentation/technical/DINCLI_Containerizaton_Guide.md` — production pointer

---

## Design deviations from task spec

1. **D1 — Cross-invocation password caching removed.** On-disk `.session` replaced with in-memory cache. Only `DIN_WALLET_PASSWORD` env avoids re-prompting across commands.
2. **D2 — No overloading.** `--account` stays `int` (dev key indices); new `--name` for keystore label; new `--wallet` for runtime selection.
3. **`hardhat/.env.example`** is signposted, not authoritative (Hardhat reads `../.env`).
4. **No SIGTERM handling** — deferred to P4 per plan.

---

## Review notes

- PR must be flagged `needs-security-review`
- Umer reviews commits: password-cache removal (commit 4) and named-keystore/import (commit 5)
- Fixes B and A touch the exact surfaces (`--wallet` resolution, demo-mode save) already under review — re-flag `needs-security-review`
- All 46 `test_connect_wallet.py` tests verified passing with actual `pytest` execution in this environment
