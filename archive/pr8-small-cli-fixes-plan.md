# PR 8 — the small CLI bundle

**Branch:** `fix/cli-small-fixes` (off `main` @ `e83c589`, already created)
**Base:** `main`. Conflict-free against #80, #82, #83, #84, #85 (§2)
**Origin:** [discussion #79](https://github.com/InfiniteZeroFoundation/DevNet/discussions/79#discussioncomment-17972890) — the remainder of @umeradl's "CLI (`main`, mostly small/independent)" list
**Status:** rev 3 — twice audited. Ready to implement.

> **Rev 2 changelog.** An audit found eight issues; all verified against the tree and all upheld.
> The password fix missed a **second** call site (§7). `read-stake` cannot use the retry helper at
> all (§3). The retry contract said "never raises" without defining the all-reads-fail case (§3.1).
> The Python 3.9 rationale was wrong — resolution fails, it does not install-then-break (§6).
> Test mechanics needed specifics (§8). And **issue #37 is not the CLI bug** — it is a DevNet 2.0
> staking redesign, so this PR must not claim to close it (§4.1).
>
> **Rev 3 changelog.** A second audit found one blocker and four corrections, all upheld. The retry
> return type could not express its own contract — `(baseline, False)` was ambiguous between "read
> succeeded and matched baseline" and "no read succeeded" (§3.1). The conflict table omitted three
> planned hunks (§2). The Python rationale still carried a false alternative (§6). The password
> message could print twice (§7). And the isolated-CLI verification could not have worked as
> written — the path constants bind at import (§9).

---

## 1. Scope

Umer's list, minus the whitelist item already shipped in #82:

| # | Item | Files |
|---|---|---|
| A | `buy()` balance retry (B10) | `cli/utils.py` (new helper), `cli/aggregator.py`, `cli/auditor.py` |
| B | `stake()` ignores its `amount` argument (see §4.1 on #37) | `cli/aggregator.py`, `cli/auditor.py` |
| C | Demo-mode warning styling + default `--mode no` | `cli/system.py` |
| D | Backport the Python floor from `develop` | `pyproject.toml` |
| E | *Beyond the wrap-up list:* `_get_password` red ❌ (B6) | `cli/utils.py` |

E is in the same file family and the same class of defect, and Umer endorsed a specific fix for it in the thread — but it is **not** in his wrap-up list, so flag it in the PR body as easy to drop, the way C2–C4 were handled in #80.

## 2. Conflict surface — clean against all five open PRs

Verified by file and hunk:

Rev 2's table omitted three planned hunks: the new helper, the second password call site, and the
demo-key provenance flag. Complete picture, with their hunks read from the actual diffs:

| Open PR | File | Their hunk | Ours | Collides? |
|---|---|---|---|---|
| #80 | `system.py` | `@@ -165,13` and `@@ -180,11` (docstring) | `:126`, **`~208-213`**, `:269` | no — nearest gap ~17 lines |
| #82 | `system.py` | `:56` skip-list | as above | no |
| #85 | `system.py` | `:56` + appended command | as above | no |
| #83 | `utils.py` | `@@ -195,15` (`get_w3`) | `_get_password` ~294-307, `_cache_password_if_needed` `:333`, **new helper** | no |
| #84 | `utils.py` | `@@ -88,15` (`resolve_ipfs_config`) | as above | no |

**Placement decisions that keep it that way:**

- **The new `read_after_write` helper goes at the end of `utils.py`** (the module runs to 586 lines),
  not near `get_w3`. Putting it beside `get_w3` would land it inside #83's `@@ -195,15` hunk.
- **The provenance flag is set at `~208-213`**, where `get_demo_private_key()` is called — the only
  place provenance is known. #80's last `system.py` hunk ends around `:191`, so there is roughly a
  17-line gap. Comfortable, but the closest call in the set.

`aggregator.py`, `auditor.py` and `pyproject.toml` are touched by nothing else. **Re-run
`git merge-tree` against all five branches once the code exists** — these are predictions from
planned line numbers, not measurements.

## 3. A — `buy()` balance retry

`aggregator.py:48` reads `balanceOf` immediately after `wait_for_transaction_receipt`. Against a
load-balanced RPC that read can hit a node behind the mined block, printing `0` after a successful
100 DIN purchase — which invites the operator to buy again.

**Correction to the brief.** Umer wrote *"Same pattern's probably worth applying to `stake()`/`read-stake`
if they have the same shape."* Checked: **they don't.**

- `stake()` has **no post-write read at all** — it prints success from the receipt and returns
  (`aggregator.py:100-104`). Nothing to race.
- `read-stake` is a standalone command doing a single read (`:115`). It only races if run
  immediately after `stake`, which the documented flow does do — but seconds apart, in a separate
  process. Lower risk.

So the retry belongs in `buy()` **and nowhere else**.

**`read-stake` is excluded, and cannot be included.** The helper needs a pre-write baseline, and a
standalone `read-stake` process has no access to the balance observed before the earlier staking
transaction. Passing its own current value as the baseline would make it wait for an increase that
is never coming — a guaranteed timeout on every run. Supporting it properly would need transaction
or block context, or persisted state; not a helper call. Dropped, including from the follow-ups.

**Design — poll for the change, not a blind sleep.** Capture the balance *before* the purchase, then
poll until it rises above that baseline:

```python
class ReadResult(NamedTuple):
    value: int       # best value available (see `observed`)
    settled: bool    # True iff a read showed value > baseline
    observed: bool   # False iff every read raised; then `value` is the baseline


def read_after_write(read_fn, *, baseline, attempts=5, delay=2.0) -> ReadResult:
    """Poll a read that follows a confirmed write, tolerating RPC lag.

    Public endpoints are load-balanced and eventually consistent, so a read
    issued straight after a receipt can land on a node behind the block.
    Does not propagate ordinary read_fn exceptions.
    """
```

Lives in `cli/utils.py`, imported by both `aggregator.py` and `auditor.py`.

### 3.1 Exact contract

"Never raises" was underspecified — it did not say what happens when *every* attempt raises. Pin it:

- Read **immediately**; sleep only *between* attempts, never before the first.
- Require `attempts >= 1`.
- Catch transient read exceptions — `Exception`, **never** `BaseException` (a `KeyboardInterrupt`
  mid-poll must still interrupt).
- Track the last **successfully observed** value.

**Why three fields, not two.** Rev 2 returned `(value, settled)`, which cannot express its own
contract: a read that succeeded and happened to equal the baseline, and a run where *every* read
raised, both collapse to `(baseline, False)` — yet they warrant different wording to the operator.
`observed` separates them:

| Case | Result |
|---|---|
| A read showed an increase | `(new_value, True, True)` |
| Reads succeeded, none above baseline | `(last_observed, False, True)` |
| **Every** read raised | `(baseline, False, **False**)` |

In the last case the value is the **pre-write** balance and must be described as such — never as
"the last value read", which would be a false claim.

**"Never raises" was also wrong** and is withdrawn. The helper *does* raise for `attempts < 1`
(a programming error, not a runtime condition), and `KeyboardInterrupt` must propagate. The accurate
phrasing is **"does not propagate ordinary `read_fn` exceptions."**

**The semantic that matters:** exhausting the attempts is **not** a failure. The receipt already said
`status == 1`. On timeout print the last observed value plus a note that the endpoint may be lagging
— never anything resembling "purchase failed". Same rule as the bridge command's L2 poll (#85 §3.5),
same reason: an operator who reads failure retries a successful write.

The helper takes **no console** — rendering is the caller's job, so the no-failure-language rule is
asserted at the `buy()` call sites, not on the helper (§8).

## 4. B — `stake()` ignores `amount`

`stake(ctx, amount: int)` accepts the argument and then hardcodes `MIN_STAKE` in all three places:
the balance check (`aggregator.py:68`), `approve` (`:76-77`), and `stake` (`:92-93`).
`auditor.py` is identical in shape at `:68`, `:76-77`, `:92-93`.

**Fix, per file:**

- `stake_amount = Web3.to_wei(amount, "ether")` — `stake 10` means 10 DIN, matching the docs
- refuse if `stake_amount < MIN_STAKE` before sending anything. The contract enforces this too —
  `DinValidatorStake.sol:73` reverts `AmountLessThanMinStake` — so catching it locally saves a
  wasted transaction and gives a better message
- balance check becomes `balance < stake_amount`, not `< MIN_STAKE`
- `approve(spender, stake_amount)` and `stake(stake_amount)`

**Do not port `develop`'s refactor.** `develop` fixed this by extracting `cli/dintoken.py` with a
shared `stake_dintokens()`; `main` has no such module. Pulling it in would drag `develop`'s structure
into a release branch for a six-line behaviour fix. The duplication between `aggregator.py` and
`auditor.py` already exists and is left as-is — say so in the PR body so it reads as a decision
rather than an oversight.

**Note for the PR body:** staking is **additive** — `DinValidatorStake.sol:80` does
`validator.stake += amount`. So this fix means `stake 25` now actually stakes 25 DIN rather than
silently staking 10.

### 4.1 Do **not** close issue #37

Umer wrote "Tracking under #37", and it is easy to read that as "this PR fixes #37". It does not.
Issue #37 is titled *"P3 staking: DAO-settable floor, per-model stake requirements,
concurrent-registration cap, withdrawal queue"* — a DevNet 2.0 mechanism-design epic covering a
DAO-settable `minStake`, per-model stake sizing, concurrent-GI stake accounting, and a withdrawal
queue. The CLI defect was raised in a **comment** on it, not in its scope.

Reference it for context; **never** use `Fixes #37` or any closing keyword. Closing a design epic
with a six-line CLI fix would lose the actual work item.

## 5. C — Demo mode

### 5.1 The save message (`system.py:269`)

Currently `[green]✅ Wallet saved in DEMO MODE (plaintext)![/green]` — styled as success.

**Precision point Umer's framing misses.** That line fires for *any* demo-mode save, but the key is
only publicly known when it came from `--account N` → `get_demo_private_key()`. If the operator
pasted their own key with demo mode on, it is *their* key in plaintext — bad, but not public. So:

- **always**: red/yellow, and state the key is stored **unencrypted on disk**
- **only when the key came from the demo accounts file**: add that it is a **publicly known Hardhat
  development key that anyone can derive**, and must never hold funds

Getting this wrong in the other direction — telling someone their own key is public — would be its
own bug.

### 5.2 The default (`system.py:126`)

`mode: str = typer.Option("yes", ...)` → `"no"`.

This is the one **behaviour change** in the PR: a bare `dincli system configure-demo` currently
switches demo mode *on*. Umer endorsed it tentatively (*"maybe alongside defaulting `--mode` to
`no`"*), so flag it prominently rather than burying it. Low risk — anyone relying on the current
default is relying on a footgun — but it is a real change and reviewers should see it as one.

## 6. D — Python floor

`pyproject.toml:10`: `requires-python = ">=3.9"` → `">=3.10"`.

**Corrected rationale.** Rev 1 said a 3.9 host "installs cleanly and then fails at runtime". Wrong:
`py-cid` 0.5.0 declares `Requires-Python: >=3.10` (confirmed from the installed distribution's
metadata), so a modern resolver refuses it on 3.9 rather than installing it. The real defect is
**inconsistent project metadata** — `dincli` advertises 3.9 support while a required dependency does
not — which surfaces as a confusing resolution failure. (Not "resolves to an older `py-cid`" — the
constraint is `py-cid>=0.5.0`, so nothing older is eligible.)
The fix is unchanged; only the reason for it needed correcting.

Already on `develop` (commit `45976b2`, from PR #14) and never backported. **Do not touch
`version = "0.1.0"` at `:7`** — that is Umer's 0.2.0 release commit.

## 7. E — `_get_password` red ❌ (B6)

`_get_password` (`utils.py:304`) calls `get_env_key("DIN_WALLET_PASSWORD")` with the default
`verbose=True`, so a miss prints a red ❌ that reads fatal — even though the function then falls
through to the session cache and finally an interactive prompt. It stopped progress during onboarding.

**There is a second call site, and rev 1 missed it.** `_cache_password_if_needed` (`utils.py:333`)
makes the same optional lookup, also with the default `verbose=True`. So even after a password is
successfully obtained from the session cache or a prompt, caching it prints the misleading red ❌
again. Both optional lookups need `verbose=False`.

Fix as Umer specified: `verbose=False` **at these two call sites only**. He was explicit that
`get_env_key` must not be downgraded wholesale — RPC URLs and private keys use it too, and a miss
there is genuinely fatal. He was right.

**Print the informational line exactly once**, or the fix trades one duplicated message for another:

- `_get_password` — query silently, and print **one** informational line when falling through to
  another source.
- `_cache_password_if_needed` — query silently and print **nothing**. It is an internal bookkeeping
  check; the user has already been told.

Assert the non-duplication explicitly (§8.4).

**Test mechanics matter here.** `get_env_key` only prints the ❌ when a `.env` file **exists** and
lacks the key (`utils.py:119-124`); with no `.env` at all it returns the default silently. So the
test must create a `.env` **without** `DIN_WALLET_PASSWORD`, or it passes without exercising the bug
at all.

## 8. Tests — `tests/test_cli_small_fixes.py`

Force-added (`tests/` is gitignored on `main`; #31 already changes `.gitignore`).

### 8.1 Mechanics that must be got right first

- **Patch `time.sleep`.** `stake()` already sleeps 5s between approve and stake; unpatched, the
  stake tests cost ten seconds each run. The retry helper's delay needs patching too.
- **Rich strips markup from captured output**, so "the message is not green" cannot be asserted from
  plain captured text. Inspect the argument passed to a mocked `console.print`, or force ANSI.
- **"No transaction below minimum" means no transaction at all** — assert `estimate_gas`, `approve`,
  `stake`, signing and `send_raw_transaction` are *all* uncalled. Asserting only on
  `send_raw_transaction` would pass even if the code built and signed one.

### 8.2 B — stake amount, for aggregator **and** auditor

`approve` and `stake` both receive `to_wei(amount)`, not `MIN_STAKE`; `stake 25` sends 25e18;
below-minimum is refused with nothing built or sent (§8.1); `stake 10` behaves exactly as today —
the documented path must not change.

**Balance comparison:** test `stake 25` with a **20 DIN** balance. That is adequate under the old
`MIN_STAKE` check and insufficient under the new one, so it is the only case that actually proves
the comparison moved to `stake_amount`. A zero-balance test would pass either way.

### 8.3 A — retry, at both layers

**Helper** — one case per row of §3.1's table, asserting **all three** fields:

- first read already increased → `(new, True, True)`, and **no sleep before the first attempt**
- increase appears on a later attempt → `(new, True, True)`
- reads succeed but never exceed baseline → `(last, False, **True**)`
- **every read raises** → `(baseline, False, **False**)`
- `attempts=0` → raises (programming error, not a runtime condition)
- `KeyboardInterrupt` from `read_fn` propagates rather than being swallowed

The third field is the point: without asserting `observed`, the two `False` rows are
indistinguishable and the caller cannot word them correctly.

**Callers — the part helper tests cannot cover.** For `buy()` in aggregator *and* auditor: the
baseline is captured **before** the purchase; the helper is actually invoked; the returned value is
what gets rendered; and after a `status == 1` receipt the output contains **neither** "purchase
failed" nor "transaction failed" — in all three outcomes. Specifically:

| Outcome | Required wording |
|---|---|
| settled | the new balance, plainly |
| not settled, `observed=True` | last observed balance + endpoint may be lagging |
| not settled, `observed=False` | **pre-write** balance, explicitly labelled as such — never "your balance is X" |

### 8.4 C, D, E

**C:** the save message is not green and warns about unencrypted storage; the publicly-known-key
line appears on the `--account` path and **not** for a pasted key; `configure-demo`'s default
resolves to `no`.

**D:** `requires-python` parses as `>=3.10`, and `version` is untouched.

**E:** with a `.env` present but lacking `DIN_WALLET_PASSWORD` (§7), neither `_get_password` nor
`_cache_password_if_needed` prints a red ❌, and the fallback chain still works.

**The non-duplication assertion must target the right workflow.** An earlier revision scoped it to
"a full connect-wallet run" — wrong: `connect_wallet` calls `_get_password(False)` and **never**
calls `_cache_password_if_needed`. The second call site lives in `load_account()`'s **encrypted**
branch (`utils.py:279`, and again at `:288` on the retry-after-failed-decryption path); the demo
branch returns early at `:271` and never reaches it.

So assert exactly-once across **a full encrypted `load_account()` flow**, or by calling
`_get_password()` then `_cache_password_if_needed()` explicitly in one test. Keep separate unit
assertions for each call site as well — the pair test proves they do not double up, the unit tests
prove each is individually silent.

Note the fix itself needs no per-call-site work here: `_cache_password_if_needed` makes its own
`get_env_key` call at `:333`, so changing that one line covers both `:279` and `:288`.

## 9. Verification — no chain writes, but not "no verification"

Rev 1 said "no live verification", which conflated two things. Correct framing: **no chain writes.**

**Excluded, with reasons:**

- **B cannot be safely exercised on-chain.** Staking is additive (`DinValidatorStake.sol:80`), so a
  real `stake` call on `0x5DD21F7A…5273` would permanently lock more DIN on the **registered GI 2
  aggregator**. Not worth it for a six-line fix with full mocked coverage.
- **A cannot be deterministically exercised on-chain.** It mitigates a race; a passing live run
  proves nothing, and the failure it guards is by definition intermittent.

**Included — local, free, and worth doing:**

- `configure-demo` through `CliRunner`, confirming the new default actually lands in `config.json`
- `connect-wallet` with a **generated disposable key**, confirming the reworded demo warning renders
  as intended on both the `--account` and pasted-key paths
- build the package (or read the built metadata) and confirm `Requires-Python: >=3.10`
- full test run plus an import/CLI smoke check, from a clean baseline

### 9.1 Isolation mechanics — the part rev 2 got wrong

**Setting `XDG_CONFIG_HOME` inside the test will not isolate anything.** The paths bind at import:

```
utils.py:23   CONFIG_DIR  = Path(user_config_dir("dincli"))
utils.py:27   WALLET_FILE = CONFIG_DIR / "wallet.json"
system.py:30  WALLET_FILE = CONFIG_DIR / "wallet.json"   # re-bound, second copy
```

By the time a test sets the variable, those are already resolved — the run would read and **write
the developer's real config and wallet**. Two workable options:

1. **Subprocess** with `XDG_CONFIG_HOME`/`XDG_CACHE_HOME` set in `env` *before* the interpreter
   starts. Closest to reality, and what the CLI checks should use.
2. **Monkeypatch the bound constants** — and note `WALLET_FILE` exists in **both** `utils` and
   `system`, so patching one leaves the other pointing at the real path.

**The `--account` path additionally needs a fixture.** `dincli/config/accounts.json` is gitignored
and absent from `main`, so `get_demo_private_key` raises `FileNotFoundError` before the message under
test is ever reached — the same wall hit while verifying #83. Patch `get_demo_private_key`, or write
a temporary accounts file.

Record the actual output. Frame it in the PR body as a deliberate boundary — the contrast with #85
is the point: that one moved funds and had to be proven live; this one does not and should not.

## 10. PR body outline

- Map each change to Umer's list item, and state the three places the brief needed correcting:
  `stake()`/`read-stake` do not share `buy()`'s shape and `read-stake` cannot use the helper at all
  (§3); the publicly-known-key warning is only true for the `--account` path (§5.1); and the
  password fix needs **two** call sites, not one (§7)
- **Reference #37 without a closing keyword**, and say why — it is a DevNet 2.0 staking epic, not
  this bug (§4.1)
- **Flag the one behaviour change** — the `configure-demo` default — up front
- **Flag E as beyond the list**, easy to drop
- Explain why `develop`'s `dintoken.py` refactor was not ported (§4)
- Explain the verification boundary: no chain writes, but local CLI/package checks were run (§9)
- Note conflict-freedom against all five open PRs, with the hunk table (§2)
- Note that `version` is untouched, for the 0.2.0 release

## 11. Follow-ups

- Reconciling `aggregator.py`/`auditor.py` duplication with `develop`'s `dintoken.py` — a real
  cleanup, but it belongs to the `main`/`develop` convergence question, not here
- `read-stake` staleness, if it ever proves to be a real problem — it needs transaction or block
  context, not the §3 helper (§3)
