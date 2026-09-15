# PR 7 — `dincli system bridge-eth`: fund L2 from Sepolia L1

**Branch:** `feat/bridge-eth-command` (off `main` @ `e83c589`, already created)
**Base:** `main`. Independent of #83 (§4); overlaps #82 on one line (§3.1)
**Origin:** [discussion #79](https://github.com/InfiniteZeroFoundation/DevNet/discussions/79#discussioncomment-17972890) — @umeradl's funding ask, part 2. Part 1 (the docs) shipped in #80
**Status:** rev 3 — twice audited. Implementation-ready, no blocking dependency.

> **Rev 2 changelog.** An audit found three blocking problems, all verified and all upheld.
> Rev 1's callback strategy made its own preflight ordering impossible (§3.1). Duplicate-deposit
> protection covered only the L2 timeout and missed every ambiguous-broadcast case (§3.2). The EOA
> check proved nothing about the L2 recipient (§3.3). Also added: the #83 dependency is now declared
> rather than assumed (§4), a full fee and nonce model (§3.4), L2 arrival demoted to a heuristic
> (§3.5), credential-safe RPC handling (§3.6), input validation (§3.7). **Additionally found while
> verifying: PR 7 must edit the same line as #82.**
>
> **Rev 3 changelog.** A second audit found four specification issues, all upheld. Affordability was
> listed as preflight but depends on fees and gas, so the flow is now four explicit stages (§5.1).
> Dry-run both prompted and read the L2 baseline, neither of which a non-sending operation should do
> (§5.2). The reorg policy was left "optional" and is now decided: **inclusion, not confirmation**,
> with the reasoning (§3.2a). Error ownership between the service and the Typer wrapper is now a
> defined `BridgeError` hierarchy with terminal outcomes (§3.8). Tests: the zero-RPC assertion must
> run through `CliRunner` or it bypasses the very callback it exists to check (§7).
>
> Rev 3 also **withdraws rev 2's #83 prerequisite** (§4): the L2 chain assertion was always local to
> this command, and having the wrapper catch `ConnectionError` closes the only real gap. No blocking
> dependency remains — #82 is a rebase, not a blocker.

---

## 1. Goal

Umer's ask:

> A `dincli` command/script wrapping the bridge transfer, using `web3` the way you described (dincli
> already depends on it) — with the gas limit set correctly instead of defaulting to 21,000.

Context is B9: no faucet lets a headless operator self-fund any more. The documented workaround is
to fund on Ethereum Sepolia L1, where faucets are far less gated, and bridge. OP's
`L1StandardBridge.receive()` credits **the same address** on L2, so a deposit is an ordinary signed
value transfer — no ABI encoding, no browser.

**Deposits only.** Withdrawals are L2→L1, take ~7 days, and need separate prove and finalize steps.
Say so in the command help rather than implying symmetry.

## 2. The two-chain problem

`dincli` assumes **one chain**. `get_w3()` resolves a single `<NETWORK>_RPC_URL`, and
`get_tx_params()` (`context.py:91-98`) stamps `chainId` from that instance. This command signs on
**L1 Sepolia (11155111)** while the DIN network stays **OP Sepolia (11155420)**.

Consequences, all of which have bitten a draft of this plan already:

- `get_tx_params()` **cannot be reused** — wrong chain id. Build L1 params directly (§3.4).
- Pointing `SEPOLIA_OP_DEVNET_RPC_URL` at an L1 endpoint to "make it work" is rejected by #83's
  chain-id check. Correct behaviour; the command builds its own L1 Web3 instead.
- `print_tx_info` does not exist on `main` (a `develop` helper), and `main`'s `din_info.json` has no
  `explorer` field. Print the hash plus a hardcoded Sepolia explorer URL; do not invent a helper.

## 3. Decisions

### 3.1 `bridge-eth` **goes in** the callback skip-list — corrected

Rev 1 said it must *not* be skip-listed "because it needs a wallet". That reasoning was wrong and it
made rev 1's own preflight order impossible. The `system` callback (`system.py:55-59`) calls
`get_en_w3_account_console()` for anything not skip-listed, which eagerly loads **both**
`ctx.obj.account` and `ctx.obj.w3` before the subcommand runs. So:

- "Wrong network → refused before any RPC call" could never happen.
- A `local` or `mainnet` RPC connection would be attempted before the command could reject it.
- The callback prints "Active Web3" before any bridge validation.

**The skip-list controls eager initialisation, not whether a handler may load a wallet.** Skip-list
it, then load explicitly in this order:

1. Validate `ctx.obj.network` is `sepolia_op_devnet` — refuse otherwise, **before any RPC**.
2. Resolve and validate the L1 RPC config (§3.6).
3. Load `ctx.obj.account`.
4. Load and validate `ctx.obj.w3` (L2).
5. Bridge preflight (§4.2).

> **Conflict with #82.** That PR rewrites this exact line (`system.py:56`) to add `configure-ipfs`
> and fix the two dead underscore entries. PR 7 must add `"bridge-eth"` to the same list. Whichever
> merges second needs a trivial rebase. Flag it in both PR bodies — #82 is a one-liner and will
> likely land first.

### 3.2 Ambiguous broadcast, not just the L2 timeout — corrected

Rev 1 protected only against "sent, not yet visible on L2". The genuinely dangerous states are
earlier and were unhandled:

- `send_raw_transaction()` reaches the node, then the connection times out
- L1 receipt polling times out after a successful broadcast
- the process is interrupted after broadcast, before the hash is printed
- an observed receipt is later reorganised away

Each of these can prompt a second deposit just as easily as an L2 timeout.

**Required behaviour:**

- **Compute the transaction hash locally from the signed raw transaction, and print it *before*
  broadcasting.** Then the hash exists even if the broadcast call never returns.
- **Never auto-retry a signed value transfer.** Not once, not with backoff.
- Give L1 receipt waiting an **explicit timeout**.
- On any broadcast or receipt ambiguity, report a distinct `SUBMISSION_UNKNOWN` outcome whose
  wording actively discourages retrying: *"submission status unknown — check this hash before
  retrying."*

Rev 1 called a mined deposit "irreversible and will arrive". **Too strong** — a single observed
receipt is not final. Soften throughout.

### 3.2a Reorg policy: **inclusion, not confirmation** — decided

Rev 2 listed reorgs as an ambiguous state but only "optionally" suggested waiting for
confirmations. Deciding: **accept one-block inclusion, and never use the word "confirmed" for the
L1 side.** Say *"included in block N"*.

Reasoning: waiting a confirmation count adds latency to an already slow flow for little benefit
here, and **the L2 balance poll is already the practical reorg detector for the path that matters**.
If a reorg drops the deposit, the L2 balance never rises and the operator sees "not visible yet"
alongside the L1 hash — the correct outcome, reached without a separate confirmation wait.

Reorg protection is therefore explicitly **out of scope**, stated in the command help. Anyone who
needs it can check the hash.

### 3.2b Exit codes and terminal outcomes

| Outcome | Meaning | Exit |
|---|---|---|
| `PREFLIGHT_REJECTED` | Refused before signing | 1 |
| `REVERTED` | L1 receipt status 0 | 1 |
| `SUBMISSION_UNKNOWN` | Broadcast or receipt ambiguous — **do not retry** | 1 |
| `SUBMISSION_REJECTED` | Node deterministically rejected the tx | 1 |
| `SUBMITTED` | Included on L1; L2 arrival observed, pending, or not waited for | 0 |

### 3.3 Check the **L2** recipient for code too — corrected

Rev 1 checked only that the sender has no bytecode on L1. That proves nothing about L2: deployment
state is per-chain, and the same address can hold code on L2 while being an EOA on L1.

It matters because the bridge delivers ETH to that address on L2, and the Standard Bridge's own
source warns that ETH sent to an L2 contract can be locked if the recipient call fails. The
`receive()` path restricts the *L1 caller* to an EOA — an L1-only guarantee.

Since this command is same-address-only, **also require `l2_w3.eth.get_code(account.address)` to be
empty**, and refuse with a clear explanation otherwise. Verified the intended live-test wallet
returns `0x` on OP Sepolia, so it passes.

### 3.4 Fee, nonce and affordability model — specified

Rev 1 said only "build L1 params directly". Underspecified in ways that produce real bugs.

| Field | Value |
|---|---|
| `to` | checksummed bridge proxy |
| `value` | integer wei |
| `data` | empty |
| `chainId` | **11155111** |
| `nonce` | `get_transaction_count(sender, "pending")` |
| `maxPriorityFeePerGas` | `w3.eth.max_priority_fee` |
| `maxFeePerGas` | `2 × latest_block.baseFeePerGas + priority_fee` |
| `gas` | `ceil(estimate × 1.20)`, integer arithmetic |

Assert `maxFeePerGas >= maxPriorityFeePerGas`.

**Affordability must use the buffered limit and the fee cap:**

```
required = value + gas_limit * max_fee_per_gas
```

Checking `estimate × current gas price` can pass preflight while the signed transaction's maximum
cost exceeds the balance. Print estimated gas, the signed gas limit, both fee caps, and the maximum
possible fee **separately**, so an absurd value is visible before signing.

(House style in `get_tx_params()` uses `gas_price * 2` for the cap; the base-fee form above is more
correct and this command does not share that helper anyway.)

### 3.5 L2 arrival is a **visibility heuristic** — corrected

"Balance rises above the pre-send reading" can false-positive on unrelated incoming ETH and
false-negative if the operator spends on L2 while waiting. It never proves *this* deposit caused the
change.

Deriving and polling the L2 deposit hash is out of scope, so label it honestly: the output says
**"balance increase observed"**, never "deposit verified", and the **L1 hash stays the durable
reference**. Polling must tolerate transient L2 RPC failures within the timeout rather than aborting.

Default timeout **360s** — Optimism's operator guidance says up to five minutes, so 300 sits exactly
on the documented boundary. `--no-wait` skips waiting and must still print an unmistakable
"submitted, delivery pending" result.

### 3.6 L1 RPC: resolution, connection and credential safety

Resolution order: `--l1-rpc-url` flag → `SEPOLIA_L1_RPC_URL` via `get_env_key(..., verbose=False)` →
clear error naming both routes.

**Not a new network.** Adding `sepolia` to `ALLOWED_NETWORKS` would make it selectable via
`configure-network`, after which every DIN command would accept a network with no contracts behind
it. That wart already exists (`sepolia_devnet` is selectable and absent from `din_info.json`) and is
logged as a follow-up on #83; duplicating it would be poor form. Umer specified the mechanism, not
the configuration, so flag the choice in the PR body.

Requirements: non-blank after trimming; `w3.is_connected()`; clean handling when `eth_chainId`,
`eth_getCode`, fee queries, gas estimation or receipt polling fail. **No raw RPC URL and no provider
exception in user-facing output** — path and query components carry API keys. #83 deliberately
removed that leak on the normal path; this new L1 path must not reintroduce it.

### 3.7 Input validation

- `amount`: finite, positive, converts to **≥ 1 wei** exactly
- `timeout`: non-negative
- Declining the confirmation exits cleanly, having signed nothing
- `--dry-run` does not read the initial L2 balance unless the printed simulation covers waiting
- Check the bridge's `paused()` directly for a clear diagnostic — verified present, currently
  `false`. Gas estimation would catch a paused bridge, but with a far worse message.

### 3.8 Error ownership between service and command

#83's boundary catches `ChainIdMismatchError` and `ConnectionError`. It does **not** know about
bridge-specific failures, so rev 2's promise of "clean exits" had no mechanism behind it.

**`services/bridge.py` raises a `BridgeError` hierarchy; the thin Typer wrapper catches it, prints
one sanitised line, and maps to the §3.2b exit code.** The service never prints and never exits —
same separation as #83's `get_w3()`.

**The wrapper also catches `ConnectionError`**, which is what makes this PR independent of #83
rather than blocked by it — see §4.

Mapping, which must be explicit rather than incidental:

| Condition | Outcome |
|---|---|
| Any preflight failure (§4.2) | `PREFLIGHT_REJECTED` |
| Transport failure during broadcast | `SUBMISSION_UNKNOWN` |
| L1 receipt wait timeout | `SUBMISSION_UNKNOWN` |
| Receipt hash mismatch | `SUBMISSION_UNKNOWN` |
| Malformed / unexpected receipt | `SUBMISSION_UNKNOWN` |
| Deterministic node rejection (e.g. nonce too low, underpriced) | `SUBMISSION_REJECTED` |
| Receipt status 0 | `REVERTED` |

Every outcome from broadcast onward — including `SUBMISSION_REJECTED` — **must print the locally
computed hash** and must **never** trigger an automatic retry.

### 3.9 Name and structure — decided

`dincli system bridge-eth`, mirroring `send-eth` on `develop`. Mechanics in a new
`dincli/services/bridge.py` as plain functions; the Typer command stays a thin wrapper.
`system.py` is already ~800 lines.

## 4. Relationship to #83 — independent, not blocked

Rev 1 asserted that "#83 already validates" the L2 chain. It is not merged: this branch is off
`e83c589`, where `get_w3()` has no chain check and `core.py` has **no exception handlers at all**,
so a `ConnectionError` from a bad L2 RPC reaches the user as a traceback.

Rev 2 responded by declaring #83 a hard prerequisite. **Rev 3 softens that** — on inspection the
dependency is avoidable and not worth imposing on an already-queued review stack:

- The L2 chain-id assertion is **local to this command** (§4.2 step 3) and raises a `BridgeError`.
  It never delegates to `get_w3()`, so #83's presence is irrelevant to it. That assertion stays
  regardless of merge order — it is a safety invariant for a value transfer, not something to
  outsource.
- The only genuine leak was error *rendering*. Having the wrapper catch `ConnectionError` as well
  as `BridgeError` (§3.8) closes it, so bridge failures render cleanly on plain `main`.

**So: implementable and mergeable independently, in any order relative to #83.** When #83 does land,
its boundary handles `ConnectionError` globally and this wrapper's own handling becomes harmless
redundancy — worth a comment saying so, not worth removing.

The real ordering constraint is **#82**, which edits the same line (§3.1). That is a rebase, not a
blocker.

### 4.1 Constants (`services/bridge.py`)

| | |
|---|---|
| `L1_STANDARD_BRIDGE_SEPOLIA` | `0xFBb0621E0B23b5478B630BD55a5f21f67730B0F1` |
| `L1_CHAIN_ID` | `11155111` |
| `L2_CHAIN_ID` | `11155420` |

Address is the **proxy**, from the `superchain-registry` entry for chain `11155420` — cite it in a
comment. Keep in code, not `din_info.json`, which holds DIN deployment state and is rewritten at
runtime by `dindao.py`.

### 4.2 Preflight — all mandatory

1. Selected network is `sepolia_op_devnet` (before any RPC)
2. L1 `chain_id == 11155111`
3. L2 `chain_id == 11155420`
4. Bridge address has bytecode on L1
5. Bridge `paused()` is false
6. Sender has **no** code on L1
7. **Recipient has no code on L2** (§3.3)
8. `balance >= value + gas_limit × max_fee_per_gas` (§3.4)

Do **not** call `OTHER_BRIDGE()` as a check — it returns the same `0x4200…0010` predeploy on every
OP-Stack chain, so it proves nothing. Note that in a comment so it is not "helpfully" added later.

## 5. Command specification

```
dincli system bridge-eth --amount 0.01
                         [--l1-rpc-url URL]
                         [--wait / --no-wait]      (default: wait)
                         [--timeout 360]
                         [--dry-run]
                         [--yes]
```

### 5.1 Flow — four explicit stages

Rev 2 listed affordability under "preflight" while the flow ran *preflight → estimate and build*.
Contradictory: affordability cannot be evaluated before fees are fetched, gas is estimated and the
buffer applied. Split it:

1. **Static preflight** — input validation, selected network, L1/L2 RPC resolution and connection,
   both chain ids, bridge bytecode and `paused()`, sender code on L1, recipient code on L2. No fee
   or gas work yet.
2. **Prepare** — fee caps, pending nonce, gas estimate, ceiling buffer (§3.4).
3. **Financial preflight** — `balance >= value + gas_limit × max_fee_per_gas`.
4. **Summary → dry-run or send.**

### 5.2 Dry-run does not prompt and does not read L2

Rev 2 had `--dry-run` fall through the confirmation prompt and the L2 baseline read. A non-sending
operation should require no confirmation, and the baseline is only meaningful when waiting.

```
stages 1-3  →  print summary
                 ├─ --dry-run:  exit 0            (no prompt, no L2 baseline, no signing)
                 └─ live:       confirm unless --yes
                                → read L2 baseline ONLY if --wait
                                → sign
                                → print hash            (before broadcast, §3.2)
                                → broadcast
                                → wait for L1 receipt, with timeout
                                → poll L2 if --wait     (§3.5)
```

## 6. Files

| File | Change |
|---|---|
| `dincli/services/bridge.py` | New — constants, preflight, fee model, deposit, L2 polling |
| `dincli/cli/system.py` | New `bridge-eth` command + **skip-list entry** (§3.1) |
| `tests/test_bridge_eth.py` | New, force-added (`tests/` gitignored on `main`; #31 changes that) |

No version state, no docs. `GettingStarted.md` documents the manual route from #80; pointing it at
the command is a follow-up that would conflict with #80 if attempted now.

## 7. Tests — mocked, no network

**Run the ordering tests through `CliRunner` against the real app**, not by calling the handler
directly. Calling the function bypasses the `system` callback entirely — which is the exact
mechanism §3.1 fixes, so a direct call would assert nothing. In particular the "wrong network → zero
RPC calls" test is meaningless unless it dispatches through the real callback.

CLI-boundary assertions, on every such test: exit code, **no traceback**, **no RPC credential**,
and the expected outcome wording from §3.2b. Plus: `--dry-run` neither prompts nor reads the L2
balance; and after the #82 rebase, the skip-list still contains both #82's entries and `bridge-eth`.

Ordering and refusal: wrong network causes **zero** L1 and L2 RPC calls; L1 chain mismatch; L2 chain
mismatch; bridge without bytecode; bridge paused; sender with L1 code; **recipient with L2 code**;
missing L1 RPC config naming both routes.

Transaction construction: buffered gas uses **ceiling** integer arithmetic; 21,000 is never sent;
affordability uses buffered gas × `maxFeePerGas`; `nonce` uses `"pending"`;
`maxFeePerGas >= maxPriorityFeePerGas`; the signed tx carries **L1**'s chain id.

Amount and timeout: zero, negative, NaN, infinite, sub-wei and malformed amounts; negative timeout.

Broadcast safety: `--dry-run` prints the exact unsigned transaction and **never touches the signing
path**; declining confirmation signs and sends nothing; broadcast raising *after* the local hash
exists still surfaces the hash; L1 receipt timeout → `SUBMISSION_UNKNOWN` with anti-retry wording;
receipt hash mismatch, malformed receipt, and deterministic node rejection each map to their §3.8
outcome, and every one of them still prints the hash.

Waiting: successful L2 balance increase; `--no-wait` prints "submitted, delivery pending"; polling
tolerates transient L2 RPC failures within the timeout.

Credential safety: a sentinel secret in the L1 RPC URL appears in **no** error path.

## 8. Live verification — one real testnet deposit

Sepolia ETH is free testnet currency with no monetary value; the only cost is that re-obtaining it
is awkward, which is the problem this command solves. Available: **~0.019 ETH on L1** at
`0x5DD21F7AEADB9CF2C86bAcADD6993ED380fC5273`, which is the registered GI 2 aggregator. Bridging
*into* L2 only raises its L2 balance, so it cannot affect T1 submission. Verified it has no code on
L2.

Sequence: `--dry-run` first, then a **0.002 ETH** deposit, recording L1 tx hash, gas used vs
estimated, L2 balance before/after, and arrival time. Those numbers also fill the gap in #80's
evidence appendix, where the bridge figures rest on a single manual run.

**Re-check immediately before executing** — L1 balance, selected account, both chain ids, bridge
bytecode and `paused()`, L2 recipient code, and the fee ceiling. This plan's approval is not a
substitute for confirming at the moment value actually moves.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Operator retries an ambiguous submission | §3.2 / §3.8 — local hash printed pre-broadcast, no auto-retry, anti-retry wording on every post-broadcast outcome |
| A reorg drops an included deposit | §3.2a — out of scope by decision; the L2 poll surfaces it as "not visible yet" with the hash, never as success |
| ETH locked at an L2 contract recipient | §3.3 — L2 code check |
| Signed tx costs more than the balance | §3.4 — affordability uses buffered gas × fee cap |
| False "arrived" from unrelated L2 income | §3.5 — reported as an observed balance increase, not verification |
| Wrong bridge address | Bytecode + `paused()` checks, registry citation, live deposit |
| Pointed at mainnet | Hard refusal unless `sepolia_op_devnet` |
| Credential leak via the new L1 path | §3.6 — no URL, no provider exception in output; sentinel test |
| Merge conflict with #82 | §3.1 — expected, trivial rebase, flagged in both PR bodies |

## 10. Follow-ups

- Point `GettingStarted.md` at the command once this and #80 have landed
- `--to` for depositing to a *different* L2 address — needs `depositETHTo`, a real ABI call, and a
  different recipient-safety story. Deliberately excluded
- Mainnet support — needs a second bridge address and chain-id pair; only when a mainnet deployment
  exists
