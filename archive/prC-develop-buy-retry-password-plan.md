# PR C — `buy()` read-after-write retry and quiet password lookups

**Branch:** `fix/develop-buy-retry-password` (off `develop` @ `bf162c0`) — not yet created
**Base:** `develop` on `InfiniteZeroFoundation/DevNet`
**Origin:** [discussion #79](https://github.com/InfiniteZeroFoundation/DevNet/discussions/79#discussioncomment-18082657) row C, greenlit by @umeradl ("do PR A and onwards too")
**Ports:** the applicable parts of `0bcf945` (#86)
**Status:** rev 4 — implemented and rebased onto `develop` @ `b2c2e43` (post-#96). Two
post-implementation findings fixed; one collision claim in this plan corrected.

> **Rev 4 changelog.** Implemented as `466c770`, reviewed, then two issues found and fixed in
> `f8688a9`:
>
> - **`read_after_write` violated its own `observed` contract.** The implementation early-returned
>   `observed=False` whenever the *final* attempt raised, discarding values earlier attempts had read.
>   `[100, 100, raise]` with baseline 100 returned `observed=False`; §2.1 specifies "False iff every
>   read raised". User-visible effect: a lagging endpoint that answers twice then hiccups reports
>   "could not read post-purchase balance" and shows the stale figure. The existing "mixed" test only
>   covered raise-then-success, so the opposite ordering was untested. Fixed and pinned.
> - **A parametrized test was deleted.** `test_legacy_role_dintoken_help_exposes_commands` (covering
>   `aggregator dintoken --help` and `auditor dintoken --help`) was dropped while the retry tests were
>   added, removing the only guard that the role sub-apps still expose buy/stake/read-stake. It passes
>   unchanged, so the deletion was unforced. Restored — and it explains why the reported "+15 tests"
>   measured as +13.
> - **§2.6's `utils.py` collision claim was wrong.** Corrected below.
>
> Rebased onto post-#96 `develop`, so the delta is now **161 → 177**, not the stale-base 114 → 130.
> #96 merged as `b2c2e43` on 2026-08-20.

> **Rev 3 changelog.** A second audit found one blocker and one important gap. Both verified; both
> applied.
>
> - **Blocker — §2.3 contradicted §3.2 on ordering.** Rev 2 said the `None` check must precede "any
>   baseline capture", which is impossible: the baseline is the *pre-purchase* balance and must be read
>   before the transaction is submitted. §3.2 already had the right order. Corrected to "before any
>   post-write balance read or retry". Two test rows followed from the same error: the `None` case
>   cannot assert "no balance output" (the pre-purchase balance is legitimately printed at
>   `dintoken.py:25-28`), and "`balanceOf` called exactly once" has to mean *once before submission*,
>   since retry reads necessarily call it again.
> - **Gap — password mutation coverage missed a call site.** The three lookups have three *different*
>   owners, confirmed by AST: `:415` in `load_account`, `:455` in `_get_password` self-fetch, `:478` in
>   `_cache_password_in_memory` self-fetch. Rev 2 covered two, so reverting `verbose=False` on `:478`
>   alone would have survived the suite. §5 now requires three independent tests, each
>   mutation-checked separately.
> - Editorial: test files allocated explicitly (§3.3), and the `read_after_write` import into
>   `dintoken.py` spelled out (§3.2).

> **Rev 2 changelog.** An audit found three blockers and six corrections. All verified against the
> tree; all stand.
>
> - **B1 — demo-mode hardening is removed from this PR entirely (§2.7).** Rev 1 called it "two tiny
>   lines". It is not: flipping `configure-demo`'s default breaks the integration bootstrap
>   (`tests/dincli/conftest.py:490` runs it bare and then registers Hardhat accounts) and inverts the
>   CLI's own guidance (`context.py:164` tells users to enable demo mode with the bare command). It is
>   a command-semantics change with two dependent callers and its own UX decision, so it becomes its
>   own PR.
> - **B2 — a live bug rev 1 got backwards (§1.3, new).** `build_and_send_tx(..., exit_on_failure=False)`
>   returns `None` on failure (`utils.py:858`), and `buy_dintokens` immediately dereferences
>   `tx_receipt.transactionHash`. Rev 1 claimed purchase failure was "unaffected" — in fact a failed
>   purchase prints the real error *and then* `✗ Error buying DINTokens: 'NoneType' object has no
>   attribute 'transactionHash'`. Reproduced. Fixed here, since this PR rewrites that exact block.
> - **B3 — the `>` mutation check could not fail (§5).** Rev 1's lagging test only returned values
>   *equal* to the baseline, where `>` and `!=` behave identically. A **below-baseline** case is
>   required to kill it.
> - **C1 (§2.4).** The yellow fallback line belongs inside `_get_password`, not at the `get_env_key`
>   call site: `system.py:598` calls `_get_password` directly for wallet creation and would otherwise
>   miss it.
> - **C2 (§1.2).** The red ❌ only fires when a `.env` file exists and lacks the key
>   (`utils.py:249-254`). Tests must create such a file or they pass without the fix.
> - **C3 (§2.2).** `ReadResult.value` is the *last successfully observed* value, not the "best"
>   available. Comment corrected to match the implementation.
> - **C4 (§3.2).** Reuse the already-displayed balance as the baseline instead of issuing a second
>   RPC call, so the displayed and compared baselines cannot diverge.
> - **C5 (§2.2).** Retry latency documented: 5 attempts × 2s is up to **8 seconds** added after the
>   receipt.
> - **C6 (§2.6, §4.2).** The merge claim now carries the exact command and heads — the repo collects
>   **247** tests in total and **114** with `--ignore=tests/dincli`, so a bare "197 passing" was not
>   interpretable. §4.2 is labelled a controlled smoke test, not a live reproduction.

---

## 1. The defects

### 1.1 `buy()` reports a stale balance — B10

`buy_dintokens` (`dincli/cli/dintoken.py:11`) confirms the transaction, then immediately reads the new
balance with no retry and no delay (`:44`). Public RPC endpoints are load-balanced and eventually
consistent: the receipt comes from the node that mined it, and the very next read can land on a
backend that has not caught up.

Observed live during onboarding — `balance: 0` printed straight after a successful 100 DIN purchase.
The operator's reasonable conclusion is that it failed, and buying twice is a real outcome.

Not a units bug; `Web3.from_wei` is correct on both lines.

**Cheaper here than on `main`:** `develop` refactored buy/stake into shared helpers in `dintoken.py`
with `aggregator.py`/`auditor.py` delegating, so there is one fix site instead of `main`'s two.

### 1.2 A missing `DIN_WALLET_PASSWORD` prints a fatal-looking error — B12

`get_env_key` prints a red ❌ on a miss (`utils.py:254`), and the password lookup calls it as step one
of a three-step fallback (env → session cache → interactive prompt):

```
❌ DIN_WALLET_PASSWORD not found in /home/agent/din-aggregator/.env file
Password:
```

The code recovers on its own immediately.

Two precisions rev 1 got loose:

- **Three call sites**, not one: `utils.py:415`, `:455`, `:478`. `main` fixed two.
- **The ❌ only fires when a `.env` file exists and lacks the key** (`utils.py:249-254`). With no
  `.env` at all, nothing is printed — so a test run in a bare directory passes even without the fix.

### 1.3 A failed purchase prints a second, misleading error — new in rev 2

`build_and_send_tx` with `exit_on_failure=False` **returns `None`** for estimation failure, a reverted
receipt, or a caught submission exception (`utils.py:858`). It does not raise. `buy_dintokens` then
does:

```python
console.print(f"... {tx_receipt.transactionHash.hex()}")   # dintoken.py:41
```

Reproduced — the user sees the genuine transaction error followed by:

```
✗ Error buying DINTokens: 'NoneType' object has no attribute 'transactionHash'
```

Squarely in scope: this PR rewrites the block immediately below that line, and leaving it would mean
the retry work sits on top of a known crash path.

---

## 2. Design decisions

### 2.1 Port `read_after_write` as a shared helper in `utils.py`

`main`'s shape holds up and is worth keeping identical for cross-branch familiarity:

```python
class ReadResult(NamedTuple):
    value: int       # last successfully observed value; the baseline if every read raised
    settled: bool    # True iff a read showed value > baseline
    observed: bool   # False iff every read raised

def read_after_write(read_fn, *, baseline, attempts=5, delay=2.0) -> ReadResult
```

`utils.py` already imports `time` (`:1`); `NamedTuple` must be added to the `typing` import (`:10`).

### 2.2 Three outcomes, because "retry until it changes" is not enough

| Outcome | Meaning | What `buy` prints |
|---|---|---|
| `settled` | a read showed a value above the baseline | the new balance, plainly |
| `observed`, not `settled` | reads succeeded, value never rose | the balance **plus** a yellow "may not reflect the purchase yet — the RPC may be lagging" |
| not `observed` | every attempt raised | a yellow line naming the **pre-purchase** balance, explicitly labelled as such |

The third case is why `baseline` is a parameter rather than an internal detail: without it there is no
honest value to report when every read fails.

**`> baseline`, not `!= baseline`.** A balance after a purchase can only rise; `!=` would treat a
stale backend reporting a *lower* balance as settlement. §5 has the test that proves this, which rev 1
lacked.

**Does not propagate `read_fn` exceptions.** The purchase already succeeded; a failed *display* read
must not turn a successful command into a traceback.

**Latency, stated:** 5 attempts × 2s means up to **8 additional seconds** after the receipt on the
lagging path. Acceptable for a purchase confirmation, and only paid when the read has not settled.

### 2.3 `tx_receipt is None` returns early

```python
if tx_receipt is None:
    return
```

`build_and_send_tx` has already reported the failure with the caller-supplied message, so there is
nothing to add — and nothing to read a post-purchase balance for. This sits immediately after the
call and **before any post-write balance read or retry**, so a failed purchase does no extra RPC work.

Note it cannot precede the *baseline* read: the baseline is the pre-purchase balance, which is read
and displayed before the transaction is submitted. Order is: read and display the pre-purchase
balance → submit → return if the receipt is `None` → poll for the post-purchase balance.

### 2.4 Password verbosity: `verbose=False` at the call sites, message inside `_get_password`

`get_env_key` is shared by RPC URLs, private keys and more, where a missing value genuinely is a loud
red error. Blanket-demoting the helper would mute real failures elsewhere — Umer's original
correction, still valid.

- `verbose=False` at all three `get_env_key("DIN_WALLET_PASSWORD")` calls (`:415`, `:455`, `:478`).
- The yellow explanatory line goes **inside `_get_password`**, after the resolved/injected `env_pass`
  proves empty. Not at the `load_account` call site: `system.py:598` calls `_get_password` directly
  for new-wallet creation and would otherwise print nothing.
- **Not** emitted from the session-cache helper, or it fires twice.

```
DIN_WALLET_PASSWORD not found in environment; checking session cache or prompting...
```

### 2.5 What is already on `develop` — do not re-port

`0bcf945` bundled five changes:

| Piece | Status here |
|---|---|
| `stake()` honouring `amount` | **already done** — `stake_dintokens` (`dintoken.py:50`) computes `Web3.to_wei(amount, "ether")`; Umer's #37 refactor, which `main` was missing |
| Python floor bump | **PR A** (#97) |
| `buy()` retry | this PR, §1.1 |
| password verbosity | this PR, §1.2 |
| demo-mode default + message | **split out** — §2.7 |

### 2.6 Collision with the PRs in flight — verified, not assumed

Established by real committed merges (not chained `--no-commit`, which has misled this repo before):

```
git worktree add <wt> develop --detach
git merge --no-edit fix/ipfs-retrieval-develop        # #96, head 5e53270 — clean
git merge --no-edit fix/develop-small-backports       # #97, head 5e61c63 — clean
git merge --no-edit fix/develop-chain-id-validation   # #98, head 31af2ca — CONFLICT: pyproject.toml only
# resolved as the union of #97's four declarations plus #98's click
.venv/bin/python -m pytest tests/ -q --ignore=tests/dincli   # -> 197 passed
```

For reference, the repo collects **247** tests in total and **114** under
`--ignore=tests/dincli`; the integration suite under `tests/dincli/` needs a running Hardhat node, so
every count in this plan uses the `--ignore` form.

| File | Claimed by | Their hunks | This PR's targets | Overlap |
|---|---|---|---|---|
| `dincli/cli/dintoken.py` | #97 | 116+, 135+ | 32–45 | none |
| `dincli/cli/utils.py` | #98 | ~48, 328–378 | ~48 (new helper), ~254, 415/455/478 | **yes, at ~48** |

**Correction (rev 4).** Rev 2/3 claimed "none" for `utils.py`. That was wrong: this PR inserts
`ReadResult`/`read_after_write` immediately after `MIN_STAKE = 10*10**18`, and #98 inserts
`ChainIdMismatchError` at the same anchor. Verified against the post-#96 `develop`:

```
merge PR C onto develop     -> clean
merge #98  onto develop     -> clean
merge PR C then #98         -> CONFLICT in dincli/cli/utils.py
```

It is an adjacent-insertion conflict, so the resolution is to keep both blocks — but whichever of the
two merges second must expect it. Rev 2's hunk table omitted this PR's own new-helper insertion,
which is how the collision was missed.

This PR does not touch `pyproject.toml`, so it inherits none of the #97/#98 conflict there.

### 2.7 Demo-mode hardening is **not** in this PR — reversal from rev 1

Rev 1 proposed folding in `0bcf945`'s `system.py` hunks — flipping `configure-demo --mode` from `yes`
to `no`, and making the plaintext-save message loud. The audit showed this is not a two-line change,
and it is being split into its own PR.

**Why it cannot ride along:** flipping the default is a breaking change with two dependent callers.

- `tests/dincli/conftest.py:490` runs bare `system configure-demo` in the integration bootstrap and
  then registers Hardhat accounts by index. With the default flipped, `register-wallet --account N`
  would look for `ETH_PRIVATE_KEY_N` instead of the bundled keys, and the bootstrap breaks.
- `dincli/cli/context.py:164` tells the user *"Enable it with `dincli system configure-demo`"* when
  `--demokey` is used outside demo mode. After the flip, following that instruction disables it.

Any resolution must update both, and there is a real UX choice to make first — flip the default,
make `--mode` required, or make a bare invocation *report* the current state without mutating
anything (which matches `configure-ipfs`'s existing idiom on this branch). That decision deserves its
own PR and its own conversation, not a footnote in a retry fix.

Two further findings that belong with it rather than here:

- `demo_key_is_public` must be initialised to `False` **before** the authentication-method branching
  (`system.py:515-525` has keystore / pasted-key / key-file / demo-account paths), or the conditional
  warning hits an unbound local on the non-demo paths.
- Calling the slice "demo-mode hardening" overstates it. Demo mode still accepts arbitrary user keys
  and writes them in plaintext via a plain `open(...)` (`system.py:574`), without the atomic 0600
  writer the encrypted path uses. It is **warning and default hardening, not prevention**, and the
  residual has to be stated plainly.

---

## 3. Changes

### 3.1 `dincli/cli/utils.py`

- `NamedTuple` added to the `typing` import (`:10`).
- `ReadResult` and `read_after_write` (§2.1).
- `verbose=False` at `:415`, `:455`, `:478`; the yellow line inside `_get_password` (§2.4).

### 3.2 `dincli/cli/dintoken.py`

Import `read_after_write` from `dincli.cli.utils` alongside the existing `MIN_STAKE`/`build_and_send_tx`
import (`:6`).

In `buy_dintokens`:

1. Keep the existing pre-purchase balance read (`:27`) and **reuse its value** as the baseline. Do not
   issue a second `balanceOf` call — a separate read could return a different value from the one just
   displayed, so the number the user saw and the number being compared would disagree.
2. `if tx_receipt is None: return` immediately after the call (§2.3).
3. Replace the post-receipt read with `read_after_write(...)` and branch on the three outcomes (§2.2).

`stake_dintokens` is **not** touched — its amount handling is already correct (§2.5).

### 3.3 Tests

Extend the existing files rather than duplicating fixtures:

| Tests | File |
|---|---|
| `read_after_write` and `buy_dintokens` | `tests/test_dintoken.py` |
| the three password call sites | `tests/test_connect_wallet.py` |

Do **not** copy the aggregator/auditor mocks from `0bcf945`'s test file — they target `main`'s
pre-refactor structure, where buy/stake lived in the role modules.

---

## 4. Verification

**Be honest about what can and cannot be shown live.** The race in §1.1 is not reproducible on
demand — it depends which backend a load-balanced endpoint happens to serve. So the retry *logic* is
proven by mocked tests, and the live checks prove the command still behaves.

### 4.1 Live — `buy` still works end to end

`dincli aggregator dintoken buy 0.00001` against the devnet from a funded wallet. Costs real testnet
ETH, so run once and record the tx hash in the PR. Assert: purchase succeeds, a balance prints, no
yellow warning on a healthy endpoint.

### 4.2 Controlled smoke test — the lagging branch

Monkeypatch `balanceOf(...).call` in a REPL against a real `w3` so it returns the baseline, and
confirm the `observed`-but-not-`settled` branch renders its yellow line. This is a **controlled smoke
test, not a live reproduction** — it forces the branch rather than catching a real race.

### 4.3 Live — the `None` receipt path (§1.3)

Force a failure (e.g. buy an amount exceeding the wallet's ETH) and assert the genuine transaction
error appears **without** the `'NoneType' object has no attribute 'transactionHash'` line that
follows it today.

### 4.4 Live — the password prompt

Run a wallet command in a directory that **has** a `.env` lacking `DIN_WALLET_PASSWORD` (§1.2's
precision — a bare directory proves nothing). Assert: no red ❌, one yellow line, then the prompt.
Repeat with the variable set and assert neither line appears.

### 4.5 Regression — the red ❌ still fires where it should

`get_env_key` on a genuinely required value with `verbose=True` must still print red. This is the
regression §2.4 exists to avoid.

---

## 5. Tests (committed)

| Group | Asserts |
|---|---|
| `read_after_write` — settled | first read above baseline returns `settled=True, observed=True` and **stops early** (call count == 1) |
| — lagging at baseline | reads equal to the baseline exhaust `attempts`; `settled=False, observed=True`, value == baseline |
| — **below baseline** | `[baseline-10, baseline-20, baseline]` must stay `settled=False`. **This is the test that kills the `>` → `!=` mutation**; the equal-value case above cannot, since both operators are false there |
| — all raising | every attempt raising returns `observed=False`, `value == baseline`, and propagates nothing |
| — mixed | raise, then a value above baseline → `settled=True` |
| — guards | `attempts < 1` raises `ValueError`; no sleep after the final attempt |
| — no real sleeping | `time.sleep` patched; assert at most `attempts - 1` sleeps so the suite stays fast |
| `buy_dintokens` — settled | prints the new balance, no warning |
| — lagging | prints the balance **and** the lag warning |
| — read failed | names the pre-purchase balance, labelled as pre-purchase |
| — **`tx_receipt is None`** | returns early. The **pre-purchase** balance is still printed (it is read and displayed before submission), but: no purchase-success message, no post-purchase balance, no lag warning, `read_after_write` never called, and no `NoneType`/`transactionHash` text anywhere (§1.3) |
| — baseline reuse | `balanceOf` is called exactly **once before submission**, and the value passed as `baseline` is the one displayed. Not "once overall" — the retry reads call it again by design (§3.2 item 1) |
| Password — `load_account` (`:415`) | with a `.env` present that lacks the key: no red ❌; the yellow line appears exactly once |
| Password — `_get_password` self-fetch (`:455`) | called directly as `system.py:598` does (`env_pass` omitted, so `_UNSET`): no red ❌, yellow line emitted |
| Password — `_cache_password_in_memory` self-fetch (`:478`) | called directly with `env_pass` omitted: no red ❌, and **no second** yellow line (§2.4 — the message lives in `_get_password` only) |
| Password — shared helper intact | `get_env_key(..., verbose=True)` on a `.env` missing a key still prints red |

The three password rows are **three independent tests**, one per call site, because the sites live in
three different functions — `load_account`, `_get_password`, `_cache_password_in_memory`. A suite that
exercised only the first two would survive a revert of `verbose=False` on `:478`. Each must run in a
directory containing a real `.env` that lacks `DIN_WALLET_PASSWORD` (§1.2), and each reverted
`verbose=False` must be mutation-checked **separately**.

Mutation-check before claiming, one at a time: each of the three `verbose=False` reverts, and flipping
`>` to `!=`. Rev 1 asserted the operator check without a test capable of failing it, and rev 2 covered
only two of the three password sites — so run these individually rather than as a batch.

---

## 6. PR body outline

1. Row C of the #79 split; the applicable parts of `0bcf945`
2. What is already on `develop` (§2.5) — `stake()` needs nothing, and why
3. The three defects, including the `None`-receipt crash found while planning (§1.3)
4. `ReadResult`'s three outcomes, why `baseline` is a parameter, why `>` not `!=`, and the 8s worst case
5. Why `get_env_key` itself is untouched, and why the message lives in `_get_password`
6. Demo-mode hardening deliberately split out, with the two dependent callers named (§2.7)
7. One fix site here vs `main`'s two, thanks to the `dintoken.py` refactor
8. What the live checks do and do not prove (§4)
9. Collision status vs #96/#97/#98 — command, heads, and counts (§2.6)

## 7. Follow-ups not in this PR

- **Demo-mode defaults and warnings (§2.7).** Its own PR: needs the `configure-demo` UX decision, both
  dependent callers updated, `demo_key_is_public` initialised, and the residual plaintext risk stated.
- **Row E, the wallet-model split.** Still needs its shape agreed before any code.
- **`read_after_write` elsewhere.** `stake`/`read-stake` share the same shape, and `dintoken.py:97`
  has a bare `time.sleep(5)` this helper could replace properly. Worth doing once the helper has
  landed and been reviewed.
- **`main` parity.** `main` fixed two password call sites; check whether it has a third equivalent
  before claiming it needs the same one-liner.
