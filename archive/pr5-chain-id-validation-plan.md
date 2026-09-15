# PR 5 — Validate the RPC chain id

**Branch:** `fix/rpc-chain-id-validation` (off `main` @ `e83c589`, already created)
**Base:** `main` on `InfiniteZeroFoundation/DevNet`
**Origin:** [discussion #79](https://github.com/InfiniteZeroFoundation/DevNet/discussions/79) finding B13; confirmed by @umeradl, who called it *"the one worth prioritizing"*
**Status:** rev 3 — twice audited. All decisions made. Ready to implement.

> **Rev 2 changelog.** An audit found nine issues in rev 1. All nine were re-verified against the
> tree and **all nine were upheld** — including one that would have shipped a guaranteed
> regression. Corrections: `local` is **1337**, not 31337 (§2.3); the chain-id *read* needs its own
> exception boundary (§2.2); the RPC-URL leak is fixed here rather than deferred (§2.5); the cost,
> coverage and `mainnet` claims were overstated and are restated (§2.7–2.9); the verification plan
> could not have reached the code under test (§4).
>
> **Rev 3 changelog.** A second audit found two blockers, both upheld. Rev 2's exception strategy
> was self-contradictory — rendering and exiting inside `get_w3()` makes the typed exception
> unobservable to the callers and tests that §4 asserts on, and terminates the process from a
> utility with a non-CLI caller. `get_w3()` is now pure and rendering moves to the root
> `TyperGroup` in `core.py` (§2.6). And the test location was not an open question: `feat/din-sdk`
> already tracks 23 files under `tests/`, so the tests are committed here (§5). Also corrected: the
> coverage and cost claims (§2.7, §2.8), `{e}` interpolation as a credential-leak vector (§3.2),
> and the live "no `eth_chainId` call" assertion, which only a mock can make (§4.1).

---

## 1. The defect

`dincli` resolves `<NETWORK>_RPC_URL`, builds a `Web3` from it, and never asserts the endpoint is on
the chain the user selected. Swapping `optimism-sepolia` for `optimism-mainnet` — one word — is
accepted silently:

```
Active Network: sepolia_op_devnet
✓ Active Web3: https://optimism-mainnet.infura.io/v3/****
ETH Balance: 0 ETH
```

The only symptom is `ETH Balance: 0`, exactly what a new operator expects before funding.
`system din-info` gives false reassurance — it prints the five platform addresses from local JSON
rather than reading the chain, so every surface says "healthy".

**Why it matters beyond confusion:** a wrong-chain RPC during the T1 window means the submission
never reaches the real coordinator. Per §4.2.6 of the PR 1 plan, the present-tense consequence is
not a slash — `slashAggregators` reverts on the deployed contracts — it is that `endGI` can never
run and **the Global Iteration cannot be closed for anyone**.

The CLI cannot detect this even in principle today: `din_info.json` carries no chain id for any
network, so there is nothing to compare against.

## 2. Design decisions

### 2.1 Placement — `get_w3()`

Umer suggested `get_en_w3_account_console` "or wherever the w3 instance is first resolved". Use the
latter. Verified:

- `Web3(Web3.HTTPProvider(...))` appears **exactly once** in the package — `cli/utils.py:201`.
- `get_w3()` has three callers: `cli/context.py:64`, `cli/contract_utils.py:123`,
  `services/client.py:53`.

One check, and every RPC connection the package builds passes through it. See §2.7 for what that
does *not* mean.

### 2.2 Three distinct failure stages

Rev 1 correctly moved the *comparison* outside the broad `try`, but left the chain-id **read**
outside all handling. A node can answer `is_connected()` and still reject, time out, or return
garbage for `eth_chainId` — which would surface as a raw provider traceback, neither of the two
documented errors.

Stages:

1. **Resolve + connect** — existing `try`, raises `ConnectionError`.
2. **Read the chain id** (only if the network is pinned) — narrow `try`, raises a distinct
   "connected but could not read chain id" error.
3. **Compare** — outside both, raises the mismatch error.

Why stage 3 must stay outside stage 1: `get_w3()` currently wraps everything and re-raises as
`ConnectionError("Could not connect to Ethereum node…")`. A mismatch reported that way points at
the wrong problem — the exact B1 failure mode this whole effort exists to remove.

### 2.3 `local` is **1337** — corrected

Rev 1 said 31337, described as "the Hardhat/anvil default". That is the generic default, **not this
repository's**. Both checked-in launchers use 1337:

| Source | Value |
|---|---|
| `foundry/anvil.sh:5` | `--chain-id 1337` |
| `hardhat/hardhat.config.ts` (hardhat network) | `chainId: 1337` |

Shipping 31337 would have rejected the project's own local nodes — a guaranteed regression for the
supported setup, not merely a risk to custom ones. **Use 1337.** Verification case 5 tests 1337.

`sepolia_op_devnet` → **11155420**, which matches `hardhat.config.ts` (`chainId: 11155420`).

### 2.4 Hard-fail

Per Santiago and Umer's "fail loudly". Applies to read-only commands too: a wrong chain yields
wrong answers, so refusing is correct.

### 2.5 Remove the RPC-URL leak in this PR — corrected

`utils.py:203` interpolates the full `rpc_url` into the unreachable-node error, leaking any embedded
API key. Rev 1 deferred this, reasoning that `sanitize_rpc_url` lives in `context.py`, which imports
`utils`, so importing it back would cycle.

That reasoning was sound but the conclusion was wrong: **the function is being rewritten anyway, so
it can simply stop printing the endpoint.** No sanitizer needed, no cycle.

```python
raise ConnectionError(f"Could not connect to the configured Ethereum node for network '{effective_network}'")
```

This is not optional polish — verification case 4 deliberately points at a bad endpoint, so leaving
it would print a credential-bearing URL into terminal scrollback and any CI log.

### 2.6 Exception type and CLI presentation — resolved in rev 3

Rev 1 said `ValueError`. Two problems: a mismatch is not an invalid argument, and
**`main.py:18` sets `pretty_exceptions_enable=False`**, so an uncaught exception prints a raw
traceback — "fails loudly" technically satisfied, practically awful.

Rev 2 picked "render + `typer.Exit(1)` inside `get_w3()`". **That was self-contradictory** and is
withdrawn: once `get_w3()` converts the mismatch to an exit, callers and tests can never receive
`ChainIdMismatchError` — yet §4.1 and §4.3 both assert exactly that. It also means constructing,
raising and immediately swallowing a domain exception, which is pointless.

It was also wrong on architecture. `get_w3()` has a **non-CLI caller** at `services/client.py:53`; a
connection utility should not terminate its host process. The `DinContext.account` precedent does
not transfer — that exit happens in the CLI context layer (`context.py:68`), not in the loader
underneath it.

**Resolution — keep `get_w3()` pure, render at the CLI boundary:**

1. `get_w3()` raises `ChainIdMismatchError`. It never prints and never exits.
2. Rendering happens once, centrally, in `dincli/cli/core.py`.

`core.py` is the right place and it is already wired up: `GlobalOptionsGroup(TyperGroup)` is set as
`cls=` on the root Typer app (`main.py:19`), so **every** command dispatches through it. Override
`invoke()`:

```python
def invoke(self, ctx):
    try:
        return super().invoke(ctx)
    except ChainIdMismatchError as e:
        click.secho(str(e), err=True, fg="red")
        raise click.exceptions.Exit(1)
```

No import cycle: `core.py` → `utils.py` is clean (`utils.py` does not import `core`).

This gets every property at once — direct callers and tests receive the typed exception, every
command renders identically, no traceback, the utility stays reusable, and exit behaviour is
testable at the boundary.

**Add `dincli/cli/core.py` to the diff allowlist** (§4.4).

### 2.7 What "coverage" actually means — corrected

Rev 1 claimed placing the check in `get_w3()` means whitelisted commands like `connect-wallet` and
`configure-network` become "validated". That is wrong: **those commands never resolve a Web3 at
all**, so there is nothing to validate. The skip-list argument doesn't apply to them.

Accurate claim — and it must not overreach, since §2.9 lists networks that stay unvalidated:

> Every RPC connection passes through the validation hook; connections for networks with a
> configured `chain_id` are validated.

`din-info` *is* worth calling out: it's in the skip-list, but its own body calls
`get_en_w3_account_console()` (`system.py:356`), so it does resolve a Web3 and will be validated.

### 2.8 Cost — corrected

Rev 1 said "once per invocation" because `DinContext` caches `self._w3`. True only for access
through `DinContext.w3`. **`get_contract_instance()` calls `get_w3(network)` directly on every
call** (`contract_utils.py:123`), each building a fresh provider and running `is_connected()`.

Accurate: **one additional RPC call per `get_w3()` call on a pinned network** — potentially several
per CLI invocation, one per contract instantiated. Unpinned networks return before `eth_chainId` and
cost nothing. Acceptable, since it sits alongside the `is_connected()` round-trip already made.
Reusing `ctx.w3` for contract construction is a reasonable follow-up, out of scope here.

### 2.9 `mainnet`, and what stays unvalidated — corrected

Rev 1 argued that setting `mainnet` to 10 "would assert a deployment that doesn't exist". That
conflates two separate facts: chain identity and contract deployment.

Better rationale: **the chain behind the ambiguous `mainnet` label isn't established** — the
hardhat config does not define it, and the five addresses are `"0x..."` placeholders, so nobody has
decided what it points at. Omit it and let the check skip.

State plainly that this PR does **not** deliver universal chain validation. Unvalidated after it:

| Network | Why |
|---|---|
| `mainnet` | No `chain_id`; target chain undecided |
| `sepolia_devnet` | In `ALLOWED_NETWORKS` (`utils.py:31`) but **absent from `din_info.json`** entirely |
| any custom network | Nothing to compare against |

So: **B13 is fixed for `sepolia_op_devnet`** — the network everyone actually uses — and `local`.

## 3. Changes

### 3.1 `dincli/config/din_info.json`

```
local             → "chain_id": 1337
sepolia_op_devnet → "chain_id": 11155420
```

Leave `mainnet` alone. Safe to extend: `dindao.py` does load-modify-save (`:48-51`, `:57-59`), so
the key survives runtime writes.

### 3.2 `dincli/cli/utils.py` — `get_w3()`

Target shape (option (a) from §2.6):

```python
class ChainIdMismatchError(Exception):
    """The configured RPC endpoint is on a different chain than the selected network."""


def get_w3(effective_network):
    # Stage 1 — resolve and connect.
    try:
        rpc_url = resolve_network_value(effective_network, "rpc_url")
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            raise ConnectionError("endpoint did not respond")
    except Exception as e:
        # No rpc_url and no {e} here: the URL may carry an API key, and provider
        # exceptions can echo request paths or response bodies derived from it.
        # `from e` keeps the original for debugging without printing it.
        raise ConnectionError(
            f"Could not connect to the configured Ethereum node for network '{effective_network}'"
        ) from e

    expected = load_din_info().get(effective_network, {}).get("chain_id")
    if expected is None:
        return w3

    # Stage 2 — read the chain id. A node can answer is_connected() and still fail here.
    try:
        actual = w3.eth.chain_id
    except Exception as e:
        raise ConnectionError(
            f"Connected to the RPC for network '{effective_network}', but could not read its chain id"
        ) from e

    # Stage 3 — compare, outside both boundaries above.
    if actual != expected:
        raise ChainIdMismatchError(
            f"RPC chain mismatch for network '{effective_network}': "
            f"the endpoint reports chain id {actual}, expected {expected}. "
            f"Check {effective_network.upper()}_RPC_URL in your .env — it points at a different chain."
        )
    return w3
```

Implementation notes:

- `load_din_info` is **defined in this same module** (`:359`). No import needed; forward reference
  resolves at call time.
- `.get(...).get(...)` keeps unknown networks from raising `KeyError`.
- **No user-facing message interpolates `{e}` or the RPC URL** — see §2.5 and the comment above.
  Keep `raise ... from e` so the cause survives for debugging; the CLI renderer prints only the
  outer exception.
- Do not reorder or rename anything else in `utils.py`.

### 3.3 `dincli/cli/core.py` — render the mismatch

Per §2.6, override `GlobalOptionsGroup.invoke()` to catch `ChainIdMismatchError`, print one red
line to stderr, and exit 1. This is the only place presentation happens; `get_w3()` stays pure.

## 4. Verification — corrected

**Rev 1's plan could not have reached the code under test.** `get_en_w3_account_console` dereferences
`self.account.address` *before* `self.w3` (`context.py:83`), and `DinContext.account` exits the
process when no wallet exists (`:70-76`). With an isolated `XDG_CONFIG_HOME` and no wallet, every
CLI command — including `din-info` — dies at account loading and never constructs a Web3.

So verification has two layers.

### 4.1 Direct `get_w3()` tests — transport-level, no wallet needed

Call `get_w3()` directly in a Python shell against the editable `.venv`, with the network selected
via `.env`. Record actual output for each:

| # | Case | Setup | Expected |
|---|---|---|---|
| 1 | Correct chain | `https://sepolia.optimism.io` | Returns a `Web3`; no error |
| 2 | **The real B13 scenario** | `https://mainnet.optimism.io` | `ChainIdMismatchError`, naming 10 vs 11155420 |
| 3 | Unpinned network | `mainnet` (no `chain_id`) | Returns without error. **Live cannot prove `eth_chainId` was never called** — that assertion belongs to the mocked test (§4.3); keep this as a smoke check only |
| 4 | Unreachable RPC | bad host | **Connection** error, not a chain error — and **no URL in the message** |
| 5 | Local | `LOCAL_RPC_URL` at a node whose id ≠ 1337 | Chain error naming 1337 as expected |

Case 4 proves §2.2 kept the failure modes distinct *and* §2.5 removed the leak.

### 4.2 One end-to-end CLI check — with a disposable wallet

Create a throwaway wallet in the isolated config (demo mode is acceptable here — the key is public
and nothing is funded), then run a real command with a wrong-chain RPC. **Assert the exit code and
the user-visible output**, not just "it fails":

- exit code is non-zero
- output contains the chain ids and the network name
- output contains **no** RPC URL and no traceback (per §2.6)

### 4.3 Mocked unit tests — committed, see §5

`tests/test_chain_id_validation.py`. Mock the provider; no network required. Cases:

| Case | Assertion |
|---|---|
| Match | Returns the `Web3` object |
| Mismatch | Raises `ChainIdMismatchError`; message contains both ids and the network name |
| Unpinned network | Returns; **`eth_chainId` is never called** (assert on the mock — the live check cannot prove this) |
| `is_connected() == False` | Raises `ConnectionError`, not a chain error |
| `eth_chainId` itself raises | Raises the stage-2 `ConnectionError`, not a mismatch |
| `load_din_info` raises | Not mislabelled as a mismatch |
| **Credential safety** | Embed a sentinel secret in the RPC URL; assert it appears in **none** of `stdout`, `stderr`, `str(exception)`, or normal CLI output |
| Config values | `local` expects 1337; `sepolia_op_devnet` expects 11155420 |
| CLI boundary | `ChainIdMismatchError` through `GlobalOptionsGroup.invoke()` → exit 1, one red stderr line, no traceback |

### 4.4 Diff scope — allowlist, not a file count

Rev 1's "exactly two files" would have excluded tests. Allowlist:

- `dincli/config/din_info.json`
- `dincli/cli/utils.py`
- `dincli/cli/core.py`
- `tests/test_chain_id_validation.py`

Still assert: no version state (`pyproject.toml`, `dincli/__init__.py`, `dist/`), no `Plans/`,
no `.gitignore` (see §5).

## 5. Tests are committed — resolved in rev 3

Rev 2 treated the test location as an open question for Umer, on the grounds that `/tests/*` is
gitignored (`.gitignore:20`) and force-adding into an ignored path is a structural decision about
someone else's repo.

**That hedge was wrong — the precedent is already established, by our own work.** `feat/din-sdk`
(PR #31) tracks **23 files** under `tests/`, including `tests/test_sdk_web3.py`, and its `.gitignore`
drops the blanket `/tests/*` exclusion while keeping only the `__pycache__` entries. There is a
conventional location and a known convention for getting there. No product decision is needed.

**Decision: commit the tests in this PR, via `git add -f`.**

Force-add the single file rather than editing `.gitignore`, because **PR #31 already changes
`.gitignore`** (9 insertions, 8 deletions) and is still open. Two PRs editing the same file to the
same end invites a pointless conflict, and a repo-wide ignore-policy change does not belong in a
chain-id PR. Once #31 lands, `tests/` is unignored for everyone and no force-add is needed again.

Note this in the PR body so the force-add is visible rather than surprising.

Pasted local output is still worth including as evidence — but it is not a substitute for a
committed regression test, which is what stops the 1337-vs-31337 class of error recurring.

## 6. PR body outline

- Link discussion #79 and Umer's comment anchor; quote the "worth prioritizing" line
- The defect, and the present-tense consequence (GI cannot be closed, not a slash)
- **The placement divergence** from his suggestion, with evidence — and phrased per §2.7: every RPC
  connection is validated, *not* every command
- Why there are three failure stages, and why the mismatch must not be reported as a connection error
- **`local` = 1337**, citing `anvil.sh:5` and `hardhat.config.ts` — note that the obvious 31337 would
  have broken both checked-in launchers
- Verification tables with real recorded output
- **Flag:** hard-fail applies to read-only commands too
- **Flag:** `mainnet` and `sepolia_devnet` stay unvalidated, with the reason — this fixes B13 for
  `sepolia_op_devnet` and `local`, not universally
- **Note the force-add:** `tests/` is still gitignored on `main`; PR #31 already proposes dropping
  that exclusion, so this PR force-adds one file rather than editing `.gitignore` twice
- Note the RPC-URL leak at `:203` is fixed here, not deferred — and that no user-facing message
  interpolates the underlying provider exception either
- Note no conflict with #80 (docs) or #82 (`system.py:56`) — different files

## 7. Follow-ups not in this PR

- Reuse `ctx.w3` in `get_contract_instance()` instead of calling `get_w3()` per contract (§2.8)
- Add `sepolia_devnet` to `din_info.json`, or drop it from `ALLOWED_NETWORKS` — it is currently
  selectable and completely unconfigured
- `mainnet` chain id, once the target chain is decided
- Once this lands, soften `setup.md`'s wrong-chain warning (added in #80) from "the CLI does not
  check this" to a description of the new error
