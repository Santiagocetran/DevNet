# PR B — Validate the RPC chain id on `develop`

**Branch:** `fix/develop-chain-id-validation` (off `develop` @ `bf162c0`) — created, nothing implemented
**Base:** `develop` on `InfiniteZeroFoundation/DevNet`
**Origin:** [discussion #79](https://github.com/InfiniteZeroFoundation/DevNet/discussions/79#discussioncomment-18082657) — row B of the backport split, greenlit by @umeradl
**Ports:** `9a3f855` (#83) and `42f19ca`, both from `main`
**Status:** rev 4 — implemented as `386f9ef`, then post-implementation review found one regression
in this plan's own §3.2. Fixed. Ten findings across three rounds, all upheld.

> **Rev 4 changelog.** Post-implementation analysis of `386f9ef` confirmed the implementation was
> faithful to rev 3 on every point, and mutation-tested the guards to prove they can fail. It also
> found **a regression introduced by this plan, not by the implementer** (§2.10 new).
>
> Rev 3's §3.2 put `resolve_network_value` *inside* stage 1's handler, copying `main`. That converts
> an unresolvable `rpc_url` — a pure configuration error with its own actionable message — into
> "Could not connect to the configured Ethereum node", i.e. it tells an operator with **no RPC
> configured at all** that their node is unreachable. Since `core.py` catches `ConnectionError`, the
> guidance is not merely reworded but erased. That is the exact class of misleading error this PR
> exists to remove, on the fresh-onboarding path that started the whole workstream.
>
> Resolution moves to a stage 0 outside the handler. `main` has the same masking bug and is now a
> fourth divergence (§2.7 row 7) plus a follow-up (§8).

> **Rev 3 changelog.** A second audit found two medium, two low. All four verified and applied.
>
> - **F1b (medium, §2.9, §3.2, §5).** `from None` was not the full fix. It clears `__cause__` and
>   sets `__suppress_context__`, so the *traceback* is clean, but Python still attaches the
>   original as `__context__`. Measured: raising inside the handler leaves `SECRET123` in
>   `err.__context__`; raising after the block exits does not. **Decision: keep the simple
>   in-handler form and state the guarantee precisely** — no credential in the message, in logger
>   output, or in a formatted traceback; the residual on `__context__` is accepted, because reaching
>   it requires deliberately walking the chain and nothing in this codebase (or its dependencies)
>   does. The sentinel-variable alternative was rejected as a readability cost in the hot path
>   against a threat that is not present. §8 carries the follow-up if error reporting is ever added.
>   The stage-2 path gets the same sentinel test as stage 1, so a regression to `from e` there
>   cannot pass unnoticed.
> - **F2b (medium, §4.1).** The direct-`get_w3()` table was not executable: it was headed with one
>   env var while its skip row used a `--network` flag that does not exist at that level, and
>   `sepolia_devnet` reads `SEPOLIA_DEVNET_RPC_URL`, not the OP one. Rewritten per call, and the
>   "never called `eth_chainId`" assertion moved to the mocked test where it can actually be made.
> - **L1 (§2.4).** `ALLOWED_NETWORKS` constrains only an explicit `--network`;
>   `resolve_network(None)` returns the persisted config value unvalidated (`utils.py:206-208`).
> - **L2 (§2.6).** Importer count corrected to four.

> **Rev 2 changelog.** An audit found two high, three medium. All five were re-verified against the
> tree and all five stand.
>
> - **F1 (high, §2.9 new).** `raise ... from e` leaks the credential through the chained cause.
>   Measured: a real provider exception for `https://x.invalid/v3/SECRET123` contains the secret,
>   and it survives into `traceback.format_exception`. `str()` stays clean, so the CLI renderer was
>   never at risk — but `get_w3()` is explicitly kept reusable by library callers, and
>   `logger.exception()` there would leak. Stages 1 and 2 now use `from None`.
> - **F2 (high, §4 rewritten).** The headline live reproduction set `SEPOLIA_OP_DEVNET_RPC_URL`
>   without passing `--network`, and `resolve_network` falls back to config then `local`
>   (`utils.py:200`). Worse, `din-info` reaches `self.account` before `self.w3`
>   (`context.py:102`), so it exits without a wallet before validation runs. This is the same
>   verification flaw rev 2 of the `main` plan corrected, reintroduced. §4 now splits
>   wallet-free `get_w3()` checks from one explicit CLI check.
> - **F3 (medium, §2.1).** "`get_en_w3_account_console()` is skipped entirely for `din-info`" was
>   wrong: only the *group callback's* invocation is skipped, and `din-info` calls it in its own
>   body (`system.py:800`). Placement conclusion unchanged; rationale reworded.
> - **F4 (medium, §2.4, §4.5).** The preservation claim holds — the auditor executed
>   `import_deployments` against isolated data and `chain_id` survived — but the proposed *live*
>   check would rewrite the tracked `din_info.json` in an editable checkout. Now a patched unit
>   test. Also: arbitrary networks are barred by `ALLOWED_NETWORKS`; the real example is
>   `sepolia_devnet`.
> - **F5 (medium, §5).** The stage-1 sanitization test inherited from `main` only exercises
>   `is_connected() == False`, which never produces a URL-bearing provider exception and so proves
>   nothing about scrubbing.
>
> Minor: 14 files tracked under `tests/`, not 7; `get_contract_instance` has four importers, not
> five; the mismatch message should name `config.json` as well as `.env`.

> **This is not a cherry-pick.** `git cherry-pick 9a3f855` onto `develop` conflicts on
> `dincli/cli/utils.py` and `dincli/config/din_info.json`. The *design* ports cleanly — the choke
> point, the three-stage failure model and the exception boundary are all identical here — but the
> surrounding code differs enough that it has to be written rather than applied. §2.7 lists every
> delta from the `main` version.

---

## 1. The defect

Identical to `main`'s B13, and live on `develop` today. `get_w3()` (`dincli/cli/utils.py:331`)
resolves `<NETWORK>_RPC_URL`, builds a `Web3`, checks `is_connected()`, and never asserts the
endpoint is on the chain the user selected:

```python
def get_w3(effective_network):
    rpc_url = resolve_network_value(effective_network, "rpc_url")
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            raise ConnectionError(f"Could not connect to Ethereum node at {rpc_url}")
        return w3
    except Exception as e:
        raise ConnectionError(f"Could not connect to Ethereum node for network '{effective_network}': {e}") from e
```

Swapping `optimism-sepolia` for `optimism-mainnet` in the RPC URL is one word, is accepted
silently, and surfaces only as `ETH Balance: 0` — indistinguishable from an unfunded wallet.
`din-info` gives false reassurance because it prints addresses from local JSON rather than reading
the chain.

The CLI cannot detect this even in principle: **`develop`'s `din_info.json` carries no `chain_id`
for any of its three networks**, so there is nothing to compare against.

**Second defect in the same function, fixed here for the same reason it was on `main`:** the
unreachable-node path interpolates the full `rpc_url` (line 337) *and* the provider exception
(line 340). Both leak credentials — Infura/Alchemy keys live in the URL path, and provider
exceptions echo request paths derived from it.

**Why it matters beyond confusion:** a wrong-chain RPC during the T1 window means the submission
never reaches the real coordinator. The present-tense consequence is not a slash — `slashAggregators`
reverts on the deployed contracts — it is that `endGI` can never run and the Global Iteration
cannot be closed for anyone.

---

## 2. Design decisions

### 2.1 Placement — `get_w3()`, and here it is provably the only site

On `main` this was argued. On `develop` it is measured:

```
$ grep -rn "Web3(Web3.HTTPProvider\|= Web3(" dincli/
dincli/cli/utils.py:335
```

One construction site in the whole package. Two callers, both inside `dincli/cli/`:

| Caller | Path |
|---|---|
| `dincli/cli/context.py:71` | `DinContext._w3`, the CLI path |
| `dincli/cli/contract_utils.py:123` | `get_contract_instance`, imported by four modules: `context.py`, `utils.py`, `dindao.py`, `modelownerd/deploy.py` |

Putting the check in `get_w3()` covers every path with no per-command wiring, and cannot be
bypassed by a command that forgets to opt in.

**Not** in `get_en_w3_account_console()`. The skip-list argument is subtler than rev 1 claimed
(audit F3): only the *group callback's* invocation is skipped, and a listed command may still call
the helper itself — `din-info` does exactly that at `system.py:800`. The real reason stands
regardless: `get_en_w3_account_console` is a CLI-presentation helper that also resolves the wallet,
so hanging validation off it would both miss the `contract_utils` path and couple chain validation
to having a wallet.

The honest coverage statement, matching the corrected wording in the `main` plan:

> Every RPC connection passes through validation. Commands that never construct an RPC connection
> are not validated — because there is nothing to validate.

### 2.2 Three distinct failure stages

A node can answer `is_connected()` and still reject or time out on `eth_chainId`, so the stages get
separate boundaries:

| Stage | Failure | Raises |
|---|---|---|
| 0 — resolve | no `rpc_url` configured | `KeyError`, propagated unchanged (§2.10) |
| 1 — connect | endpoint unreachable | `ConnectionError` |
| 2 — read chain id | connected but `eth_chainId` fails | `ConnectionError`, distinct message |
| 3 — compare | wrong chain | `ChainIdMismatchError` |

Stage 3 sits **outside** stage 1's `try`. `develop`'s current function wraps everything and
re-raises as "Could not connect to Ethereum node", so a mismatch reported through it would point at
the wrong problem entirely.

### 2.3 `local` is 1337, not 31337

Verified on this branch, both toolchains agree:

```
foundry/anvil.sh:5            --chain-id 1337
hardhat/hardhat.config.ts:56  chainId: 1337
```

Pinning the generic Hardhat default of 31337 would reject the project's own local nodes.
`hardhat.config.ts:69,85` confirm `11155420` for the OP Sepolia entries.

### 2.4 Absent `chain_id` means skip — and on `develop` this is load-bearing

`main` skips validation when a network has no `chain_id`, which there only affects the unconfigured
`mainnet` placeholder. On `develop` the same rule carries real weight, because **`develop` has
`import-deployments`, which `main` does not**:

```python
# dincli/cli/system.py, import_deployments
din_info = load_din_info()
entry = din_info.setdefault(effective_network, {})   # <- can create a brand-new network
...
save_din_info(din_info)
```

Two consequences, both checked:

1. **A reachable network can have no `chain_id`.** Rev 1 said "a user can introduce any network",
   which overstated it. The precise rule is narrower still than rev 2 claimed: an explicit
   `--network` value is checked against `ALLOWED_NETWORKS` (`utils.py:201`), but
   `resolve_network(None)` returns `get_config("network")` unvalidated (`utils.py:206-208`), so a
   hand-edited persisted config can still select an arbitrary name. The supported-workflow case is
   the one that matters here, and it is already real:

   ```
   ALLOWED_NETWORKS = ["local", "sepolia_devnet", "sepolia_op_devnet", "mainnet"]
   present in din_info.json:  local, sepolia_op_devnet, mainnet
   reachable but absent:      sepolia_devnet
   ```

   So `--network sepolia_devnet` is accepted today and has no `din_info` entry at all. Beyond that,
   `import-deployments` can populate an entry without a `chain_id`. Hard-failing on absence would
   break both. Skip is the only safe policy.
2. **`chain_id` survives the import.** The command only assigns the platform address keys onto the
   existing entry (`coordinator`, `token`, `stake`, `registry`, `proxy_admin_*`) rather than
   replacing the object, so an added `chain_id` is preserved. Its own docstring states this; the
   `setdefault` + per-key assignment confirms it, and the audit executed `import_deployments`
   against isolated temporary data with `load_din_info`/`save_din_info` patched: `chain_id`,
   `representative` and the other unrelated keys all survived while the address keys updated.
   **Worth an explicit regression test** (§5), since a future refactor to
   `din_info[network] = {...}` would silently drop the validation.

`mainnet` stays unvalidated for the same reason as on `main`: its addresses are `"0x..."`
placeholders, so it is not a usable network yet and inventing a chain id for it would be a guess.

### 2.5 Hard-fail, not warn

A warning on a wrong-chain RPC is a warning the operator will scroll past, and every subsequent
read returns plausible-looking zeros. The failure this prevents is silent by nature, so the
response has to be loud.

### 2.6 `get_w3()` stays pure; rendering happens in `core.py`

`get_w3()` raises and never exits. Rendering and `sys.exit` happen once at the CLI boundary in
`GlobalOptionsGroup.invoke()`, which every command dispatches through.

Rationale is stronger on `develop` than on `main`: `get_contract_instance` in `contract_utils.py`
is a library-shaped function imported from four modules, and a utility that terminates the process
is hostile to any non-CLI caller — including the SDK work on `feat/din-sdk`.

`sys.exit(1)`, not `click.exceptions.Exit`: Typer re-raises the latter when
`pretty_exceptions_enable=False`, printing the clean message *and* a full traceback.

### 2.7 Deltas from `main`'s version — the reason this is not a cherry-pick

| # | `main` | `develop` | Consequence |
|---|---|---|---|
| 1 | `core.py` `GLOBAL_OPTIONS = {"--network", "--version", "-v"}` | adds `--wallet`, `--demokey`; `parse_args` consumes a value for all three | **Add `invoke()` only. Do not touch `parse_args`** — porting `main`'s would drop `--wallet`/`--demokey` value handling |
| 2 | `click` imported at `core.py:7`, declared in `pyproject.toml` | nothing imports `click`; not declared | This PR *introduces* the import, so **`42f19ca` lands here**, not in PR A |
| 3 | `din_info.json` has 5 address keys per network | `local` also carries `default_manifest`, `default_services`, `default_abis`, `default_requirements`, `proxy_admin` | `chain_id` is purely additive; keep `indent=2` to match `save_din_info` |
| 4 | no `import-deployments` | writes `din_info.json` at runtime | §2.4 — skip-on-absent becomes load-bearing, plus a preservation test |
| 5 | leak is `{rpc_url}` only | leaks `{rpc_url}` **and** `{e}` | Both must go |
| 7 | wraps `resolve_network_value` in stage 1, masking config errors as connection errors | resolves in stage 0, outside the handler | `develop` reports a missing `rpc_url` correctly where `main` does not (§2.10). A genuine improvement over the source, not a porting slip — say so in the PR body |
| 6 | `tests/test_chain_id_validation.py` is new | absent, and `develop` has no `tests/conftest.py` | Port the file; patch points (`utils.load_din_info`, `utils.resolve_network_value`, `utils.Web3`) exist identically here |

### 2.8 Cost

One extra JSON-RPC round trip (`eth_chainId`) per `Web3` construction, on a connection that has
already completed `is_connected()`. `web3.py` does not cache it. This is not free but it is far
below the cost of any contract call the command is about to make, and it is skipped entirely for
networks with no `chain_id`.

### 2.9 Credential secrecy holds through the chained cause, not just `str()` — audit F1

Rev 1 said both leaks "must go" and then used `raise ... from e`, which keeps the provider
exception as `__cause__`. Measured on this branch against `https://x.invalid/v3/SECRET123`:

```
provider exception type      : ConnectionError
str(provider exception)      : contains SECRET123
str(our wrapped error)       : clean
traceback.format_exception() : contains SECRET123   <-- via __cause__
```

So the CLI was never at risk — `GlobalOptionsGroup.invoke` renders `str(e)` only. But §2.6
deliberately keeps `get_w3()` reusable by library-shaped callers, and one `logger.exception()` or
uncaught traceback in such a caller prints the chain. A guarantee that only holds inside the CLI
boundary is not the guarantee the design claims.

**Resolution: in-handler `raise ... from None`, with the guarantee stated precisely.**

`from None` clears `__cause__` and sets `__suppress_context__`, which covers every surface a person
or a log actually sees. It does *not* remove the original from `__context__`. Measured:

```
raise INSIDE except:   __cause__ None, __suppress_context__ True, traceback clean, __context__ HAS secret
raise AFTER  except:   __cause__ None, __suppress_context__ True, traceback clean, __context__ clean
```

Raising after the handler exits closes that last gap, but needs a sentinel variable and an
`if failure is not None:` in the function every RPC connection passes through. That is a real
readability cost in a hot path, paid against a threat that is not in this codebase: `__context__` is
only reachable by code that deliberately walks the chain, and nothing here does — there is no
error-reporting SDK in the dependency list that would.

The leak this PR exists to fix was a **printed message**. The simple form closes that completely.

So: keep the in-handler form, and **document what is actually promised** rather than overclaiming.

```python
except Exception as e:
    # No {e} and no rpc_url: the provider exception embeds the credential-bearing
    # URL. from None keeps it out of str() and out of any formatted traceback.
    # It remains on __context__ — see 2.9 for why that is accepted here.
    logger.debug("connect failed for network '%s': %s", effective_network, type(e).__name__)
    raise ConnectionError(
        f"Could not connect to the configured Ethereum node for network '{effective_network}'"
    ) from None
```

**The guarantee, exactly:** no credential appears in the error message, in `logger` output, or in a
formatted traceback. The originating provider exception remains on `__context__`, so a future
error-reporting integration that walks context chains would need to scrub or disable that — noted in
§8 as a follow-up, and pinned by a test asserting `__suppress_context__ is True` so a regression to
`from e` fails loudly.

**Why not sanitize the cause instead:** `develop` already has `sanitize_rpc_url` at
`context.py:26`, which masks the last path segment. It cannot be reused here — `context.py` imports
from `utils.py` (`context.py:18`), so `utils.py` importing back is a cycle. Promoting that helper
into `utils.py` is a reasonable follow-up but is scope creep for this PR, and it only scrubs a URL
handed to it, not arbitrary provider text that may embed the URL in other forms.

Stage 3 keeps no cause at all — it builds its message from two integers and a network name.

### 2.10 Resolution is stage 0, outside stage 1's handler — post-implementation

`resolve_network_value` raises a `KeyError` that names the env var and config path it checked:

```
Could not resolve 'rpc_url' for network 'sepolia_op_devnet'.
→ Checked .env for 'SEPOLIA_OP_DEVNET_RPC_URL'
→ Checked config.json → networks.sepolia_op_devnet.rpc_url
```

Wrapping that in stage 1 replaces it with "Could not connect to the configured Ethereum node",
which is actively wrong — nothing is configured. And because `GlobalOptionsGroup.invoke` catches
`ConnectionError` and renders a single line, the actionable text disappears entirely rather than
surviving in a traceback.

Measured before and after the fix:

```
inside the try : ConnectionError: Could not connect to the configured Ethereum node for ...
stage 0        : KeyError: Could not resolve 'rpc_url' ... → Checked .env for 'SEPOLIA_OP_DEVNET_RPC_URL'
```

Letting it propagate is safe for §2.9's guarantee: the `KeyError` text contains the env var *name*
and the config path, never a URL value. Verified — the `SECRET123` sentinel still appears in neither
`str()` nor the formatted traceback after the change.

Not added to `invoke()`'s except tuple: catching `KeyError` at the CLI boundary would swallow
unrelated `KeyError`s from anywhere in the command tree, which is a much worse trade than one
traceback on a misconfiguration.

---

## 3. Changes

### 3.1 `dincli/config/din_info.json`

Add one key to two networks. Additive, no reordering, `indent=2`:

```json
"local": { "chain_id": 1337, ... }
"sepolia_op_devnet": { "chain_id": 11155420, ... }
```

`mainnet` gets nothing (§2.4).

### 3.2 `dincli/cli/utils.py`

New exception near the other module-level definitions:

```python
class ChainIdMismatchError(Exception):
    """The configured RPC endpoint is on a different chain than the selected network."""
```

Rewrite `get_w3()` to the three-stage form. Neither new message may contain `rpc_url` or `{e}`,
and stages 1 and 2 use `from None` so the credential is not reachable through `__cause__` either
(§2.9). The mismatch text names both configuration sources, since `resolve_network_value` reads
`.env` *and* the persisted config.

```python
def get_w3(effective_network):
    # Stage 0 — resolve, outside stage 1's handler. See 2.10.
    rpc_url = resolve_network_value(effective_network, "rpc_url")

    # Stage 1 — connect.
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            raise ConnectionError("endpoint did not respond")
    except Exception as e:
        # from None: keeps the credential out of str() and any formatted traceback.
        # See 2.9 for the exact guarantee and the accepted __context__ residual.
        logger.debug("connect failed for network '%s': %s", effective_network, type(e).__name__)
        raise ConnectionError(
            f"Could not connect to the configured Ethereum node for network '{effective_network}'"
        ) from None

    expected = load_din_info().get(effective_network, {}).get("chain_id")
    if expected is None:
        return w3

    # Stage 2 — read the chain id.
    try:
        actual = w3.eth.chain_id
    except Exception as e:
        logger.debug("chain id read failed for network '%s': %s", effective_network, type(e).__name__)
        raise ConnectionError(
            f"Connected to the RPC for network '{effective_network}', but could not read its chain id"
        ) from None

    # Stage 3 — compare, outside both boundaries above.
    if actual != expected:
        raise ChainIdMismatchError(
            f"RPC chain mismatch for network '{effective_network}': "
            f"the endpoint reports chain id {actual}, expected {expected}. "
            f"Check {effective_network.upper()}_RPC_URL in your .env, or this network's rpc_url "
            f"in your dincli config — it points at a different chain."
        )
    return w3
```

`load_din_info` is already defined in this module (`:550`), so no new import.

### 3.3 `dincli/cli/core.py`

Add `import sys`, `import click`, `from dincli.cli.utils import ChainIdMismatchError`, and an
`invoke()` override on `GlobalOptionsGroup`. **`parse_args` is left exactly as it is** (§2.7 row 1).

```python
def invoke(self, ctx):
    try:
        return super().invoke(ctx)
    except (ChainIdMismatchError, ConnectionError) as e:
        click.secho(str(e), err=True, fg="red")
        sys.exit(1)
```

Watch for an import cycle: `core.py` currently imports nothing from `dincli`. `utils.py` imports
`contract_utils`, which does its `get_w3` import *inside* the function, so `utils` does not import
`core`. Confirm with a bare `python -c "import dincli.main"` after the edit.

### 3.4 `pyproject.toml`

Add `"click>=8.1.0"` to `dependencies` — now justified, because §3.3 introduces the first `click`
import on this branch.

> **Merge-order note.** PR A (#97) rewrites this same dependency list. #97 was opened first and is
> expected to merge first, so **rebase this branch onto `develop` once #97 lands** and resolve
> `pyproject.toml` as the union — #97's four declarations plus this PR's `click`. If #97 is still
> open when this is ready, open anyway and note the expected conflict in the PR body; do not block
> the chain-id fix behind it. #97's imported-vs-declared test will fail loudly if the rebase drops
> `click`, so the mistake cannot ship quietly.

### 3.5 `tests/test_chain_id_validation.py` — new

Port from `main`, adapted per §2.7 row 6.

---

## 4. Verification — rewritten after audit F2

Rev 1's headline reproduction could not have reached the code under test. Two independent reasons,
both verified:

1. **Network selection is not driven by the env var.** `resolve_network(cli_network=None)` falls
   back to persisted config and then to `local` (`utils.py:200`). Setting
   `SEPOLIA_OP_DEVNET_RPC_URL` without passing `--network sepolia_op_devnet` exercises whatever
   network happens to be configured.
2. **`din-info` needs a wallet before it needs a chain.** It calls
   `get_en_w3_account_console()` in its own body (`system.py:800`), and that helper touches
   `self.account.address` *before* `self.w3` (`context.py:102`). With no registered wallet it exits
   before validation ever runs.

This is the same flaw rev 2 of the `main` plan corrected, reintroduced here. The fix is to split
the wallet-free checks from the CLI check.

### 4.1 Direct `get_w3()` — no wallet, no CLI

A short REPL/script driving `get_w3()` directly reaches the code under test with nothing else in
the way. Four cases:

There is no `--network` flag at this level — call `get_w3("<network>")` directly, and note that
each network reads its *own* env var.

| Case | Call | Env | Expect |
|---|---|---|---|
| wrong chain | `get_w3("sepolia_op_devnet")` | `SEPOLIA_OP_DEVNET_RPC_URL=https://mainnet.optimism.io` | `ChainIdMismatchError`, names 10 and 11155420 |
| correct chain | `get_w3("sepolia_op_devnet")` | the real devnet RPC | returns a `Web3`, no raise |
| unreachable | `get_w3("sepolia_op_devnet")` | `https://x.invalid/v3/SECRET123` | `ConnectionError`, stage-1 message |
| skip | `get_w3("sepolia_devnet")` | `SEPOLIA_DEVNET_RPC_URL=<any reachable endpoint>` | returns a `Web3` without raising |

The skip row is a **smoke check only**. A live run cannot show that `eth_chainId` was never called;
that assertion belongs exclusively to the mocked test in §5, which can observe the absence of the
call.

### 4.2 One CLI check, with the network named and a wallet present

```bash
SEPOLIA_OP_DEVNET_RPC_URL=https://mainnet.optimism.io \
  dincli --network sepolia_op_devnet system din-info
```

Requires a registered disposable wallet (§4.2 of the `main` plan hit the same prerequisite). Assert
all four: exit code 1, both chain ids present, exactly one red line, and no traceback.

### 4.3 `local`

Start `./foundry/anvil.sh`, confirm `--network local` passes with 1337 rather than being rejected.

### 4.4 Credential leak — assert the negative, including the chain

Point the RPC at `https://x.invalid/v3/SECRET123` and grep for `SECRET123` in **three** places, not
one:

1. `str(exc)` — was already clean in rev 1
2. full CLI output including stderr
3. `traceback.format_exception(...)` and `exc.__cause__` — the case §2.9 found leaking

Run this at the `get_w3()` level per §4.1, since the CLI path cannot be reached without a wallet.

### 4.5 `import-deployments` preserves `chain_id` — as a patched test, not a live run

Rev 1 said to run the real command and re-read `din_info.json`. **Do not.** `save_din_info` writes
to `files("dincli")/config/din_info.json`, which in an editable checkout is the tracked repo file —
the live run dirties the working tree and can corrupt shipped config. The existing integration
harness backs the file up for exactly this reason (`tests/dincli/conftest.py:373`).

Patch `load_din_info`/`save_din_info` and assert `chain_id` survives, which is how the audit
confirmed the behaviour.

---

## 5. Tests (committed)

`tests/` already tracks 14 files on `develop`, so these are committed alongside.

| Group | Asserts |
|---|---|
| Stage 0 — unresolvable `rpc_url` | propagates the `KeyError` with its env-var guidance intact, is **not** a `ConnectionError`, and never constructs a `Web3`. Guards §2.10 against a revert |
| Stage 1 — unreachable | `ConnectionError`; message contains neither URL nor provider text |
| Stage 1 — **leaking provider exception** (audit F5) | `Web3(...)`/`is_connected()` raising `Exception("request failed: https://x.invalid/v3/SECRET123")` must not surface the secret in `str(exc)`, in `traceback.format_exception(exc)`, or via `exc.__cause__`. `main`'s inherited test only sets `is_connected() -> False`, which never produces a URL-bearing exception and so proves nothing about scrubbing |
| Stage 2 | `eth_chainId` raising yields `ConnectionError` with the stage-2 message, not stage 1's |
| Stage 2 — **leaking exception** | same sentinel treatment as stage 1. Without it, a future regression of stage 2 back to `from e` passes unnoticed |
| Both stages — reachability | `exc.__cause__ is None` and `exc.__suppress_context__ is True`, plus no sentinel in `str(exc)` or in `traceback.format_exception(exc)`. Do **not** assert on `__context__` — §2.9 accepts that residual deliberately, so a test forbidding it would contradict the design |
| Stage 3 | mismatch raises `ChainIdMismatchError` naming both ids; match returns the `Web3` |
| Skip — absent key | no `chain_id` returns without calling `eth_chainId`; only a mock can assert the *absence* of the call |
| Skip — absent network | `sepolia_devnet` (allowed, unshipped) resolves without raising |
| Config | `local` is 1337 and `sepolia_op_devnet` is 11155420 in the shipped file; `mainnet` has none |
| Rendering | `GlobalOptionsGroup.invoke` turns both exception types into one red line and exit 1, no traceback |
| `parse_args` | `--wallet VALUE` **and** `--demokey VALUE` still consume their values — guards §2.7 row 1. `tests/test_connect_wallet.py:666` already covers trailing `--wallet VALUE`; add the `--demokey` equivalent |
| `import-deployments` | `chain_id` survives an import, with `load_din_info`/`save_din_info` patched (§4.5) |
| Deps | `click` is declared — extends PR A's imported-vs-declared audit, which will also catch it if the rebase drops it |

Patch points: `utils.load_din_info`, `utils.resolve_network_value`, `utils.Web3` — all present on
`develop` under the same names.

---

## 6. PR body outline

1. Row B of the #79 split; ports `9a3f855` + `42f19ca`
2. Why it is a rewrite not a cherry-pick — the §2.7 table
3. The defect, with the silent-`ETH Balance: 0` reproduction
4. Three stages, and why stage 3 sits outside stage 1
5. `local` is 1337, measured from both toolchains
6. Skip-on-absent, and why `import-deployments` makes it load-bearing here
7. The credential leak — both the message *and* the chained cause, with the `SECRET123` negative
   test over `traceback.format_exception`, not just `str()`
8. `click` arrives here rather than in PR A, and why
9. Live verification output
10. The stage-0 divergence: `develop` now reports a missing `rpc_url` correctly, `main` does not —
    deliberate improvement over the source commit, with the `main` follow-up noted
11. The pyproject merge-order note vs #97 — union resolution, one line

## 7. Branch base — confirmed by audit

Stay based on `develop`; do **not** stack on PR A (#97). A is a broader, independent change
(dependency declarations, Python floor, two commands, its own tests), and stacking would block the
higher-priority chain-id fix behind it. `click` still belongs here, because this PR introduces the
first direct import. If A lands first, its imported-vs-declared test reinforces that `click` must
survive the rebase.

## 8. Follow-ups not in this PR

- **`din-info` reading the chain.** It still echoes local JSON. A `--verify` flag that compares the
  shipped addresses against deployed bytecode is a separate, larger change.
- **`mainnet`'s placeholder addresses.** Out of scope; it is not a usable network yet.
- **`__context__` scrubbing.** If an error-reporting integration that walks context chains is ever
  added (Sentry and similar do), the provider exception behind a stage-1/2 failure becomes
  reportable and would carry the RPC URL. Either scrub at the integration boundary or move to the
  raise-outside-the-handler shape considered in §2.9. Also the natural moment to promote
  `sanitize_rpc_url` out of `context.py` into `utils.py`.
- **`main` has the stage-0 masking bug** (§2.10). `main:get_w3` still resolves inside its stage-1
  handler, so a `main` user with no RPC configured is told the node is unreachable. One-line fix,
  worth a separate small PR there once this lands.
- **Backporting to `main`** is not needed — `main` already has both commits. This PR closes the gap
  in the other direction.
