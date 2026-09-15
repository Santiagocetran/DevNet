# Remediation Plan — `task_300726_8` post-implementation fixes

**Companion to:** [`task_300726_8-sdk-wallet-session-tx-plan.md`](task_300726_8-sdk-wallet-session-tx-plan.md) (the original design plan — still the reference for *intent*; this file is the reference for *what to fix*)
**Reviewed at:** `90e0104` on `feat/din-sdk` (pushed to `origin` fork; PR #31 draft head)
**Reviewed:** 2026-07-31 · env `~/.venvs/devnet` · suite reproduces at **232 passed**
**Status of the work:** structurally faithful to the plan, **not functional against a real chain**. Two chain-fatal defects, two contract defects, plus mediums.

> Nothing is published. Zero comments on PR #31, PR #32, or Discussion #67. `upstream` is untouched
> (`feat/din-sdk` and `feat/din-daemon` both still at `805ce9d`). Both PRs remain drafts. Fixes push
> in place — no force-push, no retraction needed.

---

## 0. How each finding was established

Every item below was **reproduced**, not inferred from reading. Evidence is recorded so a fixer can
re-run it and so nothing here has to be re-litigated.

| # | Claim | Evidence |
|---|-------|----------|
| R1 | `send()` dies on any unmined tx | Realistic mock (raise `TransactionNotFound` twice, then a receipt) → `RAISED: TransactionNotFound`. Confirmed `RPC.eth_getTransactionReceipt: raise_transaction_not_found` in `web3/_utils/method_formatters.py:1189` |
| R2 | Wrong wallet signs | `DIN_WALLET_NAME=alice` → `ctx.resolved_wallet_name='alice'` vs `ctx.session.signer._wallet_name='default'` |
| R3 | Missing wallet → wrong message | `load_account('no-such-wallet')` → `ValueError: Invalid password or corrupted keystore.` (was `FileNotFoundError: No wallet found for name…`) |
| R4 | Protocol-conforming adapter crashes | The documented reference `DaemonAdapter` → `isinstance(SignerProvider)=True`, `session.address` OK, `session.account` → `AttributeError: no attribute 'local_account'` |
| R5 | CLI signer adapter missing | `ls dincli/cli/signer.py` → not found; no `Interactive*Signer` anywhere in `dincli/` |
| — | `hexbytes` 1.3.1 `.hex()` returns **unprefixed** | `HexBytes(b'\x124').hex() -> '1234'` |

---

## 1. Root cause — two systemic misses, not ten unrelated bugs

Fix these two and most of the list collapses.

### RC-1 — The CLI `SignerProvider` adapter was never built

Original plan §1c/§4a specified **two adapters**: an SDK-side non-interactive `KeystoreSigner`, and a
**CLI adapter that wraps it and adds `getpass`**, injected into the session. Commit 3 was scoped as
*"interactive signer adapter; DinContext delegates to DinSession"* — **only the delegation half
landed**. `dincli/cli/signer.py` does not exist.

Consequence: two parallel account-resolution paths that never agree —

```
DinContext.account   → load_account()          → get_active_account_name()  → honors env/config
DinSession.account   → KeystoreSigner(wallet)  → ctx.wallet_name (--wallet only) → "default"
```

That single omission produces **R2** (wrong signer), **M1** (double scrypt decrypt), and is why
`send-eth` allocates a nonce for one address and sets `from` to another.

### RC-2 — Mocks encode a web3 contract that does not exist

`test_sdk_tx.py:427` asserts `get_transaction_receipt.return_value = None`. Real web3 **raises**
`TransactionNotFound`. The test suite validated the bug instead of catching it. The live-chain golden
parity check — the one the task file singled out as non-negotiable *precisely because* mocks can't
catch this class of defect — was skipped.

**Both root causes are "the plan was followed structurally but not at the seam."** The fixes below
close the seams.

---

## 2. Blockers — must fix before this is shown to anyone

### R1 — `send()` cannot wait for a receipt · `sdk/tx.py:336-349` · CRITICAL

```python
receipt = w3.eth.get_transaction_receipt(tx_hash)   # RAISES TransactionNotFound
if receipt is not None: break                        # never reached on an unmined tx
```

Every real transaction raises a bare `TransactionNotFound` out of `send()` — not a
`TransactionError`, no subcode, no `broadcast` flag, no retry surface. The timeout branch and
`poll_interval_s` are unreachable. All 57 `build_and_send_tx` call sites are broken on-chain;
successful txs would print `✗ {error_msg}` + `Exception: Transaction with hash … not found`.

**Fix** — use web3's own waiter and give `RECEIPT_MISSING` its real meaning (see R7):

```python
from web3.exceptions import TimeExhausted, TransactionNotFound
try:
    receipt = w3.eth.wait_for_transaction_receipt(
        tx_hash, timeout=timeout_s, poll_latency=poll_interval_s)
except TimeExhausted as e:
    # distinguish "still pending" from "dropped from the mempool"
    try:
        w3.eth.get_transaction(tx_hash)
    except TransactionNotFound:
        _emit(on_event, "receipt_missing", {"tx_hash": tx_hash, "nonce": nonce})
        raise TransactionError(..., code=RECEIPT_MISSING,
                               details={"tx_hash": tx_hash, "nonce": nonce, "broadcast": True}) from e
    _emit(on_event, "timeout", {"tx_hash": tx_hash, "nonce": nonce})
    raise TransactionError(..., code=TX_TIMEOUT,
                           details={"tx_hash": tx_hash, "nonce": nonce, "broadcast": True}) from e
```

`timeout_s=120.0` already matches web3's default, so D6's no-behavior-change property holds.

**Tests:** mock `get_transaction_receipt`/`wait_for_transaction_receipt` to raise
`TransactionNotFound` on the first N polls and succeed after — must return a `TxReceiptInfo`, not
raise. Add a `TimeExhausted` → `tx_timeout` case and a dropped-tx → `receipt_missing` case. **Delete
the `return_value = None` mock** — it asserts a contract web3 does not have.

### R2 — Signs with the wrong wallet · `cli/context.py:60` · CRITICAL

`DinSession(wallet=self.wallet_name)` where `wallet_name` is set **only** by `select_wallet()`
(`--wallet` flag). Users on the documented persistent-wallet flow (`dincli system set-wallet alice`,
or `DIN_WALLET_NAME`) get alice's address **printed** and the **default** wallet's key **signing**,
with `from` and the nonce both from the wrong address.

**Fix:** implement RC-1 (§3, R5). Interim one-liner if RC-1 is deferred:
`DinSession(wallet=self.resolved_wallet_name, …)`. **The interim fix alone still leaves the double
decrypt and two divergent code paths** — prefer R5.

**Test:** integration test asserting `ctx.session.signer` resolves the *same* wallet name as
`ctx.resolved_wallet_name` across all four sources: `--wallet`, `DIN_WALLET_NAME`, config
`wallet_name`, and the `"default"` fallback.

### R3 — Missing wallet reports "Invalid password" · `cli/utils.py::load_account` · HIGH

`except WalletError` collapses *missing keystore* and *bad password* into the password branch;
`_clear_memory_cache` returns `False` with no cache → `ValueError("Invalid password or corrupted
keystore.")`. A new user with no wallet is told their password is wrong. Violates scope boundary #2
and the plan's §1b verbatim-message rule.

**Fix:** separate the cases. Either add a distinct `WalletNotFound(WalletError)` subclass raised by
`load_keystore` when `resolve_wallet_path` reports absent, and re-raise it as today's
`FileNotFoundError` text; or check `resolve_wallet_path(name)` before the `except WalletError`
recovery and re-raise. `sdk/wallet.py` already carries the correct message verbatim — only the CLI
wrapper's dispatch is wrong.

**Test:** `load_account('no-such-wallet')` raises with the **exact** legacy string; assert the full
message, not the exception type alone.

### R4 — `SignerProvider` protocol is violated by its own consumer · `sdk/session.py:118` · HIGH

`session.account` calls `signer.local_account`, which is **not in the Protocol**
(`address`/`can_decrypt`/`sign_transaction`). `runtime_checkable` only checks method presence, so a
conforming adapter passes `isinstance` and then dies at `tx.py:262` (`account = session.account`) —
the first line of every `send()`. The documented reference `DaemonAdapter` in
`test_sdk_session.py` has no `local_account`; its test passes only because it never touches
`.account`. **D3's whole purpose was to prove this contract works, and it does not.**

**Fix — pick one, don't straddle:**
- **(a) Preferred:** drop `session.account` from the signing path. `send()` needs only
  `signer.sign_transaction(tx)` and `session.address`; nothing requires a `LocalAccount`. This makes
  hardware wallets / remote signers possible later, which is the point of the Protocol.
- (b) Add `local_account` to the Protocol and to the reference adapter — simpler, but permanently
  couples every signer to `eth_account`.

**Test:** extend the reference-adapter test to drive a **full `send()`** through it, not just
`session.address`.

---

## 3. High

### R5 — Build the missing CLI signer adapter (RC-1) · new `dincli/cli/signer.py`

```python
class InteractiveKeystoreSigner:
    """CLI SignerProvider: wraps the SDK's non-interactive KeystoreSigner and
    adds the getpass boundary. The ONLY place in the codebase allowed to prompt."""
    def __init__(self, wallet_name: str): ...
    def address(self) -> str: ...
    def can_decrypt(self) -> bool: ...
    def sign_transaction(self, tx: dict): ...
```

Resolution order preserved verbatim: env `DIN_WALLET_PASSWORD` → TTL cache → `getpass` → on
`WalletError` with a live cache, `[yellow]Cached password failed, prompting...[/yellow]` + one retry.

Then `DinContext` injects it and **`DinContext.account` delegates to `session.account`** — one
resolution, one decrypt, one wallet name. `load_account` stays as a thin back-compat shim over the
adapter (57 call sites and `system.py` depend on it).

Closes R2 and M1 structurally.

### R6 — Generic broadcast failure mislabeled · `sdk/tx.py:328`

Any unrecognised broadcast exception → `code=TX_ESTIMATION_FAILED` ("best-effort fallback"), but
estimation already succeeded. Daemon retry keys off `code`. Use the base `tx_failed`.

> Also reconsider `broadcast=False` here. A socket timeout during `send_raw_transaction` **may**
> have reached the node. §10's contract is that `broadcast` distinguishes "safe to rebuild" from
> "must confirm the existing tx" — asserting `False` on an unknown outcome is the unsafe direction.
> Recommend `broadcast=True` with `tx_hash` (known pre-broadcast per §3c) for unclassified broadcast
> exceptions, and document the conservative choice.

### R7 — `RECEIPT_MISSING` imported, never raised · `sdk/tx.py:25`

A required deliverable subcode is unimplemented and untested (also imported-unused in the test file).
Given real meaning by R1's fix: broadcast, then dropped from the mempool.

### R8 — `"nonce too low"` emits `submitted` · `sdk/tx.py:303`

Fires the `submitted` event for a **rejected** tx. The CLI maps `submitted` → `print_tx_info`, so the
user gets a transaction hash and a block-explorer URL for a transaction that never existed. Remove
the emit (the `broadcast=False` details are the correct signal); keep it only on the `already known`
path, which genuinely is in flight.

---

## 4. Medium

| ID | Issue | Location | Fix |
|----|-------|----------|-----|
| M1 | Double account resolution → 2× scrypt (~100-1000ms each); works only because `ctx.account` warms the TTL cache first | `cli/utils.py::build_and_send_tx` | Falls out of R5 |
| M2 | `release()` is the only mutator without the mutex | `sdk/tx.py:175` | `with self._mutex:` |
| M3 | Dead, incoherent expression: `is_already_known = … or "nonce too low" in msg_lower and _NONCE_TOO_LOW in msg_lower` — unused, second clause tautological | `sdk/tx.py:299` | Delete |
| M4 | `_resolve_w3` duplicates `sdk/web3.py::get_w3` verbatim — two divergent paths | `sdk/session.py:46` | Call `get_w3` |
| M5 | `signed.hash.hex()` is **unprefixed** (hexbytes 1.3.1) so events/pre-sanitize details carry `abc…` while `TxReceiptInfo.tx_hash` carries `0xabc…` | `sdk/tx.py:290` | `"0x" + signed.hash.hex()`. *CLI output parity is unaffected — the old code also printed unprefixed* |
| M6 | `decode_events` returns raw `AttributeDict`s despite `-> list[dict]`; not JSON-safe, so the future `operations/` layer hits the §3e problem again | `sdk/tx.py:386` | Run results through `_normalize_log` |
| M7 | Docstring garbled — "A reference implementation … lives under tests/ — it is the real CLI adapter only" is a mangled paste of the plan's D3 row, in a security-contract docstring | `sdk/session.py:22-24` | Rewrite |
| M8 | `except typer.Exit: release(nonce)` runs *after* `mark_broadcast` — a no-op that reads as a bug | `cli/system.py:770` | Drop, or move before |
| M9 | `from_receipt` hardcodes `nonce=0`, patched by the caller — a direct construction silently yields `nonce=0` | `sdk/tx.py:85` | Make `nonce` a required parameter |
| M10 | `_normalize_log(...) -> dict` but returns `str` for bytes | `sdk/tx.py:40` | Annotate `-> Any` |

---

## 5. Test-strategy fixes (RC-2) — the part that actually prevents recurrence

Patching the ten items above without this leaves the next regression equally invisible.

1. **Delete mocks that encode false web3 contracts.** Audit every `w3.eth.*` mock against real web3
   semantics. Known offender: `get_transaction_receipt.return_value = None`. Rule: a mock's failure
   mode must be the one web3 actually produces (raise vs return).
2. **Integration tests at the CLI↔SDK seam, not just unit tests either side.** Every blocker lives at
   a seam — `DinContext`↔`DinSession` (R2), `load_account`↔`load_keystore` (R3),
   `SignerProvider`↔`send()` (R4). Add a `tests/test_cli_sdk_integration.py`: wallet-name agreement
   across all four sources, error-message parity for missing/bad-password/corrupt keystore, and a
   full `send()` through a non-`eth_account` signer.
3. **Run the golden live-chain parity check** (task-file mandated, previously skipped):
   ```bash
   curl -L https://foundry.paradigm.xyz | bash && foundryup   # not installed
   ./foundry/anvil.sh
   ```
   Capture stdout/stderr + exit code before (`4ab0114`) and after for a deploy call site
   (`dindao.py` — exercises `contract_address`) and a registry write (`task.py` — exercises
   `process_receipt`). **Diff must be empty.** If foundry can't be installed, say so explicitly in
   the PR — do not let "232 passed" imply this was covered.
4. **A test that fails on today's code for each blocker**, written *before* the fix. If a proposed
   test passes at `90e0104`, it does not cover the bug.

---

## 6. Commit sequence

Small, reviewable, each independently green. `feat/din-sdk`, push to `origin` only, no rebase.

| # | Commit | Closes |
|---|--------|--------|
| 1 | `test(sdk): add failing tests for receipt-wait, wallet propagation, signer protocol` | proves R1/R2/R4 |
| 2 | `fix(sdk): wait for receipts via wait_for_transaction_receipt; implement receipt_missing (#20)` | R1, R7 |
| 3 | `feat(cli): add InteractiveKeystoreSigner; DinContext resolves accounts via session (#20)` | R5, R2, M1 |
| 4 | `fix(cli): distinguish missing keystore from bad password in load_account (#20)` | R3 |
| 5 | `refactor(sdk): sign via SignerProvider only; drop local_account from the signing path (#20)` | R4 |
| 6 | `fix(sdk): correct tx error subcodes, event emission, and nonce-manager locking (#20)` | R6, R8, M2, M3, M5, M9 |
| 7 | `refactor(sdk): session reuses get_w3; normalize decode_events output (#20)` | M4, M6, M7, M8, M10 |
| 8 | `test: CLI↔SDK seam integration + live-chain parity results (#20)` | §5 |

---

## 7. Definition of done

- [ ] Each blocker has a test that **fails at `90e0104`** and passes after
- [ ] `send()` completes a real transaction on anvil, end to end
- [ ] Wallet-name agreement verified across `--wallet` / `DIN_WALLET_NAME` / config / default
- [ ] `load_account` missing-wallet message byte-identical to `4ab0114`
- [ ] A full `send()` runs through a signer with **no** `local_account`
- [ ] Every `TransactionError` subcode — including `receipt_missing` — raised and tested
- [ ] Golden live-chain parity: deploy + registry-write diffs empty, **or** the gap explicitly stated
- [ ] Suite green on both branches (≥232 / ≥301), `dincli --help` OK
- [ ] Pushed to `origin` only; `upstream` untouched; PRs still drafts; **nothing published**

---

## 8. Do not regress these — they were done right

`NonceManager`'s three-state machine is faithful (TTL on `reserved` only, lowest-free-slot scan for
gap refill), and its tests genuinely cover distinctness and gap-refill *separately* with an injected
clock. `wallet.py`'s extraction is verbatim with messages preserved — R3 is the CLI wrapper's
dispatch, not the SDK. `build_and_send_tx` preserves the `" X "` vs `"✗"` glyph split and prints
estimation failures from `__cause__` (avoiding the 256-char truncation trap). **D5 holds** —
`info._raw` returned, all 57 call sites untouched. `logs` normalization + the `json.dumps` test are
correct. The import-boundary test is extended and real.
