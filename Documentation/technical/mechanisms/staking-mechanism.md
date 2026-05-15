# DIN Protocol: Staking Mechanism

## Overview

The DIN staking mechanism is the protocol's validator collateral system. It provides:
- economic commitment from validators;
- validator eligibility checks for Aggregators and Auditors;
- slashing for faults and non-performance;
- delayed exits through unbonding;
- emergency isolation of dangerous validators through blacklisting.

This mechanism is centered on `DinValidatorStake.sol`, but it only works correctly when coordinated with:
- `DinCoordinator.sol`
- `DINTaskCoordinator.sol`
- `DINTaskAuditor.sol`
- governance or DAO-controlled admin processes

The key architectural principle is simple:

> validator participation should be controlled by lifecycle state, not only by token balance.

That matters especially for exits, slashing, blacklisting, and future unblacklisting.

---

## Core Contracts

### `DinValidatorStake.sol`

The core staking and validator-lifecycle contract. It:
- holds validator DIN stake;
- tracks `activeStake`, `pendingWithdrawals`, and validator status;
- enforces `MIN_STAKE`;
- enforces delayed withdrawals with an unbonding period;
- keeps pending withdrawals slashable;
- exposes `isValidatorActive()` for downstream eligibility checks;
- allows emergency blacklist enforcement through coordinator authority.

### `DINTaskCoordinator.sol`

Manages Aggregator participation and task-round execution. It should:
- use `isValidatorActive()` when checking whether a validator may register or keep participating;
- call `slash()` when Aggregators fail liveness or correctness requirements;
- refuse blacklisted, jailed, or exiting validators through the shared stake state.

### `DINTaskAuditor.sol`

Manages Auditor participation. It should:
- use `isValidatorActive()` as the role eligibility gate;
- call `slash()` for Auditor faults;
- refuse blacklisted, jailed, or exiting validators via stake state.

### `DinCoordinator.sol`

The coordinator is the admin-facing control point for staking-related policy wiring. In the current architecture it:
- mints DIN against ETH deposits;
- registers or removes authorized slasher contracts on `DinValidatorStake`.

For a complete blacklist lifecycle, it should also become the governance-controlled forwarding layer for:
- `blacklistValidator()`
- `unblacklistValidator()` in a future contract revision

### Governance / DAO Admin

Governance should not directly act as a slasher for routine faults. Routine faults belong in task contracts via `slash()`.

Governance is the likely authority for blacklist and unblacklist decisions because those are not normal scoring penalties. They are exceptional trust and safety interventions affecting protocol admission and exit rights.

In practice, this authority is likely implemented as:
- a DAO-owned multisig;
- a security council;
- a timelocked governance executor;
- or a staged model where emergency actors can blacklist immediately and governance later confirms or reverses.

---

## Staking Economics and Eligibility

### Staking Asset

- DIN token
- 18 decimals

### Minimum Stake

- `DinValidatorStake` is the intended source of truth for `MIN_STAKE`
- downstream contracts should consume `minStake()` or `isValidatorActive()`
- downstream contracts should not rely on independent local stake-threshold copies for access control

### Active Eligibility

Validators should be considered eligible for new work only when:
- `status == Active`

A validator is not eligible when it is:
- `Exiting`
- `Jailed`
- `Blacklisted`
- or otherwise below active threshold

This is critical because a validator with high raw balance may still be ineligible if it already requested exit.

---

## Operational Workflow

### 1. Stake Entry

1. Validator acquires DIN.
2. Validator approves `DinValidatorStake`.
3. Validator calls `stake(amount)`.
4. DIN is transferred into the stake contract.
5. `activeStake` increases.
6. `_syncValidatorStatus()` sets validator state.
7. If stake is sufficient and no exit is pending, validator becomes `Active`.

### 2. Role Registration

Once active, validators register for protocol roles:
- Aggregators through `DINTaskCoordinator`
- Auditors through `DINTaskAuditor`

Those role contracts should:
- check `isValidatorActive(msg.sender)`;
- reject validators that are exiting, jailed, or blacklisted;
- avoid relying only on raw `getStake()`.

### 3. Normal Slashing

1. Validator misses work, submits invalid work, or fails a consensus rule.
2. Authorized task contract determines slash amount and reason.
3. Task contract calls `DinValidatorStake.slash()`.
4. Slash is applied first against `activeStake`, then against `pendingWithdrawals` if needed.
5. Validator status is resynchronized.
6. Validator may lose `Active` status if stake falls too low or if exit is already in progress.

### 4. Exit / Unbonding

1. Validator calls `unstake(amount)`.
2. Funds move from `activeStake` to `pendingWithdrawals`.
3. `withdrawAvailableAt` is set.
4. Validator becomes `Exiting`.
5. Validator cannot be selected for new work.
6. Pending amount remains slashable until claimed.
7. After the unbonding period ends, validator calls `claimUnstaked()`.

### 5. Emergency Blacklisting

1. An exceptional risk is identified.
2. Governance-authorized actor initiates blacklist action.
3. Stake contract marks validator `Blacklisted`.
4. Validator becomes permanently ineligible unless governance later restores them through a dedicated unblacklist path.
5. Existing in-contract funds remain trapped and still slashable unless governance policy explicitly allows a later release path.

---

## Blacklisting vs Slashing

These two mechanisms should not be treated as the same thing.

### Slashing

Use slashing for normal protocol faults such as:
- non-submission;
- invalid aggregation;
- invalid audit behavior;
- measurable liveness failures;
- deterministic correctness failures.

Slashing is operational, expected, and usually triggered automatically by task logic.

### Blacklisting

Use blacklisting for exceptional cases such as:
- repeated malicious behavior across rounds;
- exploit attempts;
- sybil abuse that ordinary slashing does not contain;
- compromised validator keys still being used;
- governance-determined fraudulent operation;
- legal, sanctions, or emergency trust-and-safety requirements if the protocol adopts such policies.

Blacklisting is an emergency governance action, not a routine scoring penalty.

---

## Current Contract Reality

The current codebase partially supports blacklist behavior but does not yet implement a full blacklist lifecycle.

### What Exists Today

In `DinValidatorStake.sol`:
- `blacklistValidator(address)` exists;
- it is restricted by `onlyDinCoordinator`;
- blacklisted validators cannot `stake()`, `unstake()`, or `claimUnstaked()`;
- `_syncValidatorStatus()` preserves `Blacklisted` and never clears it;
- slashing can still reduce blacklisted funds.

### What Does Not Exist Today

- no `unblacklistValidator(address)` function;
- no governance review flow on-chain;
- no public jail-to-blacklist escalation path;
- no dedicated blacklisting interface in `DinCoordinator.sol`;
- no release policy for funds locked under blacklist status.

### Important Architecture Gap

`DinValidatorStake` expects the `DIN_COORDINATOR` address to be the caller of `blacklistValidator()`, but the current `DinCoordinator.sol` does not expose a forwarding method for blacklist management.

So today, blacklist logic exists in the stake contract, but the currently documented coordinator path is incomplete.

That should be treated as a design gap, not hand-waved away in the docs.

---

## Recommended Blacklisting Mechanism

This section describes the recommended production-grade blacklist and unblacklist design.

### Governance Roles

The most likely operational split is:

- `Task contracts`
  - handle routine slashing and validator-performance penalties
- `Security council or emergency multisig`
  - can trigger urgent blacklist actions
- `DAO governance / timelocked admin`
  - confirms, reverses, or finalizes blacklist status
  - authorizes unblacklist decisions

This separation is useful because blacklisting is too powerful to leave inside routine liveness logic.

### Recommended Access Model

#### Blacklist

Blacklisting should be callable only through governance-controlled coordinator logic.

Recommended authority:
- `DinCoordinator` owned by DAO multisig or governance executor
- optional emergency sub-role for a security council

#### Unblacklist

Unblacklisting should be harder than blacklisting.

Recommended authority:
- DAO governance only, or
- coordinator owner subject to timelock, or
- security council proposal followed by DAO confirmation

The reason is that restoring a malicious validator is usually more dangerous than temporarily freezing one.

### Recommended Contract Additions

At minimum:

#### In `DinValidatorStake.sol`

Add:

```solidity
function unblacklistValidator(address validator) external onlyDinCoordinator;
```

Recommended behavior:
- revert on zero address;
- require current status is `Blacklisted`;
- clear blacklist state;
- call `_syncValidatorStatus()` so validator resumes as:
  - `Active` if `activeStake >= MIN_STAKE` and no pending withdrawal;
  - `Exiting` if stake remains but is below threshold or exit is pending;
  - `None` if nothing remains.

Optional but recommended:
- emit `ValidatorUnblacklisted(address indexed validator)`.

#### In `DinCoordinator.sol`

Add governance-forwarding functions:

```solidity
function blacklistValidator(address validator) external onlyOwner;
function unblacklistValidator(address validator) external onlyOwner;
```

Those should delegate to the stake contract.

This makes coordinator the explicit governance gate instead of embedding governance policy in the stake contract itself.

---

## Recommended Blacklist Workflow

### A. Emergency Blacklist Flow

1. Risk is detected by monitoring, community reports, or protocol operators.
2. Evidence is reviewed off-chain by the authorized governance or security actor.
3. Coordinator calls `blacklistValidator(validator)`.
4. Stake contract sets status to `Blacklisted`.
5. Validator instantly becomes ineligible for new work.
6. Task contracts naturally stop accepting the validator because `isValidatorActive()` becomes false.
7. If needed, slashers may still apply pending penalties to remaining slashable funds.

### B. Governance Review Flow

After emergency action, governance should decide one of:
- maintain blacklist permanently;
- apply additional slashing or other penalties;
- restore validator through unblacklisting if the case was mistaken or remediated.

### C. Unblacklist / Whitelist Restoration Flow

If governance decides to restore the validator:

1. Governance or DAO admin approves restoration.
2. Coordinator calls `unblacklistValidator(validator)`.
3. Stake contract removes blacklist status.
4. `_syncValidatorStatus()` recalculates the right state.
5. Validator becomes:
   - `Active` if sufficiently staked and not exiting;
   - `Exiting` if stake remains but active conditions are not met;
   - `None` if no usable stake remains.
6. Validator must re-enter normal protocol flows subject to role-contract checks.

Important:
- unblacklisting should restore eligibility only if the validator still satisfies normal staking conditions;
- it should not bypass `MIN_STAKE`, pending withdrawal state, or jail state;
- it should not auto-register the validator in downstream task rounds.

---

## Coordination With Other Contracts

### `DINTaskCoordinator.sol`

Should coordinate with blacklist state as follows:
- use `isValidatorActive()` before registration;
- use `isValidatorActive()` before accepting submissions or selecting validators;
- exclude blacklisted validators from candidate pools;
- continue using `slash()` for routine misconduct, not blacklist.

If a validator is blacklisted mid-lifecycle:
- future participation should stop automatically via active-status checks;
- any round-specific cleanup logic may still be needed in task-contract state.

### `DINTaskAuditor.sol`

Should follow the same pattern:
- no new Auditor participation if validator is blacklisted;
- no reliance on raw stake balance alone;
- blacklist is treated as immediate ineligibility.

### `DinCoordinator.sol`

Should become the explicit governance bridge for:
- slasher authorization;
- blacklist initiation;
- unblacklist restoration.

This keeps the stake contract focused on state transitions while governance policy lives in the coordinator layer.

### Off-Chain Monitoring / DAO Operations

Off-chain systems are likely to initiate blacklist proposals because they can aggregate evidence that is hard to compute on-chain, such as:
- repeated malicious pattern analysis;
- exploit forensics;
- identity-level sybil clustering;
- key-compromise reports;
- community or governance disputes.

That means blacklist decisions will often begin off-chain and end on-chain through the coordinator.

---

## Scenarios

### Scenario 1: Normal Fault, No Blacklist

- Aggregator misses a submission.
- `DINTaskCoordinator` slashes the validator.
- Validator remains in the protocol if enough stake remains.

Use case: routine liveness enforcement.

### Scenario 2: Repeated Malicious Validator

- Validator repeatedly submits bad work across rounds.
- Task contracts apply normal slashes.
- Governance determines behavior is no longer tolerable.
- Coordinator blacklists validator.

Use case: escalation from economic penalties to governance exclusion.

### Scenario 3: Validator Attempts Exit Before Penalty

- Validator requests unstake.
- Funds move to `pendingWithdrawals`.
- Before claim, evidence of fault is proven.
- Slasher contract penalizes the pending withdrawal.

Use case: unbonding preserves slashability without needing blacklist.

### Scenario 4: Compromised Validator Key

- Security operators detect key compromise.
- Governance or emergency multisig blacklists validator immediately.
- Validator cannot keep participating while the incident is investigated.
- Later, governance may choose permanent removal or restoration under a new operational policy.

Use case: blacklist as emergency containment, not routine punishment.

### Scenario 5: Mistaken Blacklist

- Validator is blacklisted due to bad evidence or false attribution.
- Governance review finds the blacklist incorrect.
- Governance triggers `unblacklistValidator()`.
- Validator returns only to the status supported by remaining stake state.

Use case: unblacklist as controlled recovery, not automatic forgiveness.

---

## Recommended Policy Rules

For a well-thought blacklist system, the policy should state at least:

- who may propose a blacklist;
- who may execute a blacklist;
- whether emergency blacklists bypass timelock;
- how evidence is recorded off-chain or on-chain;
- who may unblacklist;
- whether unblacklisting requires a delay or formal vote;
- whether blacklisted funds remain slashable;
- whether blacklisted funds may ever be withdrawn;
- whether a blacklisted validator must re-register in task contracts after restoration.

Without those rules, blacklist power becomes governance ambiguity rather than a security mechanism.

---

## Recommended Next Steps

1. Add coordinator-level blacklist forwarding so the current blacklist path is actually reachable.
2. Add `unblacklistValidator()` to `DinValidatorStake.sol`.
3. Emit explicit blacklist and unblacklist events.
4. Make all role contracts rely on `isValidatorActive()` rather than raw balance checks for access control.
5. Define governance policy for emergency blacklist, review, and restoration.
6. Decide whether blacklisted pending withdrawals remain forever frozen or can later be released by governance.

---

## Summary

The DIN staking mechanism already has the right direction on unbonding and slashability, but blacklist logic is still incomplete as a governance system.

A production-grade approach should treat:
- slashing as routine automated enforcement;
- blacklisting as exceptional governance isolation;
- unblacklisting as a stricter, review-based restoration path.

That separation keeps validator operations predictable while preserving a strong emergency control when a validator becomes too risky to leave in normal circulation.
