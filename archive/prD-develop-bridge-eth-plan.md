# PR D — `dincli system bridge-eth` on `develop`

**Branch:** `fix/develop-bridge-eth` (off `develop` @ `b2c2e43`, post-#96) — not yet created
**Base:** `develop` on `InfiniteZeroFoundation/DevNet`
**Origin:** [discussion #79](https://github.com/InfiniteZeroFoundation/DevNet/discussions/79#discussioncomment-18082657) row D, greenlit by @umeradl ("do PR A and onwards too")
**Ports:** `1562534` (#85)
**Status:** rev 3 — twice audited. Twelve findings across two rounds, all upheld. Ready to implement.

> **Rev 2 changelog.** All verified against `develop` @ `b2c2e43`.
>
> - **Test inventory was wrong (§5).** `test_wrong_network_zero_rpc` is *already* one of `main`'s 31,
>   so only one of my two "develop-specific" tests was new. And the 31 functions collect as **38
>   cases** (one `parametrize` with 8 values).
> - **Coverage was overstated (§5).** I described what `bridge.py` *has*, not what the tests *cover*.
>   Grepping the source test file: `resolve_l1_rpc` 0 hits, `classify_broadcast_error` 0 hits,
>   `Decimal` 0 hits. Precedence, error classification and non-string amount inputs are untested.
>   Tests added to close that.
> - **The dry-run claim was wrong (§4.1).** `affordability_check` runs at `main:system.py:901`,
>   *before* `if dry_run:` at `:923`. An unfunded account is rejected, so dry-run does **not** work
>   with any key — it needs funds for the deposit plus the buffered fee.
> - **"Do not interact at all" was too strong (§2.2).** PR B never sees the L1 connection, but
>   `bridge-eth` takes its L2 connection from `ctx.obj.w3`, which *does* go through `get_w3()`.
>   Reworded.
> - **Line refs were measured on the PR C branch, not `develop`** — that branch adds ~37 lines above
>   them. Corrected: `get_active_account_name` is `utils.py:538` (not 575), `print_tx_info` is
>   `utils.py:909` (not 946). The skip-list has **21** entries on `develop`, not 22 (my count came
>   from the PR A branch, which adds one).
> - **`bridge.py` does import `requests`** — guarded, at `:19-21` — plus `__future__.annotations`.
>   Still no `dincli` imports, so still a verbatim port.
> - **The public-surface list omitted the constants** the CLI and tests consume.
> - **`fail_if_called` already accepts `*args, **kwargs`** (`main:tests:76`), so only the bare
>   `lambda: account` needs the signature fix.
> - **The structural skip-list test is dropped** as redundant — the wrong-network test already fails
>   on a misspelled entry, behaviourally, because the callback would construct a `Web3` first.

> **This is the closest thing to a real port in the series.** `services/bridge.py` is self-contained
> — stdlib plus `eth_account`, `web3` and an optional guarded `requests`, with no `dincli` imports at
> all — so it copies essentially verbatim. The work is in the CLI wiring and the tests, where `develop` differs. §2.7 is the
> delta list.

---

## 1. Why

Every faucet in the funding path has grown a gate: Chainlink and `console.optimism.io` want a
connected browser wallet, Alchemy wants ≥0.001 ETH on mainnet plus transaction history. A key
generated on a headless box five minutes ago has none of that, and there is no browser on the box to
connect anything with.

Funding on **Ethereum Sepolia L1** and bridging works, because `L1StandardBridge.receive()` takes
plain ETH from an EOA and credits the same address on L2 — a signed transfer, no ABI encoding.

Two traps this command exists to remove, both hit during onboarding:

- **The gas.** A deposit burns ~590–620k gas. Setting the 21,000 limit of a normal transfer makes it
  fail with nothing useful in the error.
- **Verifying the bridge address.** `OTHER_BRIDGE()` returns the same `0x4200…0010` predeploy on
  every OP-Stack chain, so it does not tell you you are on the right one.

Verified on `main` with a real deposit:
[`0xfbdff101…5263`](https://sepolia.etherscan.io/tx/0xfbdff101d4c197511091607dbcf3f06573466e73fa279992a4c9075035415263)
— 589,390 gas against a 621,998 estimate, exactly +0.002 ETH on L2.

---

## 2. Design decisions

### 2.1 `services/bridge.py` ports verbatim

422 lines (`+423` in the diffstat — the file has no trailing newline). Imports `__future__.annotations`,
`math`, `time`, `decimal`, `typing`, `eth_account`, `web3`, plus a **guarded** `requests` (`:19-21`,
`except ImportError: requests = None`) used only by `classify_broadcast_error` (`:153`). Nothing from
`dincli`, which is what makes it portable.

Note `requests` is currently **undeclared** on `develop` — #97 adds it. The guard means the port
degrades rather than breaks if it were ever absent: a `ConnectionError`/`TimeoutError` skips the
`requests`-specific branch and falls through to the **generic `SubmissionUnknown` branch**, so only
the message loses specificity — the outcome class, and with it the never-auto-retry guarantee, is
unchanged. So this PR benefits from #97 but does not depend on it.

For completeness on sequencing: #97 declares both `requests>=2.31.0` and `eth-account>=0.13.0`. The
latter formalises the version behind `signed.raw_transaction`, which `develop` already relies on in
`send-eth` — so it is a pre-existing requirement being written down, not a new bridge-specific one.

Public surface, including the constants the CLI and tests consume:

```
L1_STANDARD_BRIDGE_SEPOLIA, L1_CHAIN_ID (11155111), L2_CHAIN_ID (11155420), L1_RECEIPT_TIMEOUT
BridgeError, PreflightRejected, SubmissionUnknown, SubmissionRejected, Reverted
parse_amount, resolve_l1_rpc, connect_l1_rpc, classify_broadcast_error
static_preflight, prepare_transaction, affordability_check
sign_deposit, broadcast_and_wait, poll_l2_balance
```

Copy it unchanged. Any behavioural improvement belongs in a separate change so the port stays
reviewable against its source.

### 2.2 The L1 `Web3` is built directly, never through `get_w3()`

`connect_l1_rpc(url)` does its own `Web3(Web3.HTTPProvider(url))` and `static_preflight` asserts both
chain ids itself (L1 `11155111`, L2 `11155420`).

This matters here specifically: **PR B (#98) adds chain-id validation inside `get_w3()`**, keyed on
the *selected* network. Routing the L1 connection through `get_w3()` would compare an Ethereum
Sepolia endpoint against `sepolia_op_devnet`'s expected `11155420` and reject it. The bridge builds
its own, so that cannot happen.

Precisely stated, because "they do not interact" is too strong: PR B never sees the independently
constructed **L1** connection. It does sit on the **L2** path — `bridge-eth` takes `ctx.obj.w3`,
which goes through `get_w3()` — where its validation is compatible with, and partly duplicates,
`static_preflight`'s own L2 chain check. A misconfigured L2 endpoint would be rejected slightly
earlier with PR B merged; a correct one costs one extra `eth_chainId` call.

### 2.3 Do **not** reuse `develop`'s tx or print helpers ⚠️

`develop` has two helpers that look applicable and are wrong for an L1 transaction. Both are the
kind of "obvious" reuse a reviewer or a future refactor would reach for, so they are called out:

| Helper | Why it breaks |
|---|---|
| `ctx.obj.get_tx_params()` (`context.py:111`) | Every field is read from `self.w3`, the **L2** connection: `chainId` would be `11155420` instead of `11155111`, `nonce` would be the L2 nonce, and gas pricing would come from the wrong chain |
| `print_tx_info(tx_hash, network)` (`utils.py:909`) | Prints `din_info[network]["explorer"]`, which is `sepolia-optimism.etherscan.io` for both `local` and `sepolia_op_devnet` — an OP Sepolia link for an Ethereum Sepolia transaction. There is **no** L1 explorer key in `din_info.json` at all |

`main` sidesteps both: `prepare_transaction` builds L1 params itself, and the command hardcodes
`https://sepolia.etherscan.io/tx/{tx_hash}`. Do the same.

**Not adding an `l1_explorer` key to `din_info.json`** in this PR: it would put a second
bridge-specific constant in a file PR B is already editing, for one string. Noted as a follow-up.

### 2.4 `develop` already has `send-eth` — related, not reusable

`system.py:702` has a `send-eth` command doing an active-network ETH transfer with
`--amount`/`--to`/`--yes`, address validation, a balance check and a confirmation prompt.

Useful as a **UX precedent** — `bridge-eth` should feel like its sibling — but it is not a
foundation to build on: `send-eth` is one chain, arbitrary recipient, default gas, and it uses both
helpers ruled out in §2.3. Keep `main`'s command surface (`--amount`, `--l1-rpc-url`,
`--wait/--no-wait`, `--timeout`, `--dry-run`, `--yes`), which is a superset.

Worth stating in the PR body, or a reviewer will reasonably ask why `send-eth` was not extended.

### 2.5 L1 RPC resolution stays `--l1-rpc-url` → `SEPOLIA_L1_RPC_URL`

An observation that could tempt a change: `ALLOWED_NETWORKS` includes `sepolia_devnet`, which has no
`din_info.json` entry, and `resolve_network_value` would read `SEPOLIA_DEVNET_RPC_URL` for it. It
*looks* like a natural L1 slot.

Do not use it. Nothing on this branch documents `sepolia_devnet` as Ethereum Sepolia — every mention
is a bare list entry — so treating it as L1 would be inventing a contract. Keep `main`'s explicit
env var, which says what it is.

### 2.6 Test port: one signature difference

`main`'s tests patch the context's account loader as a **zero-argument** callable:

```python
monkeypatch.setattr("dincli.cli.context.load_account", lambda: account)
```

`develop`'s context calls it with a keyword (`context.py:79`):

```python
self._account = load_account(name=self.resolved_wallet_name)
```

So the patch must accept it — `lambda name=None: account`, or `lambda **kw: account`.

**Only that one lambda.** `fail_if_called` already returns `def boom(*args, **kwargs)`
(`main:tests/test_bridge_eth.py:76`), so the guards need no change.

Checked, and no further patching is needed: `resolved_wallet_name` → `get_active_account_name`
(`utils.py:538`) falls through to `"default"` when nothing is configured and **never exits**, so a
test with no registered wallet resolves harmlessly.

Everything else ports as-is — the tests patch `bridge_service.*` functions on the service module
rather than any `dincli` internals, which is what makes them portable.

### 2.7 Deltas from `main`'s version

| # | `main` | `develop` | Consequence |
|---|---|---|---|
| 1 | `load_account()` | `load_account(name=...)` | test patches need a `name=`-compatible signature (§2.6) |
| 2 | no `send-eth` | has `send-eth` | UX precedent to match; explain why it was not extended (§2.4) |
| 3 | skip-list at `:56` | skip-list at `:73`, **21** entries (22 after this PR) | same one-line edit, different location — and it collides (§2.8) |
| 4 | `get_tx_params` absent from this path | exists and is L2-bound | must not be reused (§2.3) |
| 5 | `print_tx_info` not used here | exists, OP-Sepolia explorer only | must not be reused (§2.3) |
| 6 | — | `Optional` (`:11`) and `get_env_key` (`:25`) already imported in `system.py` | no import work |

### 2.8 Collision map — one guaranteed conflict

`bridge-eth` must be added to the `system` callback skip-list. **#97 edits that exact line**,
verified:

```
git diff develop..fix/develop-small-backports -- dincli/cli/system.py
@@ -70,7 +70,7 @@        <- #97 adds "configure-ipfs" to the skip-list
```

This is the `#82`/`#85` pattern from `main` repeating: two PRs, one list, guaranteed
`CONFLICT (content)`, resolved as the union. Whichever merges second must combine by hand and not
trust an auto-merge.

Against the other open work:

| PR | Files | Overlap with this PR |
|---|---|---|
| #97 | `system.py`, `dintoken.py`, `aggregator.py`, `auditor.py`, `pyproject.toml` | **`system.py` skip-list — conflict** |
| #98 | `core.py`, `utils.py`, `din_info.json`, `pyproject.toml` | none |
| #100 | `dintoken.py`, `utils.py` | none |

Verify with committed merges before opening, not chained `--no-commit` — that method has already
misled this repo once.

---

## 3. Changes

### 3.1 `dincli/services/bridge.py` — new

Copy `main:dincli/services/bridge.py` unchanged (422 lines).

### 3.2 `dincli/cli/system.py`

- `from dincli.services import bridge as bridge_service`.
- The `bridge-eth` command, ported from `main:system.py`. Surface: `--amount`, `--l1-rpc-url`,
  `--wait/--no-wait`, `--timeout`, `--dry-run`, `--yes`.
- Add `"bridge-eth"` to the skip-list (`:73`).
- The L1 explorer line stays hardcoded to `https://sepolia.etherscan.io/tx/{hash}` (§2.3).

Order inside the command matters and is `main`'s: validate input → check the selected network is
`sepolia_op_devnet` → resolve and connect L1 → resolve account, then L2 `w3` → `static_preflight`.
Static checks first means a wrong-network invocation costs no RPC calls.

### 3.3 `tests/test_bridge_eth.py` — new

Port `main`'s 31 tests, with the `load_account` signature fix from §2.6.

---

## 4. Verification

### 4.1 `--dry-run` first — but it needs a funded key

Every preflight check runs and the transaction is printed without being signed. **It is not
usable with an arbitrary key:** `affordability_check` runs at `main:system.py:901`, before
`if dry_run:` at `:923`, so a successful dry-run requires an L1 RPC *and* an account holding the
deposit amount plus the maximum buffered fee.

An unfunded account exercises only the insufficient-balance rejection path — worth running too, but
it is a different assertion, not a free full rehearsal.

### 4.2 Wrong-network rejection is free

`dincli --network local system bridge-eth --amount 0.001 --dry-run` must be refused **before any RPC
call** — that is what §3.2's ordering buys, and it is worth asserting explicitly.

### 4.3 One real deposit — manual, explicitly authorised

`dincli --network sepolia_op_devnet system bridge-eth --amount 0.002` from the funded aggregator key.
This moves real testnet funds, so it is a **manual smoke test to be authorised deliberately**, not a
mandatory step in an automated run. Run once and record the tx hash and gas used in the PR, as
`main`'s did.

Assert: L1 inclusion reported, the `sepolia.etherscan.io` link is correct (not the OP explorer), and
with `--wait` the L2 balance increase is detected.

### 4.4 Unconfigured L1 RPC

With neither `--l1-rpc-url` nor `SEPOLIA_L1_RPC_URL`: a clear message naming both, not a traceback.

### 4.5 Regression — `send-eth` still works, tested not transacted

It shares `system.py` but nothing else. Do **not** move real funds for this: a mocked `CliRunner`
test is the right check, since what could break is the new import and the skip-list edit, not the
transfer logic. A bare `--help` only proves registration, not callback behaviour, so the mocked test
belongs in §5 rather than here.

---

## 5. Tests (committed)

**Inventory, corrected.** `main` has **31 test functions** which collect as **38 pytest cases** —
one `@pytest.mark.parametrize` carries 8 amount values. Port all 31, with the §2.6 lambda fix.

`test_wrong_network_zero_rpc` is **already** among them (`main:tests:85`), so it is not a
develop-specific addition. It is also the reason no structural skip-list test is needed: a misspelled
entry such as `"bridge_eth"` makes the group callback construct a `Web3` before the command runs, and
that test asserts zero RPC calls, so it fails behaviourally. A source- or bytecode-inspecting
membership test would be weaker and more brittle; if a structural check is ever wanted, the skip-list
should first be extracted into a named constant.

**Coverage gaps in the ported suite.** Grepped the source test file rather than assuming: `Decimal`
0 hits, `resolve_l1_rpc` 0 hits, `classify_broadcast_error` 0 hits. So the inherited tests do **not**
cover precedence, error classification, or non-string amount inputs — only the missing-configuration
case and string amounts. Given this command signs transactions, those are worth closing here:

| New test | Asserts |
|---|---|
| L1 RPC precedence | an explicit `--l1-rpc-url` wins over `SEPOLIA_L1_RPC_URL` |
| whitespace URL falls back | a whitespace-only CLI value defers to the environment rather than being used |
| transport error | a `requests.ConnectionError`/`Timeout` classifies as `SubmissionUnknown` — the "may have landed" case, which must never be reported as a clean failure |
| RPC rejection | a `Web3RPCError` classifies as `SubmissionRejected` |
| non-string amounts | `Decimal`, `int`, `float` and `bool` inputs behave as intended (`bool` in particular must not be silently accepted as a number) |
| `send-eth` regression | mocked `CliRunner` invocation still reaches its own callback after the new import and skip-list edit (§4.5) |

That is 31 ported + 6 new = **37 functions**, and the earlier "33" figure was wrong on both counts.

The `SubmissionUnknown` case deserves the emphasis: it is the difference between "your deposit did not
happen" and "your deposit may have happened, do not retry blindly", and it is currently untested on
`main`.

## 6. PR body outline

1. Row D of the #79 split; ports `1562534`
2. Why the command exists: the faucet wall, the gas trap, the `OTHER_BRIDGE()` trap
3. `bridge.py` is a verbatim port — self-contained, no `dincli` imports
4. The independently constructed L1 connection bypasses #98's validation; the L2 path uses it
   compatibly and retains a redundant preflight check
5. Why `get_tx_params`/`print_tx_info` are deliberately not reused (§2.3)
6. Why `send-eth` was not extended (§2.4)
7. Why `sepolia_devnet` was not used as the L1 slot (§2.5)
8. The one test-signature difference (§2.6)
9. Verification: dry-run, the wrong-network no-RPC assertion, and one real deposit with its hash
10. **Merge order: guaranteed skip-list conflict with #97**, union resolution

## 7. Follow-ups not in this PR

- **Docs.** `Documentation/public/getting-started.md` and `guides/wallet-setup.md` mention faucets;
  neither knows about `bridge-eth`. `main` folded this into its docs overhaul, and the equivalent
  here is a separate docs PR.
- **`l1_explorer` in `din_info.json`** (§2.3), so the L1 link is not a constant in the command.
- **Withdrawals** stay out of scope: L2→L1 takes ~7 days and needs separate prove and finalize
  steps. The command is deposit-only by design, and says so in its docstring.
- **Reorg protection** is out of scope on `main` too — L1 inclusion is reported, never
  "confirmation". Keep that wording.
