# Auditor Scoring Mechanism

## Summary

DIN should stop treating scoring as:

- one test shard
- one accuracy number
- one average threshold

That works for the current demo path, but it is too narrow for production evaluation and it does not support different task scenarios cleanly.

The protocol needs a scenario-driven scoring system where:

1. eligibility is separated from utility;
2. utility scoring changes by task type and data availability;
3. contribution scoring is treated as a separate plane from admission scoring;
4. no-label tasks fall back to screening rather than pretending to have a real performance score.

## Problem Restated

The current stack is locked to one very specific path:

- model owner creates a small test shard per auditor batch;
- auditor computes top-1 accuracy;
- `DINTaskAuditor.sol` averages scores;
- approval is `eligible && avg(score) >= passScore`.

That creates three design failures:

- the protocol mixes conformance, utility, and reward logic into one scalar;
- the contract assumes dataset-based scoring is always available;
- different task scenarios cannot swap in a different scoring method without changing code by hand.

## Core Design Direction

Scoring should be organized into three separate planes.

### 1. Admission scoring

This decides whether a submitted local model is safe and useful enough to enter aggregation.

Examples:

- conformance checks
- holdout utility score
- baseline delta
- auditor agreement bounds

### 2. Reward or contribution scoring

This decides how much credit or reward a client should receive after the round.

Examples:

- leave-one-out contribution
- post-aggregation marginal utility
- client-level or shard-level TKNN-Shapley

### 3. Screening and anomaly scoring

This is the fallback when utility cannot be measured honestly.

Examples:

- malformed model detection
- update norm checks
- peer deviation or anomaly signals

## Scenario-Based Decision Summary

### 1. Trusted labeled holdout exists

Use dataset-based utility scoring, but make it policy-driven and robust:

- stratified shards, not hardcoded `5%`;
- multiple metrics, not only accuracy;
- robust aggregation across auditors, not raw mean.

### 2. Task is imbalanced or metric-sensitive

Use task-specific metrics as first-class policy inputs.

- classification: macro-F1, balanced accuracy, loss, calibration
- regression: MAE, RMSE, R2
- ranking or retrieval: NDCG, MAP, recall@k

### 3. Task has no trusted labeled evaluation set

Do not claim real performance scoring.

Use:

- conformance checks
- anomaly or agreement signals
- `screened` semantics instead of `performance-validated`

### 4. Task needs contribution-aware rewards

Use a separate contribution layer after or alongside admission scoring.

This is where:

- leave-one-out
- marginal global-model delta
- approximate Shapley-style methods

belong.

### 5. Data-quality or privacy-sensitive scenario

This is where TKNN-Shapley fits best.

The `TKNN-Shapley` analysis is useful for:

- mislabeled-data detection
- noisy-data detection
- shard or client data-quality ranking
- privacy-friendlier contribution estimation

It is not the right direct replacement for the current auditor holdout score. It is best used as a contribution or data-valuation backend, not as the only model-admission signal.

## Key Decisions

### 1. Scoring policy should live in the manifest

The manifest should declare:

- the scenario;
- the scoring mode for admission;
- the scoring mode for rewards;
- the fallback mode when no labels exist;
- the metric family and aggregation policy.

### 2. Batch evaluation should use an evaluation spec, not only a test dataset CID

The current `testDataCID` field is too narrow.

DIN should move toward an `evaluationSpecCID` that can describe:

- dataset shards when they exist;
- baseline model reference;
- metric list;
- normalization rules;
- screening-only mode when no evaluation set exists.

### 3. On-chain storage should stay compact

The contract should store normalized summary values and CIDs, not every raw metric.

The detailed report should remain off-chain in a metric bundle artifact.

### 4. Robust aggregation should replace raw average

For admission scoring, DIN should prefer:

- median;
- trimmed mean;
- explicit agreement or variance checks.

### 5. TKNN-Shapley should be scoped to the right scenarios

In DIN, TKNN-Shapley should primarily support:

- reward weighting;
- client or shard quality diagnostics;
- mislabeled or noisy data screening;
- privacy-sensitive valuation experiments.

It should not be introduced as the default replacement for the current MNIST-style holdout scorer.

## Recommended DevNet Default

For the current `mnist-digits` style path, the recommended near-term scoring mode is:

- scenario: `labeled_holdout_classification`
- eligibility: loadability, architecture match, finite tensors, bounded update norm
- utility metrics: accuracy, loss, macro-F1, baseline delta
- aggregation: median utility plus variance bound
- approval: `eligible && utility >= threshold && disagreement <= bound`

TKNN-Shapley should be added later for contribution and reward experiments, not for first-pass model admission.

## Deliverables In This Folder

- [Design](scoring-mechanism/design.md): scoring planes, scenario matrix, policy schema, on-chain/off-chain split, and TKNN-Shapley placement
- [Implementation Plan](scoring-mechanism/implementation.md): phased repo changes across manifest, services, CLI, contracts, and tests

## Definition Of Done

This issue is properly addressed when DIN can:

- choose scoring behavior by declared scenario instead of hardcoded accuracy logic;
- separate eligibility, utility, and contribution outputs;
- support labeled and no-label evaluation modes honestly;
- submit compact score summaries plus off-chain metric bundles;
- aggregate auditor outputs robustly;
- plug in contribution backends such as leave-one-out or TKNN-Shapley without rewriting the whole audit flow.

## Out Of Scope For Initial Delivery

The first proper version does not need:

- a full secure-aggregation validation network;
- cryptographic guarantees for private client-reported metrics;
- real-time TKNN-Shapley on every deep-learning round;
- fully automated reward redistribution logic.

The immediate goal is to make scoring mode explicit, scenario-aware, and implementable in the current DevNet architecture.
