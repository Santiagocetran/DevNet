# Implementation Plan — DIN-SDK loaders wave 1 (config · log · web3 → then ipfs · contracts)

**Issue:** #20 (DIN-SDK) · **Branch:** `feat/din-sdk`
**Scope:** extract the *dependency-root* loader cluster (`config`, `log`, `web3`) into
`dincli/sdk/`, then use it to complete the clean-seed by moving `ipfs` and `contracts` in.
**Status:** DRAFT v3 — audit-approved; ready to implement.
**Depends on:** the seed already landed in `a54f9b5` (`dincli/sdk/` package, `sdk/cid.py`,
`sdk/errors.py`, `tests/test_sdk_boundary.py`).
**Does NOT need Umer's sign-off:** mechanical relocation + presentation-stripping; commits to no
public-interface decision P3-DOC7 could overturn (that's the keystones step).

> **Update (2026-07-13):** Umer confirmed v0.3 is "exactly the direction I was hoping for"; formal
> feedback imminent, after which the contract freezes. Validates this plan's scoping — the
> **keystones** wait for that feedback; this loaders wave does not.
>
> **v2 (audit-incorporated):** a code-audit found real breakages in the v1 shim/test details. v2
> fixes: (1) `cli/log.py` shim must also re-export stdlib `logging`; (2) the `cli/utils.py` shim
> list was incomplete — full inventory below, generated from `rg`; (3) **test migration is
> required** — re-export does NOT redirect a moved function's module globals, so tests that patch
> `utils.CONFIG_FILE` and call moved functions must patch `sdk.config` instead; (4) wallet path
> constants stay in `cli/utils.py` and must not be deleted with the config block; (5)
> `normalize_ipfs_provider` normalizes aliases + passes unknown through (no validation) — test
> parity accordingly.
>
> **v3 (final audit):** extended Test migration to **Phase 2** — `test_ipfs_config.py` patches
> `ipfs.get_cidv1base32_from_cid` / `ipfs.requests.post`, which move to `sdk.ipfs` (same
> patched-globals lesson, one phase later). Clarified plan-internal "Phase" vs cross-plan "wave"
> naming, and the `web3` test patch target.

---

## Why this is the next step

In `a54f9b5` only `cid` could move — every other "clean-seed" module reaches into
`dincli.cli.*` at import time, which fails the import-boundary test:

- `services/ipfs.py:7-13` imports `dincli.cli.log.logger` and `dincli.cli.utils`
  (`FILEBASE_*`, `resolve_ipfs_config`).
- `services/runtime.py:7` imports `dincli.cli.utils` (`get_manifest`, `get_manifest_path`).
- `cli/contract_utils.py:122` lazily imports `dincli.cli.utils.get_w3`.

`config` + `log` + `web3` are the **root**: nothing below them depends on `dincli.cli`, and
`ipfs`/`contracts` become movable once they exist in `sdk/`. Verified `get_w3` closure
(`utils.py:331`): `get_w3` → `resolve_network_value` (`284`) → `get_env_key` (`236`) +
`load_config` (`161`). All config, no `din_info`. (`manifest`/`runtime` pull in IPFS retrieval +
`din_info` — deferred to a follow-up plan, din-sdk-02.)

---

## Design decisions (resolved before implementation)

- **Extract + re-export shim, per the `cid` precedent** — move the implementation into `sdk/`,
  re-import it back into the old module. Covers the **23** `cli/utils.py` importers and **3**
  `cli/log.py` importers with no edits to them.
- **The shim is NOT transparent to patched module globals (audit #3).** A re-exported function
  still resolves bare names (`CONFIG_FILE`, `logger`, …) in *its own* module namespace
  (`sdk.config`), not in `cli.utils`. So `monkeypatch.setattr(utils, "CONFIG_FILE", …)` followed
  by a call to a *moved* function is a no-op. → Tests that do this must patch `sdk.config`
  directly (see "Test migration"). Tests patching names used by functions that *stay* in
  `utils.py` are unaffected.
- **`sdk/log.py`, not `sdk/logging.py`** — avoids stdlib shadow; mirrors `cli/log.py`.
- **`sdk.config` uses `logging.getLogger("dincli")` directly, never imports `sdk.log`.**
  `load_config`/`get_env_key` already log; `config` importing `log` while `log` imports
  `config.get_config` would be a cycle. So: `config → stdlib logging` only; `log → config`;
  one-directional.
- **Wallet path constants STAY in `cli/utils.py` (audit #4).** `WALLET_FILE`/`LEGACY_WALLET_FILE`
  (`utils.py:41,44`), `WALLETS_DIR` (`42`), `MIN_STAKE` (`46`) belong to the wallet layer (a later plan).
  They depend on `CONFIG_DIR`, so the `from dincli.sdk.config import CONFIG_DIR, …` re-export must
  appear **above** their definitions in `utils.py`. Do not delete them with the config block.
  (Terminology: "Phase 1/Phase 2" are stages *within this plan*; `manifest`/`runtime`/`wallet` are
  separate follow-up plans, din-sdk-02+, not a "Phase 3" here.)
- **Behavior parity, not redesign.** Keep `ConnectionError` (`get_w3`), `KeyError`
  (`resolve_network_value`), alias pass-through (`normalize_ipfs_provider`) exactly as-is; mark
  wrap-sites `# TODO(sdk-keystones): wrap in <DinError>`. Wrapping into `DinError` is a keystones
  concern (still under review).
- **Two phases, one branch, incremental commits** (config/log/web3, then ipfs/contracts).

---

## Ground rules discovered from the code

- **`config` already logs via `logger`** (`load_config` uses `logger.debug/error/warning`,
  `utils.py:163-171`) and `get_env_key`/`set_env_key` use `console.print`
  (`utils.py:254,258,268,281`). In `sdk.config`: keep the `logger` calls (via
  `logging.getLogger("dincli")`), and convert the 4 `console.print` → `logger.warning`. No
  `typer`/`rich` may remain, or the boundary test fails.
- **`sdk.log` bootstrap must be quiet on missing config (audit extra).** Today `log.py:26-33`
  runs at import: `get_config("log_level")` → `load_config()` → `logger.warning("No config
  found")` when absent — noisy, and emitted before handlers are fully set. Mitigation: in
  `sdk/log.py`, set up the handler first, then read the level via a defensive path that suppresses
  the missing-config warning (e.g. a private `_read_log_level()` that reads the file directly, or
  calls `load_config` with logging temporarily raised).
- **`utils.py:26` imports `get_contract_instance` from `contract_utils`**, which lazily imports
  `get_w3` (`contract_utils.py:122`). Post-move: `sdk/contracts.py` imports `get_w3` from
  `sdk/web3.py`; `cli/utils.py` re-exports both. No `sdk → cli` import remains.
- **`context.py:17` is `from dincli.cli.log import logger, logging`** and uses `logging.INFO`
  (`context.py:54`). So the `cli/log.py` shim must re-export **both** `logger` and stdlib
  `logging` (audit #1).
- **Constant inventory (`utils.py`):** move to `sdk.config` → `CONFIG_DIR`(32), `CACHE_DIR`(33),
  `WORKER_CACHE_DIR`(38), `CONFIG_FILE`(40), `ALLOWED_NETWORKS`(119),
  `SUPPORTED_IPFS_PROVIDERS`(120), `LEGACY_IPFS_PROVIDER_ALIASES`(122),
  `FILEBASE_IPFS_ADD/CAT/PIN_URL`(131-133). **Stay** in `utils.py` → `WALLET_FILE`(41),
  `WALLETS_DIR`(42), `LEGACY_WALLET_FILE`(44), `MIN_STAKE`(46), `_ACCOUNT_NAME_RE`(18),
  `_PASSWORD_TTL_DEFAULT`(19), `_UNSET`(24).
- **The boundary test walks all `sdk` submodules** — any new module importing `typer`/`rich`/
  `dincli.cli.*` turns it red.

---

## Phase 1 — `config` · `log` · `web3` (the dependency root)

### 1a. `dincli/sdk/config.py`
Move (implementations verbatim, minus presentation):

| Symbols | `utils.py` lines |
|---|---|
| `CONFIG_DIR`, `CACHE_DIR`, `WORKER_CACHE_DIR`, `CONFIG_FILE` | 32, 33, 38, 40 |
| `ALLOWED_NETWORKS`, `SUPPORTED_IPFS_PROVIDERS`, `LEGACY_IPFS_PROVIDER_ALIASES` | 119, 120, 122 |
| `FILEBASE_IPFS_ADD_URL` / `_CAT_URL` / `_PIN_URL` | 131–133 |
| `IPFSConfig` (dataclass) | 145 |
| `save_config`, `load_config`, `get_config` | 154, 161, 175 |
| `_clean_optional_string`, `normalize_ipfs_provider` | 180, 188 |
| `resolve_network`, `resolve_ipfs_config` | 195, 213 |
| `get_env_key`, `set_env_key` | 236, 263 |
| `resolve_network_value` | 284 |

- `logger = logging.getLogger("dincli")` at module top (no `sdk.log` import).
- Convert `console.print` (`254/258/268/281`) → `logger.warning`.
- No `typer`, no `rich`. `IPFSConfig` stays a plain dataclass.

### 1b. `dincli/sdk/log.py`
- Move `logger` + handler setup (`log.py:26-35`); read level via a **quiet** helper (ground
  rules). Delete the duplicate `load_config`/`get_config` (`log.py:10-24`), sourcing level from
  `sdk.config`.

### 1c. `dincli/sdk/web3.py`
- Move `get_w3` (`utils.py:331`); imports `resolve_network_value` from `sdk.config`. Keep
  `ConnectionError` (`# TODO(sdk-keystones): NetworkError`).

### 1d. Back-compat shims (full inventory — regenerate, don't hand-trust)
Before editing, regenerate the exact list of removed-symbol importers:
```
rg -n "from dincli\.cli\.utils import|dincli\.cli\.utils\.|from dincli\.cli\.log import" dincli tests
```
- **`cli/utils.py`:** delete moved defs; add, **above** the wallet-constant definitions (line ~41):
  ```python
  from dincli.sdk.config import (
      CONFIG_DIR, CACHE_DIR, WORKER_CACHE_DIR, CONFIG_FILE,
      ALLOWED_NETWORKS, SUPPORTED_IPFS_PROVIDERS, LEGACY_IPFS_PROVIDER_ALIASES,
      FILEBASE_IPFS_ADD_URL, FILEBASE_IPFS_CAT_URL, FILEBASE_IPFS_PIN_URL,
      IPFSConfig, save_config, load_config, get_config, _clean_optional_string,
      normalize_ipfs_provider, resolve_network, resolve_ipfs_config,
      get_env_key, set_env_key, resolve_network_value,
  )
  from dincli.sdk.web3 import get_w3
  ```
  Keep `WALLET_FILE`/`WALLETS_DIR`/`LEGACY_WALLET_FILE`/`MIN_STAKE` and all remaining functions.
- **`cli/log.py`:** replace body with **both** re-exports (audit #1):
  ```python
  import logging  # re-exported: dincli.cli.context does `from dincli.cli.log import logger, logging`
  from dincli.sdk.log import logger
  ```

---

## Phase 2 — complete the clean-seed (`ipfs` · `contracts`)

### 2a. `dincli/sdk/ipfs.py` (from `services/ipfs.py`)
- Redirect imports: `FILEBASE_*` + `resolve_ipfs_config` from `sdk.config`; `logger` from
  `sdk.log`; `get_cidv1base32_from_cid` from `sdk.cid`.
- Strip 3 `console.print("Uploading via …")` (`services/ipfs.py:168/171/174`) → `logger.info`.
- Keep `RuntimeError`/`ValueError` (`# TODO(sdk-keystones): IpfsError`).
- Shim `services/ipfs.py` → re-export from `sdk.ipfs`.

### 2b. `dincli/sdk/contracts.py` (from `cli/contract_utils.py`)
- Change lazy `from dincli.cli.utils import get_w3` (`122`) → `from dincli.sdk.web3 import get_w3`.
- Move `erc20_abi`/`router_abi` + `get_contract_instance`.
- Shim `cli/contract_utils.py` → re-export from `sdk.contracts`.

---

## Test migration (required — audit #3)

The re-export does not redirect a moved function's globals, so these must be repointed. **This
applies to both phases** — the same lesson, once for config functions, once for ipfs functions:

- **`tests/test_ipfs_config.py` — all cases.** Replace `monkeypatch.setattr(utils, "CONFIG_DIR"/
  "CONFIG_FILE", …)` (lines 15/16, 38/39, 92/93, 115/116, 132/133, 146/147, 160/161, 177/178,
  194/195) with the same on `dincli.sdk.config`. Import `from dincli.sdk import config as sdk_config`.
  The `.resolve_ipfs_config()` calls can stay via `utils` (re-export) or move to `sdk_config`.
- **`tests/test_connect_wallet.py::TestFixERegression::test_set_wallet_persists_config`** — it sets
  `utils_mod.CONFIG_FILE` then calls `utils_mod.load_config()` (line ~620). Repoint the patch to
  `sdk.config.CONFIG_FILE` (and call `sdk_config.load_config()`), since `load_config` moved.
- **Phase 2 — `tests/test_ipfs_config.py` ipfs patches (audit #3, one phase later).** After
  `services/ipfs.py` becomes a shim, `upload_to_ipfs`/`retrieve_from_ipfs` live in `sdk.ipfs` and
  resolve their globals there. Add `from dincli.sdk import ipfs as sdk_ipfs`; patch
  `sdk_ipfs.get_cidv1base32_from_cid` (lines 41, 95) and `sdk_ipfs.requests.post` (line 65); and
  call `sdk_ipfs.upload_to_ipfs()` / `sdk_ipfs.retrieve_from_ipfs()` (lines 67, 105, 106).
- **Unaffected (leave as-is):** `test_connect_wallet.py` patches of `utils_mod.get_env_key`/
  `get_config`/`getpass`/`time`/`_cleanup_stale_session` — their callers (`load_account`,
  `connect_wallet`, `_get_password`) stay in `utils.py`, so bare-name lookup still hits the
  re-exported name in the `utils` namespace. `system_mod.resolve_ipfs_config` patches also fine
  (patched in the CLI module's namespace).

These edits are legitimate: the code moved, so the tests patch where it now lives. Note them in
the commit so reviewers see the churn is expected.

---

## Testing

- **Keep the suite green** after each phase:
  `pytest tests/test_connect_wallet.py tests/test_dintoken.py tests/test_ipfs_config.py
  tests/test_cache_client_dp.py tests/test_sdk_boundary.py` (baseline 76 passed / 1 skipped).
- **Boundary test auto-covers new modules** — after Phase 2 it verifies `sdk.ipfs`/`sdk.contracts`
  pull in no `typer`/`rich`/`cli`.
- **New SDK unit tests** (`tests/test_sdk_config.py`, `tests/test_sdk_web3.py`):
  - `save_config`/`load_config` round-trip against a `tmp_path` `CONFIG_FILE` (patch
    `sdk.config`).
  - `resolve_network_value` precedence: `.env` > user config > default > `KeyError`.
  - `normalize_ipfs_provider`: **alias normalization + unknown pass-through** (behavior parity —
    it does NOT reject unknown providers; audit #5). `None → "env"`.
  - `get_w3` raises `ConnectionError` on unreachable RPC — patch `dincli.sdk.web3.Web3` (or the
    constructed instance) so `is_connected()` is `False`, rather than patching `Web3.is_connected`
    globally (less brittle).
- **Runtime smoke:** `dincli --help` loads; and
  `python -c "import dincli.cli.context, dincli.services.ipfs, dincli.cli.contract_utils,
  dincli.cli.utils"` — includes `cli.context` (audit extra), which exercises the `log` shim's
  `logger, logging` re-export.

---

## Risks & mitigations

- **Patched-globals breakage (audit #3)** — handled by the Test migration section above; the full
  suite run catches any missed site.
- **`config ↔ log` import cycle** — `config` uses stdlib `logging.getLogger` directly; only `log`
  imports `config`. One-directional.
- **Noisy/early `sdk.log` bootstrap** — quiet level-read helper; handler set up before level read.
- **Wallet constants orphaned by the config delete (audit #4)** — they stay in `utils.py`; the
  `sdk.config` re-export is placed above their definitions so `CONFIG_DIR` resolves.
- **`console.print` → `logger.warning` behavior drift** — warnings move from rich-stdout to the
  logger; acceptable for a library, no test asserts on those lines. Note in commit.
- **A missed importer** — regenerate the `rg` inventory (1d); shims + full suite + `--help` +
  the 4-module smoke import are the safety net.

---

## Out of scope (explicit)

- `manifest` + `runtime` — deferred to follow-up plan din-sdk-02 (IPFS retrieval + `din_info`).
- `wallet`/keystore, `state`/`validate_*`, `tx.send`, `DinSession`, `SignerProvider` — the
  **keystones**, encoding interface decisions still under review on #20.
- Wrapping stdlib exceptions into `DinError` (keystones step).
- Any CLI command refactor onto the SDK (role-operations step).

---

## Step checklist

- [ ] Regenerate the `rg` shim-inventory; confirm the 1d import list is complete
- [ ] Phase 1: create `sdk/config.py`, `sdk/log.py`, `sdk/web3.py`; console→logger; quiet bootstrap
- [ ] Phase 1: shims in `cli/utils.py` (above wallet consts), `cli/log.py` (logger + logging)
- [ ] Phase 1: migrate `test_ipfs_config.py` + `test_set_wallet_persists_config` to patch `sdk.config`
- [ ] Phase 1: full suite green + 4-module smoke + `--help` → commit
- [ ] Phase 2: move `services/ipfs.py` → `sdk/ipfs.py` + shim; migrate `test_ipfs_config.py` ipfs patches to `sdk.ipfs`
- [ ] Phase 2: move `cli/contract_utils.py` → `sdk/contracts.py` + shim
- [ ] Phase 2: boundary test covers ipfs/contracts; add `test_sdk_config.py`/`test_sdk_web3.py` → commit
- [ ] Push `feat/din-sdk`; consider the first incremental PR into `develop`

---

## Commit / PR plan

Two commits on `feat/din-sdk`:
1. `refactor(sdk): extract config/log/web3 loaders into dincli/sdk (#20)`
2. `refactor(sdk): move ipfs + contracts into dincli/sdk, completing clean-seed (#20)`

After these, `feat/din-sdk` holds a dependency-clean SDK foundation (cid, errors, config, log,
web3, ipfs, contracts) with the boundary test enforcing the layering — a natural **first PR into
`develop`** (honoring #20's "merge early" note) while keystones/operations continue behind it.
