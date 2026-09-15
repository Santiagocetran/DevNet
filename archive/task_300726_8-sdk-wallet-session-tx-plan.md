# Implementation Plan — `sdk/wallet.py` + `sdk/session.py` + `sdk/tx.py`

**Task:** `task_300726_8` — SDK Wallet/Session/Tx Signing Keystone (issue #20)
**Thread:** [Discussion #67](https://github.com/InfiniteZeroFoundation/DevNet/discussions/67)
**Dates:** Jul 31 – Aug 6, 2026 (Fri, Mon, Tue, Wed, Thu — deadline Thu Aug 6)
**Base branch:** `feat/din-sdk` (PR #31, draft). `feat/din-daemon` receives **no code edits** — final merge-sync only.
**Spec refs:** proposal §2 (session/signer), §5b (tx keystone), §7 (back-compat), §10 (retry). Resolves `BL-2`, fixes `BL-1`.

---

> ## 🔶 STATUS: implemented at `90e0104`, then reviewed — fixes required
>
> This file remains the reference for **design intent**. For **what to fix**, see
> [`task_300726_8-remediation-plan.md`](task_300726_8-remediation-plan.md).
>
> Post-implementation review found the work structurally faithful here but **not functional against
> a real chain**: `send()` dies on any unmined transaction, and the CLI signs with the wrong wallet
> whenever the wallet name comes from env or config. Root cause of the latter: **§1c/§4a's CLI
> `SignerProvider` adapter was never built**, leaving two divergent account-resolution paths.
> Nothing is published; both PRs are drafts and `upstream` is untouched.

---

## ⚠️ Prerequisite — get on the right branch before reading further

**Every anchor, line number, and "already exists" claim in this plan is true on `feat/din-sdk`
and false on `develop`.** `develop` has **zero** files under `dincli/sdk/` — the whole SDK package
lives in unmerged PR #31. Reading this plan against a `develop` checkout will make it look wrong.

### ✅ Ground already prepared (2026-07-31) — do NOT redo these

| Item | State |
|------|-------|
| Branch | `feat/din-sdk` checked out, **`upstream/develop` already merged** (8 docs-only commits, no conflicts, no `.py` files touched — every line-number anchor in this plan survived) |
| Environment | **`~/.venvs/devnet`** (Python 3.12.3, `uv`-created, `pip install -e . pytest` done, web3 7.16.0) |
| Baseline `feat/din-sdk` | **144 passed** — reproduced on this machine, matches Umer's independent count exactly |
| Baseline `feat/din-daemon` | **213 passed** — the final sync merge was pre-tested and works; a merge commit already exists locally on that branch, **unpushed** |

**Run tests with the venv's interpreter explicitly** (there is no activated venv in a fresh shell,
and system `python3` has no `web3`):

```bash
~/.venvs/devnet/bin/python -m pytest -q \
    --ignore=tests/test_cache_client_dp.py --ignore=tests/dincli
```

`tests/test_cache_client_dp.py` needs `torch` (not installed, expected) and `tests/dincli/` is a
live-chain integration harness — both exclusions are environment gaps, not regressions. Use
`~/.venvs/devnet/bin/dincli` for CLI smoke checks.

> **144 and 213 are now verified facts on this machine, not quoted numbers.** If a run shows a
> different count, it is caused by your changes — do not rationalize it as pre-existing drift.

### ⚠️ No local chain available

`forge` / `anvil` / `cast` are **not installed**, and `hardhat/node_modules` is empty — so §5's
golden CLI-parity spot-check against a live local chain **cannot run as written**. Do not silently
skip it. Either:

1. ask Santiago to install one toolchain (`foundryup`, or `cd hardhat && npm install`), **or**
2. perform the parity check against a mocked w3 (assert the exact printed strings and exit codes for
   the deploy and registry-write call sites) and **explicitly report that the live-chain half of the
   §5 golden check was not performed**, so it can be flagged in the PR rather than implied done.

---

## ⚠️ Git workflow — read before the first commit

### Remotes (verified 2026-07-31)

| Remote | URL | Rule |
|--------|-----|------|
| `origin` | `git@github.com:Santiagocetran/DevNet.git` (the fork) | **push here, always** |
| `upstream` | `https://github.com/InfiniteZeroFoundation/DevNet.git` | **fetch only — NEVER push** |

`git push upstream <anything>` is forbidden without exception. All work reaches the org repo as a PR
from the fork, never as a direct push.

### Branch topology

```
origin/feat/din-sdk      <- work here; local is currently IN SYNC (0/0), nothing to pull
  └─ PR #31 (draft): Santiagocetran:feat/din-sdk -> InfiniteZeroFoundation:feat/din-sdk
origin/feat/din-daemon   <- stacked on the above; NO code changes this task
  └─ PR #32 (draft): Santiagocetran:feat/din-daemon -> InfiniteZeroFoundation:feat/din-sdk
```

`upstream/feat/din-sdk` (PR #31's base) is **36 commits behind** our branch — that's normal and
expected, it's what the PR diff is measured against.

### Rules

1. **Work on `feat/din-sdk`. Do not create a new feature branch** — PR #31 is already open against
   this exact branch name, and pushing to it updates the existing PR.
2. **Never commit to `develop`.** It's the local mirror of upstream and must stay clean.
3. **During implementation, push only `origin feat/din-sdk`.** This auto-updates PR #31 — **do not
   open a new PR.** The single exception is the final PR #32 sync block below, which pushes
   `origin feat/din-daemon` once, at the end.
4. **No rebase. No force-push. No history rewriting.** Umer reviewed PR #31 at commit `6eac109`; a
   rewrite invalidates that review and breaks the comment anchors. Merge commits are fine, rewritten
   history is not.
5. **Merging `upstream/develop` in is expected** (the task file explicitly says to re-pull since
   develop may have moved). It inflates the PR diff with develop-sync commits — PR #31's body
   already explains this, so it's not a surprise to the reviewer.
6. **`Plans/` is git-excluded** via `.git/info/exclude` — it is a local working directory. Do not
   `git add` it, and do not "fix" its untracked status.
7. **Commit messages:** conventional-commit subjects per §6, imperative mood, `(#20)` suffix, a body
   paragraph explaining the *why*, and a `Co-Authored-By:` trailer (matching existing history on this
   branch). Say **"unchanged call sites and return contracts"**, never "zero behavior change".

### `feat/din-daemon` — no code edits, final merge-sync only

No **code** changes at any point. But the deliverables require the suite green on both PRs, so at the
very end, once `feat/din-sdk` is complete:

```bash
git checkout feat/din-daemon
git merge feat/din-sdk          # sync onto the new tip — a merge commit, not a code change
pytest --ignore=tests/test_cache_client_dp.py --ignore=tests/dincli   # expect 213+ baseline
git push origin feat/din-daemon # keeps PR #32 from going stale/red
git checkout feat/din-sdk       # return to the working branch
```

If that merge surfaces conflicts or test failures, **stop and report** — do not fix them by editing
`dincli/dind/`, which is out of scope (boundary #4).

### Outward-facing actions — draft, don't publish

Two deliverables are visible to the team (the PR #31 body update, and the closing discussion post
plus the §9 questions). **Draft them as text for Santiago to review and post; do not run
`gh pr edit`, `gh pr comment`, or any discussion/comment API call.** Pushing commits to
`origin/feat/din-sdk` is authorized and expected; publishing prose under Santiago's name to a
colleague's review thread is not.

---

## 0. Anchors (verified 2026-07-31 against `feat/din-sdk` @ `6eac109`)

Everything below was read directly off the branch, not from the task file.

- **`errors.py` is already fully provisioned.** All six tx subcodes (`TX_ESTIMATION_FAILED`,
  `TX_REVERTED`, `TX_TIMEOUT`, `TX_NONCE_CONFLICT`, `TX_REPLACEMENT_UNDERPRICED`, `RECEIPT_MISSING`)
  plus `RPC_UNREACHABLE` exist as module constants; `SignerUnavailable`, `WalletError`,
  `NetworkError`, `TransactionError` classes all exist; `_ALLOWLIST` already carries
  `{"tx_hash": "hex", "nonce": "int", "broadcast": "bool"}` for every tx subcode — exactly §10's
  retry surface. The `ipfs_error` allowlist entry already exists too. **`errors.py` needs no changes
  at all this task.**
- **`build_and_send_tx`** (`cli/utils.py:452-501`): **57 call sites** across 15 modules (plus 15
  import lines and the definition = 73 matching lines; an earlier draft of this plan miscounted those
  73 as call sites). Callers read `receipt.transactionHash` (13×), `receipt.contractAddress` (5×),
  `receipt.status` (2×), and two `process_receipt(tx_receipt)` sites (`cli/task.py:279`, `:356`).
- **`system.py::send-eth` is a second, independent signing path** (`cli/system.py:747-757`): it calls
  `ctx.obj.get_tx_params()`, estimates, signs, broadcasts and waits **by hand**, never touching
  `build_and_send_tx`. See §3e — it constrains the BL-1 fix.
- **`load_account`** (`cli/utils.py:172-213`): password chain is env `DIN_WALLET_PASSWORD` →
  in-memory TTL cache (`_PASSWORD_CACHE`, 900s default) → `getpass`, plus a *second* `getpass` on
  cache-miss retry. Demo-mode wallets short-circuit to a plaintext `private_key`.
- **`DinContext`** (`cli/context.py:40-118`): lazy `network` / `config` / `w3` / `account` /
  `resolved_wallet_name`; `get_tx_params()` at `:111-118`; mutators `select_network` /
  `select_wallet` / `select_demo_account` at `:120-177`.
- **`sdk/web3.py:14`** carries `# TODO(sdk-keystones): NetworkError` — legitimately this task's
  (§2 requires `w3` to raise `NetworkError`). Distinct from `ipfs.py`'s mislabeled one (§9, item 5).
- **No timeout today**: `wait_for_transaction_receipt(tx_hash)` uses web3's default (120s).

### Decisions taken up front (confirmed 2026-07-31)

| # | Decision | Choice |
|---|----------|--------|
| D1 | `DinContext` integration depth | **Full delegation** — properties become thin wrappers over an internal `DinSession`; console/exit/prompting stay at the CLI edge |
| D2 | BL-1 nonce fix | **`pending` block param + in-process `NonceManager`** in `tx.py`; documented as not solving cross-process |
| D3 | Daemon `SignerProvider` adapter | **Reference impl under `tests/`** — real CLI adapter only; no code edits on `feat/din-daemon`; spec tension raised on #67 |
| D4 | Password-source boundary | **SDK owns the non-interactive sources** (env + TTL cache + decrypt); CLI adapter adds only `getpass` + retry messaging |
| D5 | `build_and_send_tx` return type | **Unchanged — still the raw web3 `AttributeDict`** (`info._raw`). Renaming to `TxReceiptInfo` fields would break all 57 call sites; migrating them is the `operations/` task's job |
| D6 | Timeout/polling (§5b Q3) | Explicit `timeout_s=120`, `poll_interval_s=0.1` params — today's web3 defaults, so no behavior change |

---

## 1. `dincli/sdk/wallet.py` (new)

Non-interactive keystore/account resolution. **Verbatim-extraction discipline** (same as `state.py`):
snapshot, move, diff.

### 1a. Moved verbatim from `cli/utils.py`

`_ACCOUNT_NAME_RE`, `validate_account_name` (`:51`), `wallet_path_for_name` (`:60`),
`resolve_wallet_path` (`:65`), `ensure_wallets_dir` (`:74`), `atomic_write_wallet` (`:82`),
`_extract_keystore` (`:102`), `get_demo_private_key` (`:122`), `get_demo_account_index` (`:146`),
`_PASSWORD_CACHE` / `_PASSWORD_TTL_DEFAULT` / `_UNSET`, `_cache_password_in_memory` (`:255`),
`_clear_memory_cache` (`:264`), and the `WALLET_FILE` / `WALLETS_DIR` / `LEGACY_WALLET_FILE` constants.

> ⚠️ **`validate_account_name` must keep raising `ValueError`, not `ValidationError`.**
> `context.select_wallet` (`:132`) and `context.resolved_wallet_name` (`:91`) both `except ValueError`.
> `DinError` derives from `Exception`, not `ValueError` — swapping the type silently breaks both
> catches. Keep the moved function byte-identical; raise SDK-native errors only in *new* code paths.

### 1b. New — the non-interactive core

```python
def resolve_password(name: str, *, env_pass=_UNSET) -> str | None:
    """Non-interactive half of utils._get_password: env var, then TTL cache.
    Returns None when neither source has one — the caller decides whether to prompt."""

def load_keystore(name: str) -> dict:
    """Read + validate the on-disk wallet. Raises WalletError (missing/malformed).
    No format or location change (§7)."""

def account_from_keystore(keystore: dict, password: str) -> LocalAccount:
    """Decrypt. Raises WalletError on bad password/corrupt keystore."""

def load_account_noninteractive(name: str = "default") -> LocalAccount:
    """load_account minus every prompt. Demo-mode plaintext short-circuit preserved.
    Raises SignerUnavailable when no non-interactive password source is available,
    WalletError when the keystore is missing/malformed or decryption fails."""
```

> ⚠️ **Error message strings must be verbatim copies of today's.** `context.account` prints
> `f"[red]Error loading account: {e}[/red]"` — the text comes straight off the exception. So
> `WalletError` must carry `"No wallet found for name '{name}' at {path}. Run `dincli system
> register-wallet --name {name}` first."` and `"Invalid password or corrupted keystore."` exactly.

`_cleanup_stale_session` (`:112`) **splits**: SDK does the `unlink()` and returns `bool`; the
`[dim]Removed stale .session cache…[/dim]` line stays in `cli/utils.py`. Deliberately avoids
repeating PR #31 review finding No. 1 (silent `console.print` → `logger` conversions).

### 1c. SignerProvider implementations (SDK-side, non-interactive)

```python
class KeystoreSigner:      # env + TTL cache only; never prompts
class PrivateKeySigner:    # raw key (demo mode / --demokey / daemon-injected)
```
Both satisfy the §2 protocol: `address()`, `can_decrypt()`, `sign_transaction(tx)`.

### 1d. `cli/utils.py` shim

Re-export everything moved. `load_account` stays in `cli/utils.py` as the *interactive* wrapper:
calls `load_account_noninteractive`, catches `SignerUnavailable`, prompts via `getpass`, keeps the
`[yellow]Cached password failed, prompting...[/yellow]` retry branch verbatim.

---

## 2. `dincli/sdk/session.py` (new)

```python
@runtime_checkable
class SignerProvider(Protocol):
    def address(self) -> str: ...
    def can_decrypt(self) -> bool: ...
    def sign_transaction(self, tx: dict) -> SignedTransaction: ...

class DinSession:
    """Lazily resolves network, web3, account, config. No printing, no exit, no prompts."""
    def __init__(self, network=None, wallet=None, signer=None): ...
    @property
    def network(self) -> str: ...
    @property
    def w3(self) -> Web3: ...          # raises NetworkError
    @property
    def account(self) -> LocalAccount: ...   # via signer; SignerUnavailable / WalletError
    @property
    def config(self) -> dict: ...
    @property
    def address(self) -> str: ...      # cheap — no decrypt, delegates to signer.address()
```

Default signer when none supplied: `KeystoreSigner(wallet_name)` — non-interactive, so a bare
`DinSession()` can never hang.

**Also closes `sdk/web3.py:14`:** `get_w3` raises

```python
raise NetworkError(msg, code=RPC_UNREACHABLE, details={"endpoint_host": rpc_url}) from e
```

instead of a bare `ConnectionError`.

> **Why the explicit subcode.** `errors.py` defines *both* `NetworkError.code =
> "network_unreachable"` and `RPC_UNREACHABLE = "rpc_unreachable"`, and `_ALLOWLIST` carries both
> with an identical `{"endpoint_host": "host"}` shape — so raising a bare `NetworkError` is
> syntactically fine but leaves consumers keying off the wrong string. Proposal §4 settles it:
> `network_unreachable` is the **base class code**, `rpc_unreachable` is the **reserved subcode** for
> RPC/network failures — exactly the `tx_failed` + tx-subcode pattern. An unreachable RPC endpoint is
> the subcode case, so always pass `code=RPC_UNREACHABLE`. Reserve the bare base code for
> non-RPC network failures. Retry policy and `to_envelope()` both key off `code`, so this is not
> cosmetic.

→ *Verify first:* `git grep -n "except ConnectionError" dincli/` must come back empty, else the CLI's
handling changes.

### Daemon adapter — documented contract (D3, and the §2 doc gap Umer flagged)

Docstring in `session.py` states plainly: the daemon's adapter is backed by **session-held state
bootstrapped once, interactively, at `dind start`** — held in memory for that daemon's lifetime.
Config changes mid-run arrive via a separate `dind config` command (interactive there is fine) plus a
non-interactive `dind load config` trigger; the daemon process itself **never blocks on stdin
mid-run**, and any missing credential raises `SignerUnavailable` for the job layer to turn into a job
error. Explicitly **not** a raw env-var lookup — that's the gap being closed. Building
`dind config` / `dind load config` is out of scope (boundary #5).

---

## 3. `dincli/sdk/tx.py` (new)

```python
@dataclass
class TxReceiptInfo:
    tx_hash: str; status: int; block_number: int; gas_used: int; nonce: int
    contract_address: str | None
    logs: list[dict]
    _raw: "TxReceipt" = field(repr=False, metadata={"json": "omit"})

def build_tx_params(session, overrides: dict | None = None) -> dict
def send(session, contract_function, *, tx_params=None, on_event=None,
         timeout_s=120.0, poll_interval_s=0.1) -> TxReceiptInfo
def decode_events(receipt: TxReceiptInfo, contract_event) -> list[dict]
```

`decode_events` wraps `contract_event.process_receipt(receipt._raw)` — this is what `cli/task.py:279`
and `:356` do by hand today.

### 3a. Nonce management — BL-1 (D2)

A single high-water mark **cannot** deliver both "N concurrent threads get N distinct nonces" and
"an unreported reservation self-heals". Bump the mark at reservation time and an abandoned nonce
leaves a permanent gap; bump it only after broadcast and concurrent reservers all read the same
`chain_pending` and collide. The two requirements need **three explicit states**, not one counter.

```python
RESERVATION_TTL_S = 90.0   # generous: reserve→broadcast is milliseconds (see note below)

class NonceManager:
    """Per-(chain_id, address) nonce allocation with an explicit state machine.

    Three states, all mutated under one per-account mutex:
      reserved  : dict[int, float]  — allocated, NOT yet broadcast (nonce -> reserved_at)
      inflight  : set[int]          — broadcast, not yet confirmed
      confirmed : implicit          — anything < get_transaction_count(addr, "pending")

    reserve(w3, addr):
        prune(w3, addr)                       # see below
        n = get_transaction_count(addr, "pending")
        while n in reserved or n in inflight:  # lowest free slot, so gaps get REFILLED
            n += 1
        reserved[n] = monotonic()
        return n

    prune(w3, addr):
        base = get_transaction_count(addr, "pending")
        drop every reserved/inflight entry < base            # chain confirmed them
        drop every reserved entry older than RESERVATION_TTL_S  # abandoned by a blind caller

    mark_broadcast(nonce): reserved.pop(nonce); inflight.add(nonce)
    release(nonce):        reserved.pop(nonce, None)   # pre-broadcast failure, immediate reclaim
    resync(w3, addr):      reserved.clear(); inflight.clear()   # nonce conflict: chain is truth
    """
```

**Why this satisfies both properties:**

- **Distinctness under concurrency** — `reserve()` scans for the lowest slot in neither `reserved`
  nor `inflight` and inserts before releasing the mutex, so two threads can never receive the same
  nonce regardless of what `chain_pending` reports.
- **Self-healing without leaks** — an abandoned reservation is reclaimed two ways: immediately if the
  caller calls `release()` (what `send()` does), or after `RESERVATION_TTL_S` via `prune()` for a
  caller that never reports back (§3f). Because `reserve()` picks the *lowest* free slot, the
  reclaimed nonce is handed out again and the gap is refilled rather than skipped.
- **Bounded stall.** The worst case for a blind abandoning caller is a `RESERVATION_TTL_S` window in
  which later txs queue behind the gap. 90s is deliberately generous relative to the real
  reserve→broadcast interval (milliseconds — the long wait is *after* broadcast, by which point the
  nonce has moved to `inflight`, which has no TTL). A reservation still held after 90s is
  overwhelmingly likely to be abandoned, not slow.

**Scope, stated not assumed:** this solves back-to-back and concurrent submission from **one
process** — the `dind` case (one daemon, many jobs, one account). It does **not** solve cross-process
collisions: two `dincli` invocations, or `dincli` alongside `dind`, still race. That needs a
file-lock or a chain-side strategy and belongs to the operations/daemon layer.

- `build_tx_params()` replaces `context.get_tx_params()`'s internals. **The literal BL-1 fix**: the
  nonce comes from the manager, which reads `block_identifier="pending"` instead of today's
  bare `get_transaction_count(address)` (defaulting to confirmed-only `"latest"`).
- Everything else in `get_tx_params` stays byte-identical: `maxFeePerGas = gas_price * 2`,
  `maxPriorityFeePerGas = max_priority_fee`, `chainId`, `from`.
- **Release discipline in `send()`:** `mark_broadcast()` immediately after `send_raw_transaction`
  returns; `release()` on any pre-broadcast failure; `resync()` on `tx_nonce_conflict`. These make
  reclaim *immediate*; the TTL sweep is the backstop for callers that don't report back, not the
  primary mechanism.

### 3b. `on_event` vocabulary (§5b Q2) — derived from CLI output ordering

Today's print order is: estimate → build → sign → **print `action_msg`** → broadcast →
**print tx hash/URL** → wait. So the event set has to include a pre-broadcast hook or the CLI
wrapper can't reproduce that ordering:

| Event | Payload | Fires |
|-------|---------|-------|
| `estimation_failed` | `{reason}` | `estimate_gas` raised |
| `broadcasting` | `{tx_hash, nonce}` | after signing, **before** `send_raw_transaction` |
| `submitted` | `{tx_hash, nonce}` | immediately after broadcast |
| `confirmed` | `{tx_hash, block_number, gas_used, status}` | receipt, `status == 1` |
| `reverted` | `{tx_hash, block_number}` | receipt, `status == 0` |
| `timeout` | `{tx_hash, nonce}` | wait exhausted |

`on_event` callbacks are wrapped in `try/except` — a buggy callback must never lose an already
broadcast transaction.

### 3c. The tx hash is known *before* broadcast — capture it there

`eth_account`'s `SignedTransaction` exposes `.hash` alongside `.raw_transaction`, so the hash is
computable the moment the tx is signed, without any network round-trip. Capture it there and thread
it through every subsequent path:

```python
signed = session.account.sign_transaction(tx)
tx_hash = signed.hash.hex()            # known pre-broadcast
_emit("broadcasting", {"tx_hash": tx_hash, "nonce": nonce})
```

This matters for §10 compliance. `send_raw_transaction` can fail with `"already known"` /
`"nonce too low"` **without returning a hash** — the node rejects the call. Those are precisely the
cases where the tx may already be in flight, so `broadcast=True` details *must* carry `tx_hash` for
the retry policy to confirm-rather-than-resend. Without the pre-broadcast capture there'd be nothing
to report, and the retry surface silently degrades exactly where it's most load-bearing.

### 3d. Failure → subcode mapping

| Failure | Subcode | `broadcast` | Also in details |
|---------|---------|-------------|-----------------|
| `estimate_gas` raises | `tx_estimation_failed` | `False` | `reason` |
| broadcast raises "nonce too low" | `tx_nonce_conflict` | `False` | `tx_hash` (§3c), `nonce` |
| broadcast raises "already known" | `tx_nonce_conflict` | **`True`** | `tx_hash` (§3c), `nonce` |
| broadcast raises "replacement transaction underpriced" | `tx_replacement_underpriced` | `False` | `nonce` |
| `TimeExhausted` | `tx_timeout` | `True` | `tx_hash`, `nonce` |
| receipt `status == 0` | `tx_reverted` | `True` | `tx_hash`, `nonce`, `block_number` |
| receipt is `None` | `receipt_missing` | `True` | `tx_hash`, `nonce` |

`"already known"` means the node has seen this exact raw tx — it *is* in flight, hence
`broadcast=True` and a mandatory `tx_hash`. `"nonce too low"` means it was rejected outright, so
`broadcast=False` and the nonce should be resynced.

### 3e. `logs` must be normalized, not passed through

`TxReceiptInfo.logs: list[dict]` is specified as "raw, **JSON-serializable** log entries", but web3
receipts hand back `AttributeDict` objects containing `HexBytes` values — neither survives
`json.dumps`. A bare `list(receipt.logs)` would ship an envelope that explodes at serialization time,
in the daemon, at the worst moment.

Normalize on construction: recursively map `AttributeDict → dict`, `HexBytes/bytes → "0x…"`, leave
ints alone (`serialize.py` handles `uint256` tagging downstream). Same treatment for `tx_hash` and
`contract_address` (checksummed). `_raw` keeps the untouched web3 object for `decode_events`, and is
`metadata={"json": "omit"}` so it never reaches the wire.

A test must assert `json.dumps(asdict_without_raw(info))` succeeds on an event-emitting receipt —
that's the actual contract, and nothing else in the suite would catch its violation.

### 3f. `send-eth` — the signing path `send()` cannot wrap

`cli/system.py:747-757` builds, signs, broadcasts and waits **by hand** for a raw ETH transfer.
`send()` can't absorb it: the signature takes a `contract_function`, and a value transfer has none.
Two consequences:

1. **The BL-1 fix reaches `send-eth` only through `DinContext.get_tx_params()` delegation** (§4a).
   If nonce allocation lived inside `send()` instead of `build_tx_params()`, this path would keep the
   old racy `"latest"` fetch and BL-1 would be only half fixed. This is the reason D2 puts the
   `NonceManager` behind `build_tx_params()` rather than inside `send()`.
2. **Nonce-leak hazard.** `build_tx_params()` reserves a nonce; `send()` releases it on pre-broadcast
   failure. `send-eth` has no such release — if its `estimate_gas` (line 750) or `sign_transaction`
   raises, the reserved nonce is never handed back and never used, leaving a permanent gap that
   wedges every later tx from that account in the same process.

**Mitigation — two layers, in this order:**

1. **Stop treating `send-eth` as permanently blind.** It's our code, so it can report back. Its
   existing `try/except` (`system.py:746`) gets `nonce_manager.release(...)` in the failure path and
   `mark_broadcast(...)` right after `send_raw_transaction` — mirroring what `send()` does. This is
   a few lines inside an existing exception handler with **no output change and no new exit path**,
   so it stays inside scope boundary #2. Immediate reclaim, no TTL wait.
2. **The TTL sweep (§3a) is the backstop, not the plan.** It exists so a *future* hand-rolled signing
   path that forgets to report back degrades to a bounded 90s stall instead of a permanent wedge.
   Correctness must not depend on every caller being well-behaved — but the caller we know about
   will be.

> Do **not** rely on layer 2 alone. The audit trail on this plan: an earlier draft tried to get both
> concurrency-distinctness and self-healing from a single high-water mark, which is impossible
> — see §3a. If `send-eth` is left blind, BL-1 is fixed only for `send()` callers.

Optionally expose `sdk/tx.py::send_value(session, to, amount_wei, ...)` so `send-eth` gets the same
error taxonomy — **stretch goal only**, after the deliverables; it touches a live money-moving path.

### 3g. Replacement transactions (§5b Q4) — the release valve

Per the task's own note, **do not build a `replace()` function**. Document in `send()`'s docstring:
replacing a stuck tx is a fresh `send()` call with an explicitly passed `tx_params={"nonce": n,
"maxFeePerGas": ...}`; the `NonceManager` honors a caller-supplied nonce override rather than
allocating. Nothing calls it yet. Cut this first if the week runs tight — **never** cut BL-1 or the
core `send()`/`SignerProvider` contract.

---

## 4. CLI rewiring — output-preserving

### 4a. `context.py` — full delegation (D1)

`DinContext.__init__` builds `self._session = DinSession(network=network_arg, wallet=...)`.
`network` / `config` / `w3` / `account` become thin wrappers; **every `console.print` + `sys.exit(1)`
/ `typer.Exit(1)` stays exactly where it is**. `select_network` / `select_wallet` /
`select_demo_account` invalidate and rebuild the session (`select_demo_account` injects a
`PrivateKeySigner`, keeping its demo-mode gate + messaging in the CLI). `get_tx_params()` delegates
to `tx.build_tx_params(self._session)`.

`account`'s existing `except Exception → print → sys.exit(1)` already catches `SignerUnavailable` and
`WalletError` — no change needed there, given §1b's verbatim message strings.

### 4b. `build_and_send_tx` — thin wrapper, identical output (D5)

Returns `info._raw` (raw `AttributeDict`) on success; `None` on failure when
`exit_on_failure=False`. Print mapping, preserving today's **inconsistent glyphs**:

| Condition | Exact output today (must be reproduced) |
|-----------|------------------------------------------|
| estimation failure | `[bold red] X Transaction estimation failed: {e}[/bold red]` |
| revert (`status == 0`) | `[bold red] X {error_msg}[/bold red]` — **no** `Exception:` line |
| any other failure | `[bold red]✗ {error_msg}[/bold red]` + `[bold red]Exception: {e}[/bold red]` |
| success | `[bold green] ✓ {success_msg}[/bold green]` |

> ⚠️ **Truncation trap.** `sanitize_details` caps `reason` at 256 chars, so printing from
> `err.details["reason"]` would silently truncate long revert strings. Raise with
> `raise TransactionError(str(e), code=..., ...) from e` and have the wrapper print from
> `err.__cause__` (falling back to `err.message`) so `{e}` renders byte-identically.

`get_en_w3_account_console()` still fires first on every call (wallet + RPC lines), and
`print_tx_info` moves into the `submitted` handler — same position in the stream.

---

## 5. Tests

- **`tests/test_sdk_wallet.py`** — keystore round-trip against the existing on-disk format (wrapper,
  bare, and demo shapes via `_extract_keystore`); `resolve_wallet_path` legacy-`default` fallback;
  env-var and TTL-cache resolution paths; `SignerUnavailable` when neither source has a password;
  `WalletError` on missing/corrupt keystore and bad password; **`getpass` monkeypatched to raise** —
  proves the non-interactive path never reaches it.
- **`tests/test_sdk_session.py`** — lazy resolution (no RPC call until `.w3` is touched);
  `NetworkError` on unreachable RPC; `SignerProvider` `runtime_checkable` conformance for both SDK
  signers; **the daemon reference adapter (D3)** — a non-interactive fixture provider asserting
  `SignerUnavailable` instead of a hang; a fresh-subprocess check with **stdin closed** that
  constructing and resolving a `DinSession` never blocks.
- **`tests/test_sdk_tx.py`** — `send()` happy path against a mock w3 (`TxReceiptInfo` fields,
  `contract_address` on a deployment-shaped receipt, `logs` on an event-emitting one); each subcode
  from §3d on its matching failure; `broadcast` / `tx_hash` / `nonce` correctness on at least one
  pre-broadcast and one post-broadcast failure; **`"already known"` yields `broadcast=True` *with* a
  `tx_hash` even though the node returned none** (§3c); **`json.dumps()` round-trip over the
  `_raw`-less dataclass on an event-emitting receipt** (§3e — nothing else in the suite catches an
  `AttributeDict`/`HexBytes` leak); the full `on_event` sequence and ordering; `on_event` raising
  doesn't break `send()`; `decode_events` against a mock receipt.
- **`tests/test_sdk_tx.py::TestNonceManager`** — the two properties must be tested *separately*,
  since the whole point of §3a's state machine is that one formula can't give both:
  1. **Distinctness:** N threads calling `reserve()` against a frozen `chain_pending` get N distinct
     nonces (`len(set(results)) == N`) — catches the "bump only after broadcast" failure mode.
  2. **Gap refill:** reserve → abandon → advance the clock past `RESERVATION_TTL_S` → the next
     `reserve()` returns **the same nonce**, not `n+1` — catches the "bump at reservation" failure
     mode. Inject a clock rather than sleeping 90s.
  3. `release()` reclaims immediately without waiting for the TTL.
  4. `prune()` drops entries below `chain_pending` once the chain confirms them.
  5. `resync()` clears both sets and re-reads the chain.
  6. `mark_broadcast()` moves a nonce `reserved → inflight`, and `inflight` entries are **not**
     TTL-expired (only `reserved` is) — a tx waiting 5 minutes for confirmation must keep its nonce.
- **`tests/test_sdk_tx.py::TestSendEthNoncePath`** — the `send-eth` constraint (§3f): assert
  `DinContext.get_tx_params()` allocates through the shared `NonceManager` (not a bare
  `get_transaction_count`), so BL-1 is fixed on the manual signing path too; assert the failure path
  calls `release()` (layer 1) and that even without it the next allocation is not wedged (layer 2).
- **`tests/test_sdk_boundary.py`** — extend the asserted module set to `session`, `wallet`, `tx`.
- **Golden CLI parity (§7)** — by hand, not just the suite: capture stdout/stderr + exit code before
  and after for (a) a deploy call site (`dindao.py` — exercises `contract_address`) and (b) a
  registry write (`task.py` — exercises `process_receipt`), on local anvil. Diff must be empty.
- Full suite green (144 baseline + new) on `feat/din-sdk`, and re-verified on `feat/din-daemon`
  after it's re-synced.

---

## 6. Commit sequence

| # | Commit | Day |
|---|--------|-----|
| 1 | `feat(sdk): add dincli/sdk/wallet.py — non-interactive keystore/account resolution (#20)` + `cli/utils.py` shim + tests | Fri |
| 2 | `feat(sdk): add dincli/sdk/session.py — DinSession + SignerProvider (#20)`; `web3.py` raises `NetworkError` | Mon |
| 3 | `refactor(cli): interactive signer adapter; DinContext delegates to DinSession (#20)` | Mon–Tue |
| 4 | `feat(sdk): add dincli/sdk/tx.py — send()/decode_events() + NonceManager (#20)` + tests | Tue–Wed |
| 5 | `fix(sdk): allocate nonces from pending via NonceManager (BL-1) (#20)` | Wed |
| 6 | `refactor(cli): build_and_send_tx wraps sdk.tx.send (#20)` + golden parity checks | Wed–Thu |
| 7 | `docs(design): record §5b resolutions (event vocabulary, timeouts, replacement) (#20)` | Thu |

Commit messages say **"unchanged call sites and return contracts"**, never "zero behavior change" —
per PR #31 review finding No. 1.

---

## 7. Risks / watch-items

1. **57 call sites** — D5 (raw receipt return) is what keeps this from becoming a 15-module diff. Any
   drift to `TxReceiptInfo` breaks 20 attribute reads plus two `process_receipt` sites.
2. **`ValueError` catch sites** — §1a's warning. Grep `except ValueError` in `cli/` before moving.
3. **Verbatim message strings** — §1b. `context.account` renders exception text directly to console.
4. **`pending` semantics vary by provider** — anvil and OP Sepolia differ on what's in the pending
   pool. Verify the BL-1 fix on both, not just local.
5. **`getpass` hanging CI** — every new test either monkeypatches it to raise or runs with stdin closed.
6. **Delegation blast radius (D1)** — `DinContext` is on the path of *every* command. Commit 3 lands
   alone, with the full suite run before and after.
7. **256-char `reason` truncation** — §4b's trap.
8. **Nonce leaks via non-`send()` paths** — §3f. `send-eth` reserves without reporting back; the
   self-healing `reserve()` is what prevents a permanent gap. Any *future* hand-rolled signing path
   inherits this hazard — grep for `sign_transaction(` before shipping to confirm `send-eth` is
   still the only one.
9. **Plan is branch-scoped** — see the prerequisite block. Re-verify anchors after the
   `upstream/develop` merge; `develop` moved 8 commits since PR #31's HEAD.

---

## 8. Definition of done (task deliverables)

- [ ] `sdk/session.py` — `DinSession` + `SignerProvider`, daemon-adapter contract documented as
      session-held/bootstrapped (not raw env lookup)
- [ ] `sdk/wallet.py` — non-interactive resolution extracted; old call sites re-exported as shims
- [ ] `sdk/tx.py` — `send()` + `decode_events()` + param building; `build_and_send_tx` a thin wrapper
      with identical exit codes and output
- [ ] BL-1 fixed in the nonce fetch, approach documented
- [ ] §5b Q2/Q3/Q4 resolved in docstrings/code, not deferred to a doc
- [ ] New SDK tests; boundary test covers `session`, `wallet`, `tx`
- [ ] Existing suite green on both branches; no CLI behavior change
- [ ] Commits pushed to `origin/feat/din-sdk` (this auto-updates PR #31), **plus a drafted PR #31
      body update** handed to Santiago noting the slice covers §2/§5b — *publishing is Santiago's step*
- [ ] **Drafted** closing discussion post + the §9 questions, prepared for Santiago to review and
      post on #67, flagging `sdk/operations/` + plan/apply (§6) as the deferred next slice

> The task file lists these last two as "PR #31 updated" and "Discussion posted". Those deliverables
> close when **Santiago posts**; the agent's deliverable is the reviewed-and-ready draft. See the
> "draft, don't publish" rule in the git-workflow section.

---

## 9. Items to raise on #67 before starting

Bundle into one comment — none of these block the work:

1. **Spec tension (D3):** item 1 says the daemon adapter "lives in `dincli/dind/`", but the
   base-branch note says `feat/din-daemon` gets no changes. Going with a reference impl under
   `tests/` — confirm that's the intent.
2. **Deliverable posting target:** deliverable line 144 says post the closing discussion on **#50**,
   but that's the previous task's closed thread. Assuming #67 with a cross-link to #50.
3. **Three untracked `dind` gaps** from the PR #32 review (TOCTOU, healthcheck can't see `degraded`,
   no persistent log file) — Umer asked these be tracked "now"; only BL-9 landed. Drafted BL-10/11/12
   rows ready to paste.
4. **PR #32 quick fixes** (broken `dind.service` specifiers, `server_close()`, `resource_snapshot`
   type hint) — offer to land them, noting it deviates from "no changes on that branch".
5. **PR #31 finding No. 5** — the mislabeled `TODO(sdk-keystones): IpfsError`. Proposing to fold the
   fix in here (three `RuntimeError` → `IpfsError` swaps; the `ipfs_error` allowlist entry already
   exists in `errors.py`) since the TODO names this task.
6. **`send-eth` (§3f)** — a second signing path the task file doesn't mention, which `send()` can't
   wrap. Confirming the intent is BL-1-via-`get_tx_params()` (what this plan does) rather than a
   `send_value()` addition to `tx.py` that would touch a live money-moving path this week.

---

*Pre-flight commands are in the prerequisite block at the top of this plan.*
