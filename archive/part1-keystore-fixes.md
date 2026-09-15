# Implementation Plan — Part 1 Fixes: Keystore Security Review Follow-up

**Parent task:** `task_300626_3` (P3-T0.2b), implemented per `Plans/archive/part1-keystore-security.md` / `Plans/archive/part1-keystore-summary.md`
**Branch:** `feat/validator-readiness` (continue on same branch, new commits)
**Revision:** v2 — incorporates an external audit of v1 (4 confirmed implementation-detail corrections) plus empirical findings from actually installing deps and running the test suite for the first time (12/35 tests in `tests/test_connect_wallet.py` currently fail).
**Reviewer gate:** unchanged — Umer reviews before merge. Re-flag `needs-security-review` since fixes B and A touch the exact surfaces (`--wallet` resolution, demo-mode save) already under review.

---

## 0. Guiding principles

1. **Targeted fixes, no re-architecture.** Every finding gets the smallest change that closes it. Do not touch the wrapper schema, back-compat loading, or anything already verified correct in the Part 1 review.
2. **Every bug fix ships with a regression test that fails on the old code and passes on the new code.**
3. **Tests must actually run — not just "compile."** v1 of this plan said this too, but only as an aspiration. This revision was produced *after* actually installing deps (`.venv` had no `pip`; bootstrapped via `python -m ensurepip`, then `pip install -e .`) and running `pytest tests/test_connect_wallet.py`. Result: **12 of 35 tests fail.** Every one of those is now a named, root-caused item below — this is no longer a "should probably run tests" plan, it's a "here is exactly what's broken" plan.
4. **No invented facts in docs.** Any external-tool (OWS) claim must be verified against a primary source or phrased as "check upstream," never asserted outright.

### Decisions locked before coding

**D3 — Implement the missing `wallet_name` config writer rather than removing the config tier** (unchanged from v1). Add `dincli system set-wallet <name>`, mirroring `configure_network`'s existing pattern exactly.

**D4 — Validate account names at the lowest boundary function, not just at CLI entry points.**
v1 only validated `get_active_account_name()`'s output (i.e. names arriving via `--wallet` / `DIN_WALLET_NAME` / config). An external audit correctly pointed out that `load_account(name=...)` — a public `utils.py` function — reaches `resolve_wallet_path()` → `wallet_path_for_name()` with **no validation at all**, independent of how the name got there. Verified by reading the three functions directly: none of them call `validate_account_name`. Fix: put the validation inside `wallet_path_for_name()` itself, the one function every read and write path already funnels through. CLI-level validation (in `select_wallet` / `resolved_wallet_name`) stays too, for fast/friendly CLI errors — but the filesystem boundary no longer depends on every caller remembering to validate first.

---

## 1. Findings recap

### 1a. From the original code review (unchanged, still the core of this plan)

| # | Finding | File:line | Severity |
|---|---|---|---|
| A | `wallets/` dir never created before demo-mode's plain `open()` write → `FileNotFoundError` on any fresh install | `dincli/cli/system.py:400-402` | Critical |
| B | Name validation only wired to `connect-wallet --name`; `--wallet`/`DIN_WALLET_NAME`/config reach the filesystem unvalidated | `dincli/cli/utils.py:53-63` (`wallet_path_for_name`, `resolve_wallet_path`), `508-516` (`get_active_account_name`) | Security gap |
| C | `--keystore` import persists the raw outer file instead of the unwrapped keystore → double-wraps if the imported file was already dincli-wrapped | `dincli/cli/system.py:344` | Correctness bug |
| D | `wallet-setup.md` asserts an unverified `ows wallet export ...` command as fact | `Documentation/guides/wallet-setup.md` §2 Option B | Doc correctness |
| E | `keystore-migration.md` attributes `wallet_name` config persistence to `configure-network`, which never writes it; no command does | `Documentation/guides/keystore-migration.md` §6, `dincli/cli/system.py:212-223` | Doc inaccuracy / missing feature |

### 1b. From the audit of this plan's v1 (all 4 confirmed by direct inspection before coding)

| # | Finding | Evidence |
|---|---|---|
| F | `main.py` prints "Active Network" (line 66/68) **before** calling `ctx.obj.select_wallet(wallet)` (line 70) — so v1's "fails fast before other output" claim for invalid `--wallet` was false as written. | Read `dincli/main.py:60-70` directly. |
| G | `system.py` and `utils.py` both do `from getpass import getpass` (not `import getpass`), so `monkeypatch.setattr("getpass.getpass", ...)` does **not** intercept calls made from those modules — only `monkeypatch.setattr(system_mod, "getpass", ...)` / `monkeypatch.setattr(utils_mod, "getpass", ...)` does. | Confirmed via `grep` + empirical test run (§1c below). |
| H | The no-account-needed skip list in `system()`'s callback uses `"read_wallet"` and `"show_index"` (underscores), but Click/Typer's actual invoked-subcommand names are `read-wallet` (auto-hyphenated, no explicit name given) and `show-index` (explicit `@app.command("show-index")`). Pre-existing bug, unrelated to Part 1, but this plan already edits this exact line for `set-wallet`. | Read `@app.command()` decorators at `system.py:435` (`read_wallet`) and `system.py:561` (`show-index`) directly. |
| I | Test fixture teardown: `utils_mod.WALLET_FILE = orig_wallets = orig_config / "wallet.json"` reassigns the already-used `orig_wallets` variable — works by accident, reads as wrong. | Read `tests/test_connect_wallet.py:51` directly. |
| — | OWS's AES-256-GCM claim (which v1 flagged as unverified) is actually corroborated by multiple independent sources (MoonPay press release, PRNewswire, Morningstar) found via search — **keep it, cite the homepage**. Only the specific `ows wallet export ... --output ...` command syntax remains unconfirmed (OWS's own GitHub reference lists `create/list/info/sign/mnemonic`, no `export`). | WebSearch corroboration this session; softens finding D from "remove the whole claim" to "remove only the export command." |

### 1c. New — empirical: 12/35 tests in `tests/test_connect_wallet.py` fail when actually run

Ran `python -m ensurepip && pip install -e . && pip install pytest && pytest tests/test_connect_wallet.py -v`. Baseline result: **23 passed, 12 failed.** Root-caused each:

| Test | Root cause |
|---|---|
| `test_keystore_import_valid` | Finding G — patches `"getpass.getpass"`, doesn't intercept `system_mod.getpass`; real prompt hits pytest's stdin capture → `OSError`. |
| `test_keystore_import_wrong_password` | Same as above (Finding G). |
| `test_save_named_wrapper_schema` | Same (Finding G). |
| `test_name_validation_rejects_bad` | Same (Finding G). |
| `test_load_account_named_wallet` | Same (Finding G). |
| `test_load_account_legacy_fallback` | Same (Finding G). |
| `test_read_wallet_named_wallet` | `DummyCtxObj` test double has no `.account` attribute; `read_wallet`'s `ctx.obj.account.address` raises `AttributeError`, caught by `read_wallet`'s own except-block, re-raised as `typer.Exit(1)` — test doesn't expect an exit. New root cause, not previously flagged. |
| `test_todo_shows_named_wallet` | Unrelated **pre-existing** bug in `todo()`: `UnboundLocalError: cannot access local variable 'rpc_env_key'` at `system.py:770` — the `else` branch of an `if network: ... else: ...` references `rpc_env_key`, which is only assigned inside the `if` branch. Triggered because the test's `get_config` monkeypatch causes `network` to resolve falsy. Predates Part 1; newly exposed because Part 1 is the first thing to add a `todo()` test that reaches this code path. |
| `test_validate_account_name_invalid` | Test bug, not a product bug: `"abc" * 20` is **60** characters, not >64, so it's actually a *valid* name under `^[A-Za-z0-9_-]{1,64}$` and correctly doesn't raise. Verified `validate_account_name` itself correctly rejects `""`, `".."`, `"../"`, `"a/b"`, `"wallet name"`, `"/etc/passwd"` — the regex is fine. The test's too-long case just needs a string actually longer than 64 chars (e.g. `"a" * 65`). |
| `test_in_memory_password_cache` | Test bug: assumes `_get_password()` populates `_PASSWORD_CACHE` itself. It doesn't — only `_cache_password_in_memory()` does (called by `load_account`/`connect_wallet` after a successful decrypt, not by `_get_password`). Calling `_get_password()` twice in isolation just prompts twice. Test must call `_cache_password_in_memory()` explicitly or drive the scenario through `load_account`. |
| `test_clear_memory_cache` | Same misunderstanding as above — `_PASSWORD_CACHE` is never populated by the calls the test makes, so it's empty (`len == 0`) instead of the expected 2. |
| `test_list_accounts_command_empty` | `CliRunner(mix_stderr=False)` — the installed Click/Typer version's `CliRunner.__init__` doesn't accept `mix_stderr`. Version/API mismatch, not a logic bug. |

This table **is** the acceptance criteria for the test-fix commit: after fixes, all 12 must pass, unmodified passing tests must stay passing, and the new tests added for findings A–E must also pass.

---

## 2. Work breakdown

### 2.1 Fix A — create `wallets/` before demo-mode save (CRITICAL)

Unchanged from v1. In `system.py`'s demo-mode branch (`~line 394-402`), call `ensure_wallets_dir()` (already exists in `utils.py`, needs importing into `system.py`) immediately before opening `wallet_path_for_name(resolved_name)` for writing.

**Test:** from-scratch tmp dir that does **not** use the shared `temp_config` fixture (which pre-creates `wallets/` and hides this exact bug) — patch `CONFIG_DIR`/`WALLETS_DIR`/`WALLET_FILE` onto a bare empty directory, run `connect_wallet(demo_mode=True, account=0, ...)`, assert no exception and the file lands under `wallets/`.

---

### 2.2 Fix B — validate account names at the filesystem boundary (revised per D4)

**Files:** `dincli/cli/utils.py`, `dincli/cli/context.py`, `dincli/main.py`

1. **Boundary fix (new, per audit):** `wallet_path_for_name(name)` calls `validate_account_name(name)` first and uses its (stripped) return value to build the path. Since `resolve_wallet_path()` and `load_account()` both call `wallet_path_for_name()`, this makes path safety an invariant of the one function everything already funnels through — `load_account("../evil")` now raises `ValueError` before touching the filesystem, regardless of caller.
2. **CLI-level fixes (unchanged intent from v1, for fast/friendly errors):**
   - `get_active_account_name()` (`utils.py:508-516`): let `ValueError` from the boundary/validate call propagate (don't swallow).
   - `DinContext.resolved_wallet_name` (`context.py:86-89`): wrap in `try/except ValueError`, print red error, `sys.exit(1)` — mirrors the existing pattern in the `account` property.
   - `DinContext.select_wallet()` (`context.py:122-127`): validate the incoming `--wallet` value immediately; `console.print` + `raise typer.Exit(1)` on failure.
   - Centralize: `read_wallet`, `todo`, `list_managed_accounts` in `system.py` switch from calling `get_active_account_name(ctx.obj)` directly to `ctx.obj.resolved_wallet_name`, so the clean-exit path is in one place.
3. **Fail-fast ordering fix (Finding F, new):** in `main.py`, move `ctx.obj.select_wallet(wallet)` to run **before** the network-resolution/print block, so an invalid `--wallet` value exits before any console output — matching the acceptance language this plan actually intends, rather than leaving it order-dependent by accident. Confirmed safe: `select_wallet` has no dependency on network state.

**Acceptance:**
- `dincli --wallet '../evil' system list-accounts` exits 1 immediately, no other output printed first, no filesystem access outside `wallets/`.
- `DIN_WALLET_NAME=../evil dincli system todo` fails the same way.
- A hand-edited invalid `wallet_name` in `config.json` fails cleanly.
- Calling `load_account(name="../evil")` directly (bypassing all CLI plumbing) also raises `ValueError` before any file I/O — this is the specific gap the audit identified.
- Valid names: no behavior change.

**Tests:** invalid `--wallet` flag (assert nothing printed before the error and no stray file touched), invalid `DIN_WALLET_NAME`, invalid config `wallet_name`, and a direct unit test calling `utils_mod.load_account(name="../evil")` / `wallet_path_for_name("../evil")` asserting `ValueError` pre-filesystem-access.

---

### 2.3 Fix C — persist the unwrapped keystore on `--keystore` import

Unchanged from v1: `dincli/cli/system.py:344`, `inner_keystore = imported_ks` → `inner_keystore = inner_ks`.

**Test:** import an already-wrapped file via `--keystore`, assert the saved result is single-level (not nested) and `load_account()` succeeds afterward.

---

### 2.4 Fix D — remove only the unverified OWS command (revised: keep AES-256-GCM)

**File:** `Documentation/guides/wallet-setup.md` §2 Option B

- **Keep:** `ows wallet create --name <name>` (confirmed in OWS's own CLI reference) and the AES-256-GCM claim (corroborated by MoonPay's launch press release / PRNewswire / Morningstar coverage of OWS — cite `https://openwallet.sh/` as the source in the doc's footnote rather than asserting it bare).
- **Remove:** `ows wallet export --name ... --output ...` — not present in OWS's documented CLI subcommand list (`create/list/info/sign message/sign tx/mnemonic generate/mnemonic derive`). Replace with a note to check `ows --help` / `https://docs.openwallet.sh/` for the current export/import surface at time of use.
- Option A (`eth-account` one-liner) remains the primary, fully self-contained, tested path — unaffected either way.

**Acceptance:** no command in the doc that isn't in OWS's own published subcommand list; the encryption-algorithm claim is cited, not bare-asserted. No test possible (docs-only).

---

### 2.5 Fix E — implement `set-wallet`, fix the skip-list, correct the migration doc

**Files:** `dincli/cli/system.py`, `Documentation/guides/keystore-migration.md`

1. New command (mirrors `configure_network`):
```python
@app.command("set-wallet")
def set_wallet(ctx: typer.Context, name: str = typer.Argument(..., help="Wallet name to set as the persistent default")):
    """Persist a default named wallet for this machine (config wallet_name)."""
    console = ctx.obj.console
    try:
        resolved = validate_account_name(name)
    except ValueError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1)
    config = load_config()
    config["wallet_name"] = resolved
    save_config(config)
    console.print(f"[green]Default wallet set to '{resolved}'.[/green]")
```
2. **Finding H, while touching this exact area:** fix the no-account-needed skip list in `system()`'s callback (`system.py:74`) to use the real invoked-subcommand names — `"read-wallet"` and `"show-index"` (not the underscored `"read_wallet"`/`"show_index"` currently there), and add `"set-wallet"`. This is a pre-existing bug unrelated to Part 1, but left as-is it means `dincli system read-wallet`/`show-index` currently get forced through the "requires resolved account" path in `system()`'s callback before their own body ever runs — defeating the purpose of `read-wallet` (which is meant to work even to report "no wallet found").
3. Update `keystore-migration.md` §6 table row to reference `dincli system set-wallet <name>` instead of `configure-network`.

**Acceptance:** `dincli system set-wallet validator` persists `wallet_name` to `config.json`; subsequent commands with no `--wallet`/`DIN_WALLET_NAME` resolve to it; invalid name rejected with exit 1; `dincli system read-wallet` (hyphenated, the real command) is confirmed via a **CliRunner-based test** (not a direct function call) to skip the account-resolution gate even when no wallet exists yet.

**Test:** `test_set_wallet_persists_config`; and a new `TestSkipListRouting` class using `typer.testing.CliRunner` against the real `app` (not calling Python functions directly) invoking `system read-wallet`, `system show-index`, `system set-wallet` with no wallet configured, asserting they reach their own command bodies rather than failing in the parent callback's account-resolution step. This is the only way to actually catch Finding H's class of bug — every existing test in the file calls `system_mod.<command>()` as a plain function, which bypasses Click's routing entirely and can never detect a skip-list name mismatch.

---

### 2.6 Fix the 12 currently-failing tests + the fixture typo

**File:** `tests/test_connect_wallet.py`

Per the root-cause table in §1c:

- **Finding G (6 tests):** replace `monkeypatch.setattr("getpass.getpass", ...)` with `monkeypatch.setattr(system_mod, "getpass", ...)` in every test that drives `system_mod.connect_wallet`/`read_wallet`, and `monkeypatch.setattr(utils_mod, "getpass", ...)` where `utils_mod.load_account`/`_get_password` is exercised directly.
- **`test_read_wallet_named_wallet`:** give `DummyCtxObj` a real `.account` property/attribute (e.g. lazily calling `utils_mod.load_account(name=...)`, or a `SimpleNamespace(address=...)` set up by the test) instead of leaving it undefined.
- **`test_todo_shows_named_wallet`:** fix the actual product bug it exposed — `system.py:770`'s `else` branch references `rpc_env_key`, which only exists in the `if network:` branch above it. Initialize it before the `if`/`else` (or restructure so the `else` doesn't reference it). This is a pre-existing bug, unrelated to keystores, but it's now blocking a Part-1-added test and is trivial to fix while here.
- **`test_validate_account_name_invalid`:** fix the too-long case to an actually-too-long string (`"a" * 65`, not `"abc" * 20`).
- **`test_in_memory_password_cache` / `test_clear_memory_cache`:** fix the test's mental model — call `utils_mod._cache_password_in_memory(name, pw)` explicitly to populate the cache (matching how `load_account` actually uses it) before asserting cache-hit/cache-clear behavior, rather than expecting `_get_password()` to self-cache.
- **`test_list_accounts_command_empty`:** drop the unsupported `mix_stderr=False` kwarg from `CliRunner(...)` (or pin/check the installed Click version — the simplest fix is removing the kwarg since default behavior is fine here).
- **Finding I:** fix the fixture teardown typo — `utils_mod.WALLET_FILE = orig_config / "wallet.json"` (drop the confusing `orig_wallets =` reassignment).
- Add the new tests from 2.1–2.5.

**Then run for real and keep it real:**
```bash
python -m ensurepip --upgrade   # this repo's .venv ships without pip
python -m pip install -e .
python -m pip install pytest
python -m pytest tests/test_connect_wallet.py -v
python -m pytest                # full suite, confirm no collateral regressions
```
Capture the actual `X passed` output in the PR description — the standard this plan holds itself to, given Part 1's summary claimed tests "compile but were not executed."

---

## 3. Sequencing & commits

1. `fix(wallet): create wallets/ dir before demo-mode save` — Fix A, critical, standalone.
2. `fix(wallet): validate account names at the filesystem boundary; fail-fast --wallet before other output` — Fix B (+ Finding F reorder in `main.py`). **Security-sensitive — re-flag for Umer.**
3. `fix(wallet): persist unwrapped keystore on --keystore re-import of a wrapped file` — Fix C.
4. `feat(wallet): add system set-wallet command; fix read-wallet/show-index skip-list entries` — Fix E + Finding H.
5. `fix(cli): resolve pre-existing UnboundLocalError in todo() when network is unset` — called out separately since it's an unrelated legacy bug, not part of the keystore feature surface, uncovered incidentally by this work.
6. `docs(guides): remove unverified ows wallet export command from wallet-setup.md; cite AES-256-GCM source; fix wallet_name row in keystore-migration.md` — Fix D + doc half of Fix E.
7. `test(wallet): fix getpass patch targets, fixture typo, DummyCtxObj, CliRunner kwarg, cache/length test bugs; add CliRunner routing coverage; add regression tests for A/B/C/E; install deps and run full suite for real` — Fix 2.6, PR description includes real `pytest` output.

> Re-flag `needs-security-review`; ask Umer to specifically re-check commit 2 (name validation / path handling, now also at the filesystem boundary) and commit 1 (touches the demo-mode save path already reviewed once).

---

## 4. Definition of done

- All 5 original findings (A–E) fixed with a passing regression test each (D is docs-only, verified by reread against corroborated sources).
- All 4 audit findings (F–I) fixed.
- All 12 currently-failing tests pass; no previously-passing test regresses.
- `pytest` actually executed in this environment with real output captured in the PR (deps bootstrap steps included, since this repo's `.venv` needs `ensurepip` first).
- `wallet-setup.md` and `keystore-migration.md` contain no unverified or incorrect claims.

## 5. Files touched (summary)

**Modified:** `dincli/cli/system.py` (Fixes A, C, E, H — `ensure_wallets_dir()` call, `inner_ks` fix, new `set-wallet` command, corrected skip-list, `todo()` `rpc_env_key` bug), `dincli/cli/utils.py` (Fix B — validation moved into `wallet_path_for_name`), `dincli/cli/context.py` (Fix B — validation + clean exit in `resolved_wallet_name`/`select_wallet`), `dincli/main.py` (Fix F — reorder `select_wallet` before network print), `Documentation/guides/wallet-setup.md` (Fix D), `Documentation/guides/keystore-migration.md` (Fix E doc row), `tests/test_connect_wallet.py` (Fixes G, I, all new regression tests, all 12 failing-test corrections).

**Not touched:** wrapper schema, back-compat loading (`_extract_keystore`), atomic-write/permission logic, `.env.example` templates — all verified correct, out of scope.
