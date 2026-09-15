# PR 1.5 — realign `SlashingInvariants.t.sol` with the burn/treasury split

**Base:** `develop` on `InfiniteZeroFoundation/DevNet` @ `3c1f100`
**Branch:** `fix/slashing-invariants-burn-treasury`, cut from `develop` — **local only, not pushed** (§10)
**Origin:** blocker found while preparing PR 2 of [discussion #74](https://github.com/InfiniteZeroFoundation/DevNet/discussions/74); see `Plans/archive/ci-cd-phase1-plan.md`
**Status:** rev 2 — every number below was measured against `develop` @ `3c1f100`. The fix was executed
and mutation-tested before this plan was written (§5). Nothing here is projected.

> **Rev 2 changelog.** A review of rev 1 found one substantive coverage overclaim and two rigor
> issues. All three were verified against the tree and **all three hold**:
>
> - **Rev 1 claimed the "staked supply never increases" invariant was already satisfied** (§2). It is
>   not: `invariant_noActorStakeExceedsWhatWasEverStaked` compares each actor's stake against the
>   *global cumulative* amount ever staked, so a slash that wrongly raised an actor from 100 to 200 DIN
>   still passes when 1 000 DIN has been staked overall. Rev 2 adds
>   `invariant_totalAccountedStakeMatchesLedger`, an exact equality, and a mutation test proving it is
>   the **only** invariant in the file that catches that bug class (§5.3).
> - **Rev 1 called the closure assertion load-bearing** (§3.3). It was not:
>   `ghost_totalBurned + ghost_totalToTreasury == ghost_totalSlashed` sums `actual / 2` and
>   `actual - actual / 2`, so it is true by construction regardless of what the contract does. Dropped,
>   along with the same tautology in the fuzz test. No-leak is now stated as what it really is — a
>   joint consequence of three *system-observable* deltas.
> - **Rev 1's supply identity silently assumed zero initial supply** (§3.5). True today
>   (`DinToken.initialize()` mints nothing) but brittle. Now anchored on a captured `initialSupply`.

> ### ⚠️ Implementation stops at a local commit
>
> This work is **not** to be pushed and **no PR is to be opened**. Implement, verify, commit to a local
> branch, and stop — the changes get reviewed first, and the PR is opened separately afterwards. Full
> handoff conditions in **§10**; §8's PR body outline is written for that later step, not this one.

---

## 1. The failure

`forge test` on `develop` @ `3c1f100`, clean tree, submodules present, `npm ci` run first:

```
Ran 20 test suites: 237 tests passed, 3 failed, 0 skipped (240 total tests)

Ran 12 tests for test/SlashingInvariants.t.sol:SlashingInvariantsTest
Suite result: FAILED. 9 passed; 3 failed; 0 skipped

[FAIL: assertion failed: 0 != 999990000000000000001930]  invariant_contractBalanceMatchesStakedMinusWithdrawn
[FAIL: assertion failed: 0 != 999990000000000000001930]  invariant_slashedAmountStrandsInContract
[FAIL: slash must not burn: total supply unchanged:
       5000000000000001000000 != 10000000000000001000000]  test_slash_doesNotTransferOrBurnTokens
```

All three are in one file. The rest of the suite is green.

> **Note on a false lead.** A first run in a dirty tree produced 15 failures, the extra 12 being
> `ValidateCommandError: Found multiple contracts with name …` out of `UpgradeValidation.t.sol` and
> `DeployPlatform.t.sol`. That is stale `foundry/out` build-info, not a code defect — `forge clean`
> clears it. Only the 3 above are real. Worth recording because CI (fresh checkout) will never see the
> other 12, and anyone reproducing this locally in a warm tree will.

### Root cause

`DinValidatorStake.slash()` (`foundry/src/DinValidatorStake.sol:235-242`):

```solidity
uint256 burnAmount = actualAmount / 2;
uint256 treasuryAmount = actualAmount - burnAmount;
IBurnableToken(address(DIN_TOKEN)).burn(burnAmount);
if (slashTreasury != address(0)) {
    DIN_TOKEN.safeTransfer(slashTreasury, treasuryAmount);
} else {
    IBurnableToken(address(DIN_TOKEN)).burn(treasuryAmount);
}
```

The three failing tests assert the opposite — that `slash()` moves no tokens at all and the slashed
amount strands in the stake contract's own balance. `SlashingInvariants.t.sol`'s `setUp()` never calls
`setSlashTreasury`, so on the current file both halves are burned; that is why
`test_slash_doesNotTransferOrBurnTokens` sees supply drop by the *full* slashed amount (10 000 → 5 000
ether on a 10 000-ether stake slashed by half) rather than by half of it.

---

## 2. Why the tests are wrong and the contract is right

This is not an open question, and PR 1.5 does not need to reopen it. The trail:

1. **`Developer/design/MECHANISM_DESIGN.md:93`** — *"✅ Resolved (Abraham, via Slack, 2026-07-21):
   split — 50% burn / 50% treasury."* Burning is a deflationary sink and avoids validators profiting
   from peers being slashed; the treasury half funds dispute adjudication. The same line calls the
   old stranding behaviour *"an accidental burn — make it explicit either way."*
2. **PR #60 / PR #65** implemented that decision in `slash()`. `DeployPlatform.s.sol:97` wires
   `setSlashTreasury(dinTreasuryProxy)`, so the treasury branch is the deployed path.
3. **`Developer/design/slashing-taxonomy.md:9-11`** (updated 2026-08-31) records the consequence
   explicitly: the test file *"was written to prove the pre-#65 'never moves tokens' behavior … it now
   fails 3 of its 12 tests against current `develop` for exactly that reason."*

So the tests encode a behaviour that was deliberately replaced. `SlashingInvariants.t.sol` landed via
PR #66 against an older merge-base and was never rebased onto the new semantics.

**The dangling tracker.** `slashing-taxonomy.md:11` ends *"Updating those 3 tests … is tracked
separately (see the backlog), not done as part of this doc fix."* There is no such backlog row —
`Developer/BACK_LOG.md` runs BL-1 through BL-22 and none of them is this. The pointer was written but
the row never was. PR 1.5 resolves that by doing the work and correcting the sentence; it deliberately
does **not** add a BL row for something it closes in the same commit.

### What the tests should have asserted

`MECHANISM_DESIGN.md:102-105` already specifies the invariants, under the heading
*"Invariants (feed P3-6.3b fuzz tests)"*. Measured status of each on `develop` today:

| Spec invariant | Status before this PR |
|---|---|
| Total staked supply never increases after a slash | ⚠️ **only loosely bounded.** `invariant_noActorStakeExceedsWhatWasEverStaked` checks each actor against the *global cumulative* stake, which a faulty slash can violate while still passing. §3.1 |
| Slashed amount always reaches its declared destination (burn / treasury), never a third party | ❌ asserted **inverted** by `invariant_slashedAmountStrandsInContract` |
| A slash can never make `activeStake + pendingWithdrawals` negative | ✅ `testFuzz_slash_neverLeavesNegativeAccounting` — passing, untouched |

Row 2 is the failure that makes `develop` red. Row 1 is a silent gap that nothing was failing over —
found in review of rev 1 of this plan, and closed here because it is the same concern in the same file
and would otherwise need its own PR against issue #38 to re-open the same code.

> The third spec invariant's second clause — *"or leave a validator Active below min stake"* — remains
> unasserted. That one **is** left to a follow-up (§7): it needs new fixtures around
> `_syncValidatorStatus`, not an assertion on the existing ledger.

---

## 3. Design decisions

### 3.1 Assert the ledger exactly; a loose upper bound is not the invariant

`invariant_noActorStakeExceedsWhatWasEverStaked` asserts, per actor:

```solidity
assertLe(activeStake + pendingWithdrawals, handler.ghost_totalStaked());
```

`ghost_totalStaked` is the cumulative total ever staked *by every actor*. With 1 000 DIN staked across
the pool, an actor whose stake a broken `slash()` raised from 100 to 200 DIN still satisfies
`200 <= 1000`. The assertion is true but nearly free — it constrains almost nothing.

Add the exact form, summing the contract's own accounting across the actor pool:

```solidity
sum(activeStake + pendingWithdrawals)
    == ghost_totalStaked - ghost_totalWithdrawn - ghost_totalSlashed
```

Paired with `invariant_contractBalanceMatchesStakedMinusWithdrawn` — which asserts the same
right-hand side against `token.balanceOf(address(stake))` — this yields **solvency**: every unit of
stake the contract believes it owes is a unit it actually holds. Neither invariant alone gives that;
the two sharing a right-hand side is the point, not redundancy.

The loose bound is **kept**, not deleted. It is passing, it is cheap, and removing a green assertion is
not this PR's business. Its docstring gains a line pointing at the exact one.

Verified in §5.3: this is the only invariant in the file that catches a `slash()` which under-deducts
accounting while moving tokens correctly.

### 3.2 Wire a `slashTreasury` in `setUp()` — test the production path, not the fallback

The file currently leaves `slashTreasury` unset, which exercises the `else` branch (burn both halves).
`DeployPlatform.s.sol:97` sets a treasury, so leaving it unset would mean the only invariant coverage
of slashing never touches the branch that actually runs in production, and the 50/50 split — the part
that was actually *decided* — would go unasserted at the invariant level.

So `setUp()` gains:

```solidity
vm.prank(admin);
stake.setSlashTreasury(slashTreasury);
```

with `address slashTreasury = makeAddr("slashTreasury")` alongside the other test addresses.
`makeAddr` guarantees no collision with the handler's `slashActor0..4`, so treasury receipts can never
be mistaken for actor balances.

The unset-treasury fallback stays covered by `test_slash_burns100PercentWhenNoTreasurySet` in
`DinValidatorStake.t.sol:220`. Cross-reference it in a comment rather than duplicating it here.

**Blast radius:** setting a treasury changes token *destinations*, never stake *accounting*. Of the 9
currently-passing tests in the file, none asserts on supply, contract balance, or treasury balance —
they assert on `getStake()`, `validators()` and revert behaviour. Verified: all 9 still pass (§5.1).

### 3.3 Recompute the split in the ghosts — but do not mistake ghost arithmetic for a check

The handler computes `actual / 2` and `actual - actual / 2` itself from `slash()`'s return value rather
than querying the contract for what it burned. An invariant that reads its expectation out of the
system under test restates the implementation instead of checking it, and would keep passing through
any change to the split. This is the same failure mode PR #103's review checked for on the pytest
marker hook, and it is worth the same care here.

**But the converse trap is just as real.** Rev 1 of this plan asserted:

```solidity
assertEq(ghost_totalBurned + ghost_totalToTreasury, ghost_totalSlashed);  // dropped
```

Both operands are derived from the same `actual`, so this reduces to
`actual / 2 + (actual - actual / 2) == actual` — arithmetic that holds for every `uint256` no matter
what the contract did. It tests Solidity's integer division, not `DinValidatorStake`. Dropped. The same
tautology appeared in rev 1's fuzz test (`assertEq((actual / 2) + (actual - actual / 2), actual)`) and
is dropped there too.

The no-leak property is real, but it is established **jointly by three system-observable deltas**, not
by any single assertion:

- the stake contract's balance falls by exactly `actual` (invariant 1 / fuzz test);
- the treasury balance rises by exactly `actual - actual / 2`;
- total supply falls by exactly `actual / 2`.

Together those account for every unit that left, leaving no room for a third-party transfer. The plan
says it that way now.

### 3.4 Track minted supply, or the burn assertion is not real

`token.totalSupply()` moves for two reasons in this harness: the handler mints via
`coordinator.depositAndMint()` inside `_fund`, and `slash()` burns. Asserting
`initialSupply - totalSupply == ghost_totalBurned` would therefore be wrong, not merely weak.

`_fund` must measure the real delta rather than assume it equals the requested amount — it sends
`ethNeeded = dinAmount * 1e18 / (1e6 * 1e18) + 1`, and that `+ 1` wei of ETH mints slightly more DIN
than `dinAmount`. So:

```solidity
uint256 supplyBefore = token.totalSupply();
vm.prank(who);
coordinator.depositAndMint{value: ethNeeded}();
ghost_totalMinted += token.totalSupply() - supplyBefore;
```

### 3.5 Anchor the supply identity on a captured `initialSupply`

`totalSupply() == ghost_totalMinted - ghost_totalBurned` is exact only because `DinToken.initialize()`
mints nothing, so the fixture starts at zero. That is true today and invisible in the assertion — if
`setUp()` ever prefunds an account, the invariant breaks for a reason unrelated to slashing.

Capture it instead, right after the treasury is wired and before `targetContract`:

```solidity
initialSupply = token.totalSupply();
```

and assert `totalSupply() == initialSupply + ghost_totalMinted - ghost_totalBurned`. One extra term,
and the invariant stops depending on a fact nobody wrote down.

### 3.6 Rename `invariant_slashedAmountStrandsInContract`, do not flip it

Its name states the old model. Flipping the assertion under the old name leaves a test whose name says
the opposite of what it checks — worse than the current failure, which is at least honest. It becomes
`invariant_slashedAmountSplitsBetweenBurnAndTreasury`.

`invariant_contractBalanceMatchesStakedMinusWithdrawn` keeps its name: still accurate, just incomplete,
and the docstring carries the correction.

### 3.7 Do not restate `DinValidatorStake.t.sol`'s coverage

`DinValidatorStake.t.sol` already covers the single-call split three ways —
`test_slash_burns50Percent` (:198), `test_slash_sends50PercentToTreasury` (:208),
`test_slash_burns100PercentWhenNoTreasurySet` (:220). Rewriting
`test_slash_doesNotTransferOrBurnTokens` into a fourth "does it burn half" unit test would add
maintenance burden and no information.

What this file uniquely offers is the *conservation* framing across a random walk, plus the odd-wei
rounding edge (`treasuryAmount = actual - actual / 2`, so an odd `actual` sends the extra wei to the
treasury). The three existing unit tests use `MIN` — an even number — so that edge is exercised nowhere
in the repo today. Hence the replacement is a **fuzz** test, not a unit test.

### 3.8 Out of scope, deliberately

- **The `block-timestamp` lint finding** at the `claimAction` line. Pre-existing, advisory, and part of
  the open security question in `Plans/archive/ci-cd-phase1-plan.md` §8 item 2. Untouched; repo-wide `forge
  lint` count stays 37 (verified §5.4).
- **`MECHANISM_DESIGN.md:104`'s "or leave a validator Active below min stake"** — see §7.
- **`MECHANISM_DESIGN.md`'s own stale "today" columns** (lines 34 and 184) — see §7.

---

## 4. Changes

One commit. `foundry/test/SlashingInvariants.t.sol` plus two doc corrections that directly describe it.

### 4.1 `foundry/test/SlashingInvariants.t.sol`

**a. File header (lines 5-11)** — the third claim is now inverted. Replace:

```
// slashed tokens strand in the contract's own balance rather than being
// burned or transferred anywhere, and no validator can be pushed into a
// negative-stake state.
```

with wording stating the burn/treasury split, and cite `MECHANISM_DESIGN.md` §4 as the source of the
invariant list rather than only the taxonomy doc.

**b. Handler ghosts (after line 36)** — add three:

```solidity
uint256 public ghost_totalMinted;
uint256 public ghost_totalBurned;
uint256 public ghost_totalToTreasury;
```

**c. `SlashingHandler._fund` (line 52)** — bracket the mint with a supply measurement, per §3.4.

**d. `SlashingHandler.slashAction` (line 75)** — after `ghost_totalSlashed += actual;`:

```solidity
// Recomputed here rather than read back from the contract, so the
// invariants check the split instead of restating it.
ghost_totalBurned += actual / 2;
ghost_totalToTreasury += actual - actual / 2;
```

**e. Test state (line 132)** — add:

```solidity
address slashTreasury = makeAddr("slashTreasury");
uint256 initialSupply;
```

**f. `setUp()` (before `targetContract`, line 192)** — wire the treasury and capture the supply:

```solidity
vm.prank(admin);
stake.setSlashTreasury(slashTreasury);

// Captured rather than assumed zero: DinToken.initialize() mints nothing
// today, but the supply identity below should not silently depend on that
// staying true.
initialSupply = token.totalSupply();
```

**g. `invariant_contractBalanceMatchesStakedMinusWithdrawn` (line 199)** — subtract the slashed total,
and rewrite the docstring, which currently reads *"slash() never moves tokens"*:

```solidity
uint256 expected = handler.ghost_totalStaked()
    - handler.ghost_totalWithdrawn()
    - handler.ghost_totalSlashed();
assertEq(token.balanceOf(address(stake)), expected);
```

**h. NEW `invariant_totalAccountedStakeMatchesLedger`** (immediately after (g), per §3.1):

```solidity
/// @dev The contract's internal accounting must equal the same ledger its
///      token balance does. Paired with the balance invariant above this is
///      solvency: every unit of stake the contract believes it owes is a
///      unit it actually holds. This is what carries MECHANISM_DESIGN.md
///      §4's "total staked supply never increases after a slash" -- an
///      exact equality, not the loose per-actor bound below, which a slash
///      that wrongly *raised* an actor's stake could still satisfy.
function invariant_totalAccountedStakeMatchesLedger() public view {
    uint256 total;
    for (uint256 i = 0; i < handler.actorsLength(); i++) {
        (uint256 activeStake, uint256 pendingWithdrawals, , , ) = stake.validators(handler.actors(i));
        total += activeStake + pendingWithdrawals;
    }
    assertEq(
        total,
        handler.ghost_totalStaked() - handler.ghost_totalWithdrawn() - handler.ghost_totalSlashed()
    );
}
```

**i. `invariant_slashedAmountStrandsInContract` (line 207)** — replaced wholesale. Two assertions, both
on system-observable state; the ghost-closure assertion from rev 1 is deliberately absent (§3.3):

```solidity
/// @dev Slashed tokens leave the stake contract in the 50/50 split resolved
///      in MECHANISM_DESIGN.md §4: half burned, half to slashTreasury (an
///      odd wei goes to the treasury). Nothing reaches a third party -- that
///      follows jointly from these two assertions and the balance invariant
///      above, which together account for every unit that left.
///      The unset-treasury fallback (both halves burned) is covered by
///      DinValidatorStake.t.sol:test_slash_burns100PercentWhenNoTreasurySet.
function invariant_slashedAmountSplitsBetweenBurnAndTreasury() public view {
    if (handler.ghost_slashCallCount() == 0) return;
    assertEq(token.balanceOf(slashTreasury), handler.ghost_totalToTreasury());
    assertEq(
        token.totalSupply(),
        initialSupply + handler.ghost_totalMinted() - handler.ghost_totalBurned()
    );
}
```

**j. `invariant_noActorStakeExceedsWhatWasEverStaked`** — body unchanged; docstring gains one line
noting it is a loose bound and that `invariant_totalAccountedStakeMatchesLedger` carries the exact
property.

**k. `test_slash_doesNotTransferOrBurnTokens` (line 295)** — replaced by
`testFuzz_slash_splitsBetweenBurnAndTreasury(uint256 stakeAmount, uint256 slashAmount)`:

```solidity
stakeAmount = _setUpSingleValidator(stakeAmount);
vm.prank(admin);
stake.setSlashTreasury(slashTreasury);
slashAmount = bound(slashAmount, 1, stakeAmount);

uint256 supplyBefore = token.totalSupply();
uint256 contractBalanceBefore = token.balanceOf(address(stake));
uint256 treasuryBefore = token.balanceOf(slashTreasury);

vm.prank(slasher);
uint256 actual = stake.slash(validator1, slashAmount, "TEST");

assertGt(actual, 0);
// These three together are the no-leak property: exactly `actual` left the
// contract, and burn + treasury account for all of it.
assertEq(contractBalanceBefore - token.balanceOf(address(stake)), actual);
assertEq(supplyBefore - token.totalSupply(), actual / 2);
assertEq(token.balanceOf(slashTreasury) - treasuryBefore, actual - actual / 2);
```

**Counts:** the file goes from 12 tests to **13** (4 invariants + 9 fuzz/unit), so `forge test` goes
from 240 to **241** total — and green.

### 4.2 `Developer/design/slashing-taxonomy.md:11`

Rewrite the closing sentence. It currently says the 3 tests fail on `develop` and that fixing them is
"tracked separately (see the backlog)". After this PR both halves are false. Replace with a statement
that they were realigned to assert the #60/#65 split, naming this PR.

### 4.3 `Developer/ROADMAP.md:124` (P3-6.3b)

Two errors in one sentence:

> `SlashingInvariants.t.sol` (StdInvariant handler + 9 fuzz/unit tests confirming slashed stake **never
> moves** and always reaches its target) landed in PR #66, reviewed/approved, **unmerged**.

- *"never moves"* is the stale model, and self-contradictory with *"always reaches its target"* in the
  same parenthesis.
- *"unmerged"* is out of date — PR #66 merged as `044f67c`.

Also update the count if kept: the file now carries 4 invariants + 9 fuzz/unit tests.

---

## 5. Verification — already performed

Everything below was run against `develop` @ `3c1f100` before this plan was written.

**Method, stated plainly:** the changes in §4.1 were applied to a *renamed copy* of the file
(`foundry/test/ZZProposed.t.sol`, contracts `ProposedSlashingHandler` / `ProposedSlashingInvariantsTest`)
and run alongside the untouched original, then deleted. The real PR edits the original in place. The
only difference between what was executed and what will be committed is the two contract names. The
verified copy is kept at `<scratchpad>/verified-final.t.sol` for reference during implementation.

### 5.1 The fix works

```
forge test --match-contract ProposedSlashingInvariantsTest
Suite result: ok. 13 passed; 0 failed; 0 skipped; finished in 27.06s
```

All four invariants ran `256 runs, 128000 calls, 0 reverts`. Zero reverts matters: it means the
handler's 128 000 calls were real state transitions, not a random walk bouncing off `require`s and
asserting against an empty system.

All 9 previously-passing tests still pass, confirming §3.2's blast-radius claim.

### 5.2 The split invariant is not a tautology

Mutate the handler's expected burn share from `actual / 2` to `actual / 3`:

```
[FAIL: assertion failed: 768886939024133599772669 != 849102567864501028515113]
       invariant_slashedAmountSplitsBetweenBurnAndTreasury
[PASS] invariant_contractBalanceMatchesStakedMinusWithdrawn
[PASS] invariant_noActorStakeExceedsWhatWasEverStaked
```

Caught, and caught by exactly one invariant. The others correctly ignore it — they constrain *how much*
leaves the contract, not *where it goes*.

### 5.3 The ledger invariant closes a hole nothing else covers

The decisive experiment for §3.1. Mutate `slash()` itself to under-deduct accounting while still moving
tokens correctly — `v.activeStake = activeStake - actualAmount / 2` — i.e. exactly the "a faulty slash
leaves too much stake" bug class:

| Invariant | Result under the mutant |
|---|---|
| `invariant_noActorStakeExceedsWhatWasEverStaked` | **PASS** — the loose bound misses it |
| `invariant_contractBalanceMatchesStakedMinusWithdrawn` | **PASS** — tokens moved correctly |
| `invariant_slashedAmountSplitsBetweenBurnAndTreasury` | **PASS** — destinations correct |
| **`invariant_totalAccountedStakeMatchesLedger`** | **FAIL** — `…922730 != …921078` |

```
Suite result: FAILED. 3 passed; 1 failed
```

The new invariant is the only thing in the file that detects a broken `slash()` of this shape. That is
the answer to rev 1's overclaim: before this PR, the property was not covered by anything.

`foundry/src/DinValidatorStake.sol` was restored from backup immediately afterwards and confirmed
byte-identical to `HEAD` (`git diff HEAD -- foundry/src/` empty).

The converse direction needs no experiment: dropping `- ghost_totalSlashed` from
`invariant_contractBalanceMatchesStakedMinusWithdrawn` reproduces the current `develop` failure, which
§1 already records.

### 5.4 No new lint findings

`forge lint --json` over the proposed file reports exactly one finding — `block-timestamp` at the
`claimAction` line, pre-existing and merely shifted down by the added ghost tracking. Repo-wide count
stays **37** (31 `unsafe-typecast` + 6 `block-timestamp`), unchanged from `develop`.

### 5.5 To reproduce after implementing

```bash
cd foundry && npm ci && forge clean && forge build
forge test --match-contract SlashingInvariantsTest    # expect: 13 passed
forge test                                            # expect: 241 passed, 0 failed
```

`forge clean` is not optional on a warm tree — see §1's note on stale build-info.

---

## 6. What this unblocks

With `forge test` green on `develop`, PR 2 (`ci/phase1-workflow`) can be pushed and opened, and its
`CI OK` check can go green on its own first run. That matters beyond tidiness: PR 2's whole argument
(discussion #74) is that *"a gate is only worth having if passing it means something"*. Opening it
against a red `develop` would make the project's first-ever CI run red for reasons unrelated to the PR,
and would make branch protection unaskable — nobody grants a required status check that has never
passed.

PR 2's body also needs three stats refreshed once this lands, since `develop` has moved past what the
commit message recorded: `forge test` 162 → **241**, pytest 282 → 298, `forge lint` 21 → 37.

---

## 7. Follow-ups this PR deliberately does not take

- **`MECHANISM_DESIGN.md:104`'s "…or leave a validator Active below min stake"** has no assertion
  anywhere. Unlike §3.1's gap, this one needs new fixtures around `_syncValidatorStatus` rather than an
  assertion over the existing ledger, so it belongs in its own PR against issue #38.
- **`MECHANISM_DESIGN.md:34` and `:184`** still describe slashed stake as *"stranded in stake
  contract"* / *"Accidental (stranded in stake contract)"* in their "today" columns. Stale since
  #60/#65. A mechanism-doc accuracy pass, not a test fix.
- **`Developer/BACK_LOG.md`** gains no row here (§2). If the two follow-ups above are not taken
  promptly, they should each get one.

---

## 8. PR body outline — drafted now, used later

Not for this step (§10). Written down here so the reasoning is captured while it is fresh, and so
whoever opens the PR after review does not have to reconstruct it.

**Title:** `fix(foundry): realign SlashingInvariants.t.sol with the resolved burn/treasury split`

Lead with the fact that `develop` is red today — 3 of 240 — and that it is a stale-test problem, not a
contract bug. Then the decision trail in §2, in three lines: the split was resolved 2026-07-21,
implemented by #60/#65, and the test file predates it. Say explicitly that the taxonomy doc already
diagnosed this and that the backlog row it pointed at was never written.

Then the substance, in this order:

1. The three stale assertions, realigned.
2. **The gap found while reviewing the fix** — the "staked supply never increases" invariant was only
   loosely bounded, and the new `invariant_totalAccountedStakeMatchesLedger` is the only thing in the
   file that catches a `slash()` which under-deducts accounting. Lead the evidence with §5.3's table;
   it is the most interesting result in the PR.
3. The harness now wires a treasury so the invariant covers the deployed path.
4. The ghosts recompute the split rather than reading it back — with the §3.3 note that a ghost-to-ghost
   closure assertion was written and then dropped for being true by construction.

Close with the numbers: 13 passed in the suite, 241 total green, lint count unchanged at 37, and one
line on what it unblocks (§6).

---

## 9. Decisions needed

None. The slashed-stake destination was resolved on 2026-07-21 and implemented; this PR only makes the
tests agree with a decision already taken. Two judgement calls are reviewer preferences, and either
choice leaves the suite green:

1. Wiring a treasury into `setUp()` rather than leaving the fallback path under test (§3.2).
2. Keeping the loose `invariant_noActorStakeExceedsWhatWasEverStaked` alongside the exact ledger
   invariant rather than deleting it as subsumed (§3.1). Recommend keeping — it is green, cheap, and
   deleting passing assertions is not this PR's job.

---

## 10. Delivery — local only

**The implementation stops at a local commit.** The changes are reviewed before anything leaves this
machine.

### Do

```bash
git checkout develop && git checkout -b fix/slashing-invariants-burn-treasury
# ... apply §4, verify per §5.5 ...
git add foundry/test/SlashingInvariants.t.sol \
        Developer/design/slashing-taxonomy.md \
        Developer/ROADMAP.md
git commit    # message per §10.1
```

Then **stop** and report: the branch name, the commit SHA, `git diff --stat develop..HEAD`, and the two
test counts from §5.5.

### Do not

- `git push` anywhere — not to `origin` (the fork), not to `upstream`.
- `gh pr create`, or any other `gh` write operation.
- Switch `gh` accounts. Nothing in this step touches GitHub at all.
- Commit anything under `Plans/` — it is excluded via `.git/info/exclude` and must stay local.

### Leave the tree in a reviewable state

- Exactly one commit on the branch, three files, nothing staged and nothing dirty afterwards.
- `develop` itself untouched — verify `git diff develop origin/develop` is empty.
- `foundry/src/` byte-identical to `HEAD` after the §5.3 mutation experiment. `forge clean`'s output
  (`foundry/out/`, `foundry/cache/`) is already gitignored, but confirm `git status --porcelain` is
  clean before reporting.

Reviewing is then `git diff develop..fix/slashing-invariants-burn-treasury`, and unwinding is
`git branch -D` — no remote state to undo, which is the point of stopping here.

### 10.1 Commit message

```
fix(foundry): realign SlashingInvariants.t.sol with the resolved burn/treasury split
```

Body: the three stale assertions and why they were stale (§2); the coverage gap found in review and
that `invariant_totalAccountedStakeMatchesLedger` is the only invariant catching an under-deducting
`slash()` (§5.3); the treasury wired into the fixture (§3.2); the ghost-closure assertion written and
dropped as true-by-construction (§3.3). Close with `13 passed` / `241 total` / lint unchanged at 37.

Trailers:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Wu3sbCps6PEhyvsQNGK3pr
```

### 10.2 After review

Once the diff is approved, the push-and-open step is: push the branch to `origin`
(`Santiagocetran/DevNet` — never upstream), then open a PR to upstream `develop` with the
`Santiagocetran` gh account, using §8's outline. That is a separate instruction, not part of this one.
