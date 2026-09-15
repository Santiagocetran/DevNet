# DRAFT — PR #31 body update (for Santiago to review and post)

---

**Draft / WIP — progress on #20.** Base is `feat/din-sdk` (not `develop`).

## What's new in this update — `task_300726_8`, the wallet/session/tx signing keystone

Implements proposal **§2** (session/signer) and **§5b** (the `send()` keystone), resolving
[`BL-2`](../BACK_LOG.md) and fixing [`BL-1`](../BACK_LOG.md).

### Modules

- **`dincli/sdk/wallet.py`** — non-interactive keystore/account resolution extracted from
  `cli/utils.py` + `cli/system.py`, same on-disk keystore format. Plus `KeystoreSigner` and
  `PrivateKeySigner`.
- **`dincli/sdk/session.py`** — `DinSession` + the `SignerProvider` protocol. Lazy network / `w3` /
  account / config, no printing, no exit, **no prompts**.
- **`dincli/sdk/tx.py`** — `send()`, `decode_events()`, `build_tx_params()`, and a `NonceManager`.
- **`dincli/cli/signer.py`** — the CLI adapter, the only component permitted to prompt.

### BL-1 — nonce management

`get_tx_params()` fetched the nonce with no block param (`"latest"`, confirmed-only), so two
transactions fired back-to-back collided. Now allocated by a `NonceManager` with an explicit
three-state machine:

- `reserved` (allocated, not broadcast) — carries a 90s TTL so an abandoned reservation self-heals
- `inflight` (broadcast, unconfirmed) — **no** TTL; a tx waiting minutes for confirmation keeps its nonce
- confirmed — implicit, anything below `get_transaction_count(addr, "pending")`

`reserve()` scans for the lowest free slot under a mutex, so concurrent callers get distinct nonces
*and* a reclaimed nonce refills its gap rather than being skipped. A single high-water counter cannot
give both properties, which is why this is a state machine rather than an increment.

**Scope, stated rather than assumed:** this solves concurrent submission from one process (the `dind`
case — one daemon, many jobs, one account). It does **not** solve cross-process collisions; two
`dincli` invocations, or `dincli` alongside `dind`, still race. That belongs to the operations layer.

`send-eth` (`system.py`) is a second signing path that `send()` cannot wrap — its signature takes a
`contract_function` and a value transfer has none — so it allocates through `get_tx_params()` and now
reports back to the manager.

### The other three §5b open questions

- **`on_event` vocabulary:** `estimation_failed`, `broadcasting`, `submitted`, `confirmed`,
  `reverted`, `timeout`, `receipt_missing`. The set is derived from CLI output ordering — `action_msg`
  prints after signing but before broadcast, which is why a pre-broadcast `broadcasting` event exists.
  Callbacks are wrapped so a buggy consumer can never lose an already-broadcast transaction.
- **Timeout/polling:** explicit `timeout_s=120.0` / `poll_interval_s=0.1` — web3's existing defaults,
  so wait behaviour is unchanged.
- **Replacement transactions:** no `replace()` function. A fresh `send()` with
  `tx_params={"nonce": n, "maxFeePerGas": …}` — `build_tx_params` honours a caller-supplied nonce
  instead of allocating. Documented in `send()`'s docstring; nothing calls it yet.

### Back-compat

`build_and_send_tx` keeps returning the **raw web3 receipt**, not `TxReceiptInfo` — 57 call sites read
`.transactionHash` / `.contractAddress` / `.status`, plus two `process_receipt` sites. Migrating them
belongs with `operations/`. Exit codes and printed output are unchanged, including the inconsistent
`" X "` vs `"✗"` glyphs.

Per the review note on the previous slice, the claim here is **unchanged call sites and return
contracts** — not "zero behavior change".

## Review-and-fix cycle

The first implementation of this slice was structurally faithful to the design but **could not complete a
transaction against a real chain** — it broadcast successfully, then failed while waiting for
confirmation. A self-review before requesting yours found and fixed:

| | |
|---|---|
| `send()` could not wait for a receipt | `get_transaction_receipt` **raises** `TransactionNotFound` for an unmined tx; it never returns `None`. The polling loop tested for `None`, so the first poll of any real transaction escaped as a bare web3 error with no subcode. Now uses `wait_for_transaction_receipt` |
| Signed with the wrong wallet | The session was built from the `--wallet` flag only, so a wallet set via `DIN_WALLET_NAME` or config `wallet_name` was **displayed** while the *default* key **signed**. Root cause: §1c/§4a's CLI signer adapter was never built, leaving two divergent resolution paths |
| Missing wallet reported as bad password | A user with no wallet was told their password was wrong |
| `SignerProvider` unusable | `send()` reached `signer.local_account`, which is not in the protocol — a conforming daemon or hardware adapter passed `isinstance` then died on the first line of `send()` |

Also: unclassified broadcast failures were labelled `tx_estimation_failed` (estimation had already
succeeded); `"nonce too low"` emitted `submitted`, so the CLI printed a hash and explorer URL for a
transaction that was **rejected**; `receipt_missing` was imported and never raised; `release()` was the
only nonce mutator without the mutex.

**`broadcast=True` on unclassified broadcast failures is deliberate.** A socket timeout during
`send_raw_transaction` may have reached the node. §10 uses that flag to choose between "safe to
rebuild" and "must confirm, don't resend" — on an unknown outcome, `False` risks a double-send while
`True` costs a confirmation lookup. Happy to revisit if you'd rather it stayed optimistic.

## Verification

- **247 tests** on `feat/din-sdk`, **316** on `feat/din-daemon` after sync.
- Each of the four defects above has a test written to **fail at `90e0104`** and pass after — verified
  red first (7 failed / 3 passed, the passes being control cases).
- **Live chain (anvil):** contract deploys with `status=1` and a populated `contract_address`; event
  order `broadcasting → submitted → confirmed`; three back-to-back sends take distinct nonces (BL-1
  confirmed on a real chain, not just in mocks); receipt is JSON-serializable.
- **Golden parity (§7):** `dindao deploy din-coordinator` run against `4ab0114` and HEAD in separate
  venvs against real anvil — stdout/stderr and exit code **identical** after normalizing tx hash and
  addresses.

### Not verified — please weigh this

**The registry-write parity case was not run.** Reaching `process_receipt` needs the full registration
flow (registry + IPFS + manifest); both `dintoken` paths I tried fail on a read before reaching
`build_and_send_tx`. So the `error_msg` formatting on the failure paths is covered by unit tests but
**not** by live-chain parity. Flagging rather than letting "247 passed" imply otherwise.

Also corrected the previous slice's test mocks, which asserted `get_transaction_receipt` returns
`None` — a web3 contract that does not exist, and the reason this class of defect went unnoticed.

## Still out of scope

`sdk/operations/` and plan/apply (§6) — [`BL-9`](../BACK_LOG.md). `dind`'s `JOB_HANDLERS` stays a no-op
`"demo"` entry. `dind config` / `dind load config` not built (boundary #5), though the daemon adapter's
contract is documented against session-held bootstrapped state rather than a raw env lookup.
