# Implementation Plan — PR #16 review fixes #2, #3, #5

**Branch:** `feat/validator-readiness`
**Scope:** the three open review items from Umer's "Code review — Part 1" comment that
still need work (bugs #1 and #6 already ported in commit `634ce1e`).
**Status:** DRAFT — for audit before implementation.

All three touch already-merged `develop` code, so each fix is written to be
cherry-pickable on its own. No Lighthouse/Part-2 files are involved.

---

## Audit decisions (resolved before implementation)

- **[High — fixed in this revision] `yes` is unsafe for direct callers if omitted.**
  With `yes: bool = typer.Option(False, ...)`, a *direct* `connect_wallet(...)` call that
  omits `yes` receives a truthy `OptionInfo`, so `not yes` would **bypass** the guard on an
  existing target. This is an unsafe *API default*, not just a test artifact. Fix: normalize
  to a real bool at the top of the function — `yes = yes if isinstance(yes, bool) else False`
  (chosen over `Annotated[bool, ...]` to keep the option style consistent with the rest of
  `connect_wallet`/`send_eth`). A regression test must cover the **omitted-`yes`** direct
  call on an existing target, not only `yes=False`.
- **[Low — fixed in this revision, lighter design] Guard placement.** The overwrite prompt must
  come *after* non-secret input validation and *before* any secret prompt. Rather than
  restructuring the whole function, hoist only the keystore *non-secret* validation
  (`expanduser`/`exists`/`json.load`/`_extract_keystore` — **no `getpass`, no `Account.decrypt`**)
  above the guard, and place the guard just before the existing `if/elif` chain. This fixes the
  keystore, interactive, and create-password paths; `--key-file`/`--account` (dev-tier) keep a
  documented prompt-then-fail quirk. Chosen to minimize diff on this security-sensitive,
  already-reviewed function.
- **[Accepted] Legacy-default existence check** (#2): keep `wallet_path_for_name(...).exists()`.
  It intentionally does not prompt for the non-destructive legacy→named migration; the caveat
  is documented below.
- **[Accepted] `DIN_WALLET_PASSWORD` honored for new wallets** (#3): the bug is stale
  in-memory cache reuse, not the explicit automation env var. Only the cache is ignored.

---

## Ground rules discovered from the code + tests

- `tests/test_connect_wallet.py` calls `system_mod.connect_wallet(**kwargs)` **directly**
  (not through `CliRunner`). When a Typer command function is called directly, unpassed
  parameters take their *signature default*, which for `typer.Option(...)` is an
  `OptionInfo` object (truthy), **not** the option's nominal value. Therefore:
  - Any new option must be **optional** and existing behavior must not depend on it
    resolving to its nominal default in direct calls.
  - Because `OptionInfo` is **truthy**, `not yes` would *bypass* the guard on a direct call
    that omits `yes`. The new `yes` option must be **normalized to a real bool** inside the
    function before it's used (`yes = yes if isinstance(yes, bool) else False`).
  - The overwrite guard (#2) also keys on **file existence**, so it's inert whenever the
    target doesn't pre-exist (which is every current create/import test).
- `_get_password` / `_cache_password_in_memory` are unit-tested directly with positional
  args and a monkeypatched `get_env_key(key, verbose=None)`. New parameters must be
  keyword-only-ish optionals with defaults that preserve the current call signatures.
- `get_env_key()` re-parses `.env` from disk on **every** call (`dincli/cli/utils.py:246-249`,
  `dotenv_values`) — no memoization. This is the root of #5.

---

## Fix #2 — Overwrite confirmation guard on `connect-wallet --name <existing>`

**Problem.** `connect_wallet` writes to `wallet_path_for_name(resolved_name)` in both the
demo branch (`system.py:419-425`) and the encrypted branch (`system.py:448-449`) with no
existence check. Re-running `connect-wallet <key> --name aggregator` silently replaces a
real validator keystore. (`develop` `dc6ff23` has the same gap.)

**Design.**
- Add option to `connect_wallet`:
  `yes: bool = typer.Option(False, "--yes", "-y", help="Skip overwrite confirmation")`.
  A bypass flag is **required** (not optional nicety): `connect-wallet` is used in
  automated/demo flows; a hard prompt with no bypass would hang non-interactive callers.
  This mirrors `send-eth`, which the review cited as the pattern.
- **Normalize `yes` immediately** (first lines of the function body, right after `console`):
  ```python
  yes = yes if isinstance(yes, bool) else False   # direct calls pass OptionInfo (truthy)
  ```
  Without this, a direct `connect_wallet(...)` omitting `yes` gets a truthy `OptionInfo` and
  `not yes` silently skips the guard on an existing target — an unsafe API default.

- **Lighter placement (chosen): hoist only the keystore *non-secret* validation above the
  guard, and put the guard immediately before the main `if/elif` input chain.** No full
  restructure of the function — minimizing the diff on this security-sensitive, already-reviewed
  code is the priority. Concretely:

  1. **Keystore non-secret pre-validation** (only when `keystore is not None`), moved up to run
     right after the mutual-exclusivity check:
     - `keystore.expanduser()` → `exists?` (exit 1 if not) → `open`/`json.load` (exit 1 if
       unreadable/malformed) → `_extract_keystore()` (exit 1 if unrecognizable).
     - Hold the resulting `inner_ks`; set `source = "imported"`.
     - **Do NOT `getpass` the passphrase and do NOT `Account.decrypt` here** — those are secret
       operations and must stay after the guard (preserves the "no secret prompt before the
       overwrite decision" rule).
  2. **Overwrite guard**, placed before the main `if/elif` chain:
     ```python
     target_path = wallet_path_for_name(resolved_name)
     if target_path.exists() and not yes:
         console.print(f"[yellow]A wallet named '{resolved_name}' already exists at {target_path}.[/yellow]")
         if not typer.confirm("Overwrite it?"):
             console.print("[yellow]Aborted. Existing wallet left unchanged.[/yellow]")
             raise typer.Exit(0)
     ```
  3. **Existing `if/elif` chain and crypto/write run unchanged, after the guard.** Because the
     chain now runs after the guard, the interactive private-key `getpass` (`system.py:398`) and
     the create/confirm wallet password (`system.py:432-437`) both occur *after* the overwrite
     decision. The keystore branch consumes the already-extracted `inner_ks` and only then does
     `getpass("Keystore passphrase")` → `Account.decrypt(...)`.

  **Cases this fixes:**
  - existing wallet + `--keystore`: file/JSON/shape validated → confirm → passphrase. ✅
  - existing wallet + interactive: confirm → private-key prompt. ✅
  - existing wallet + create password: confirm → create/confirm password. ✅
  - direct call with `yes` omitted: covered by the `isinstance` normalization above. ✅

  **Docstring/help cleanup (required):** the `connect_wallet` docstring currently reads
  *"In demo mode (--yes), stores plaintext key for Hardhat testing."* Once `--yes/-y` means
  "skip overwrite confirmation," that line is actively misleading — demo mode is config-driven,
  not controlled by `--yes`. Change it to *"In configured demo mode, stores plaintext key for
  Hardhat testing."*

  **Implementation detail — no re-read/re-parse:** the post-guard keystore branch must consume
  the already-extracted `inner_ks` (and `source="imported"`) from the hoisted pre-validation. Do
  **not** re-`open`/`json.load`/`_extract_keystore` the file after the guard — that keeps the
  diff small and avoids a time-of-check/time-of-use gap between validation and use.

  **Accepted remaining quirk (documented, not fixed now):** `--key-file missing.key` and a
  missing `ETH_PRIVATE_KEY_<n>` are resolved *inside* the `if/elif` chain, i.e. after the guard,
  so they can prompt about overwrite before surfacing the missing-input error. These are
  dev/testing-tier paths (per the task's tier table); restructuring the whole function just to
  reorder them is not worth the added diff/regression risk on this file.

- **Existence check uses `wallet_path_for_name(...).exists()`**, i.e. the exact file about
  to be written — precisely "will this destroy an existing keystore file."
  - *Known limitation (accepted, documented):* if `name == "default"` and only the legacy
    `wallet.json` exists (no `wallet_default.json`), the guard does not fire. That path writes
    a *new* `wallet_default.json` (which then wins on load) without deleting the legacy file —
    a non-destructive migration, not an overwrite. Conscious choice, per audit decision.
- Uses `typer.confirm` (returns bool) rather than `_confirm_or_exit` (raises on "no", no
  bypass) because we need the `--yes` bypass and an explicit `Exit(0)` (clean abort, not
  error). Same shape as `send-eth`'s confirmation.

**Test compatibility.** All existing create/import tests target fresh names in a temp config
→ `target_path.exists()` is False → guard inert regardless of `yes`. Confirm during
implementation that no existing test connects twice on the *same* name (a normalized
`yes=False` would newly prompt there). ✅

**New tests:** `test_connect_wallet_overwrite_*`
- **Omitted `yes` on an existing target** (the audit-requested case): pre-create
  `wallet_prod.json`, call `connect_wallet(...)` for `name="prod"` **without passing `yes`**,
  `typer.confirm` monkeypatched → `False`; assert `typer.Exit` and original file bytes
  unchanged. (Proves the `OptionInfo` normalization works.)
- `yes=False` explicit + `typer.confirm` → `False`: assert `Exit(0)` and file unchanged.
- `yes=False` explicit + `typer.confirm` → `True`: assert file replaced (new address).
- `yes=True`: assert overwrite proceeds and `typer.confirm` is **not** called (spy).
- **No prompt on doomed input:** `connect_wallet(..., keystore=Path("missing.json"), name="prod")`
  with `wallet_prod.json` pre-existing and `typer.confirm` spied → assert `Exit(1)` and
  `typer.confirm` **not** called (proves the reorder — validation precedes the guard).

---

## Fix #3 — Force create/confirm password path for a new wallet (no stale-cache reuse)

**Problem.** In the encrypted create branch, `password = _get_password(resolved_name, False)`
(`system.py:431`) returns a **cached** password for `resolved_name` if one exists (from a
prior `load_account(resolved_name)` in the same process). `password != ""` then **skips**
the "Create wallet password / Confirm password" flow (`system.py:432-437`), so a brand-new
or overwritten wallet gets silently encrypted with a previously-cached password the user
never re-chose. Real for daemon/programmatic reuse; the review asked for an explicit
`is_new_wallet` flag.

**Design.** Add `is_new_wallet: bool = False` to `_get_password`:

```python
def _get_password(name="default", prompt=True, is_new_wallet=False, env_pass=_UNSET):
    _cleanup_stale_session()
    if env_pass is _UNSET:
        env_pass = get_env_key("DIN_WALLET_PASSWORD")
    if env_pass:
        return env_pass          # deliberate automation path — preserved
    if not is_new_wallet:
        # existing in-memory cache lookup (unchanged)
        ...
    if prompt:
        return getpass("Enter wallet password: ")
    return ""
```

- `connect_wallet` create path becomes `_get_password(resolved_name, False, is_new_wallet=True)`.
  With no env var set → returns `""` → existing inline create/confirm getpass flow runs
  (unchanged). The **cache is never consulted** for new-wallet creation.
- **`DIN_WALLET_PASSWORD` env is still honored** for new wallets. The review's risk is the
  *incidental* cache hit, not the *deliberate* env var (PR deviation D1 documents env as the
  intended no-reprompt automation path). Ignoring only the cache kills the footgun while
  keeping automated wallet creation working.
- `env_pass=_UNSET` sentinel is shared with fix #5 (below) — one signature change covers both.

**Test compatibility.** `is_new_wallet` defaults to `False`; all existing `_get_password`
tests keep the cache path. `test_save_named_wrapper_schema` (create path) has no env and no
cache seeded → returns "" → create/confirm getpass (monkeypatched) → unchanged. ✅

**New test:** seed `_PASSWORD_CACHE["prod"]` with a password, then call
`connect_wallet(..., name="prod", ...)` on a fresh name with `system_mod.getpass`
monkeypatched to a *different* password; assert the saved keystore decrypts with the
getpass password, **not** the cached one.

---

## Fix #5 — Eliminate the double `.env` parse per wallet unlock

**Problem.** `load_account` → `_get_password` calls `get_env_key("DIN_WALLET_PASSWORD")`
(`utils.py:439`); then `_cache_password_in_memory` calls it **again** (`utils.py:457`).
`get_env_key` re-parses `.env` from disk each time, so one unlock = two full `.env` parses,
on a path that runs on nearly every `dincli` invocation touching an account.

**Design — fetch once, inject via sentinel (no global memoization).** Global memoization of
`get_env_key` is rejected: it's a shared helper used for many keys and tests monkeypatch
`.env`/env between calls in one process — caching would break correctness/tests.

- Add `env_pass=_UNSET` to both `_get_password` (already shown above) and
  `_cache_password_in_memory`:

```python
def _cache_password_in_memory(name, password, env_pass=_UNSET):
    if env_pass is _UNSET:
        env_pass = get_env_key("DIN_WALLET_PASSWORD")
    if env_pass:
        return
    ...
```

- `load_account` fetches once and threads it:

```python
env_pass = get_env_key("DIN_WALLET_PASSWORD")     # single parse
password = _get_password(name, env_pass=env_pass)
try:
    private_key = Account.decrypt(keystore_data, password)
    _cache_password_in_memory(name, password, env_pass=env_pass)
    ...
```

- Result: **one** `.env` parse per unlock in the hot path. The retry branch
  (`utils.py:417-424`) can thread the same `env_pass` too for consistency.
- `_UNSET` module sentinel (`_UNSET = object()`) so callers that don't inject (and the
  existing unit tests) behave exactly as before — the functions self-fetch. Fully
  backward-compatible with the monkeypatched `get_env_key(key, verbose=None)` signature.

**Test compatibility.** Existing `_get_password` / `_cache_password_in_memory` / `load_account`
tests pass no `env_pass` → self-fetch path → unchanged. ✅ Optionally add a test asserting
`get_env_key` is called exactly once during `load_account` (spy/counter) to lock in the fix.

---

## Files touched

| File | Fixes | Change |
|---|---|---|
| `dincli/cli/system.py` | #2, #3 | `--yes/-y` option + `yes` normalization; hoist keystore non-secret validation above a new overwrite guard placed before the `if/elif` chain (keystore passphrase/decrypt stay after the guard); `is_new_wallet=True` at the create-path `_get_password` call. Lighter than a full reorder — the `if/elif` chain and crypto/write are otherwise unchanged. |
| `dincli/cli/utils.py` | #3, #5 | `_UNSET` sentinel; `is_new_wallet` + `env_pass` params on `_get_password`; `env_pass` param on `_cache_password_in_memory`; single env fetch threaded through `load_account` |
| `tests/test_connect_wallet.py` | #2, #3, #5 | overwrite guard (3 cases), stale-cache-not-reused, single-env-parse spy |

## Commit strategy

Three focused commits (cherry-pickable into `develop` independently), or one combined —
recommend **three**:
1. `fix(wallet): confirm before overwriting an existing named keystore (#2)`
2. `fix(wallet): force create/confirm password path for new wallets, ignore cache (#3)`
3. `perf(wallet): parse .env once per unlock instead of twice (#5)`

## Validation

- `.venv/bin/python -m pytest tests/test_connect_wallet.py -q` → expect 46 existing + new tests green.
- Manual: create `wallet_prod.json`, re-run `connect-wallet --name prod` → prompt; `--yes` → no prompt.

## Out of scope

- Lighthouse / Part 2 (blocked on Discussion #18).
- OWS hands-on spike (separate track / decision pending).
- Bug #4 (Lighthouse 402) — architectural, not a code fix.
