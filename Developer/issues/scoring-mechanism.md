# Auditor Scoring Mechanism

## Summary

This issue defines how auditors should score local models in DevNet and why the current mechanism is too narrow.

Today the system assumes that:

- the model owner has a labeled test dataset
- each auditor batch receives a small subset of that test dataset
- auditors score a local model with a single accuracy number
- the contract averages auditor scores and compares the result to a pass threshold

That is workable for a demo, but it is not a strong federated learning evaluation design.

## Current State

Current implementation is centered around:

- `cache_model_0/services/auditor.py`
- `cache_model_0/services/modelowner.py`
- `hardhat/contracts/DINTaskAuditor.sol`

The flow is roughly:

1. Model owner creates auditor batches on-chain.
2. Model owner samples a test subset per batch and uploads it to IPFS.
3. `DINTaskAuditor.sol` stores `testDataCID` for each batch.
4. Auditors retrieve the batch dataset and the submitted local model.
5. Auditors compute top-1 accuracy.
6. Auditors submit `(score, eligible)` on-chain.
7. Contract finalizes eligibility by quorum and final score by average.

Important current details:

- `create_audit_testDataCIDs(...)` hardcodes `testData_percentage_per_auditor_batch = 5`
- `Score_model_by_auditor(...)` uses one metric: classification accuracy
- `DINTaskAuditor.sol` assumes one shared `testDataCID` per batch
- approval is currently `eligible && avg(score) >= passScore`

## Why The Current Design Is Weak

### 1. It assumes a trusted labeled test dataset exists

That is a strong assumption. In many FL settings:

- labels are expensive
- the model owner may not have a representative centralized test set
- the centralized test set may violate the reason FL was chosen in the first place

FL is still useful even if training data is distributed and private. But evaluation still needs some trusted signal. If no trusted signal exists, the system cannot make strong claims about model utility.

### 2. A 5% shard per batch can be noisy and unfair

If each batch sees a small random shard:

- scores can vary a lot by shard composition
- class imbalance can distort the result
- two models may be ranked differently just because they saw different examples
- a small shard is easy to overfit to if it leaks over time

This is especially weak when:

- the total test set is small
- the task is imbalanced
- the metric is only accuracy

### 3. Accuracy alone is too simplistic

Accuracy is often the wrong single metric. It misses:

- class imbalance
- calibration
- regression quality
- ranking quality
- robustness to noisy inputs
- whether the local update actually improved over the starting model

### 4. The current design mixes two different questions

Auditors are effectively answering both:

1. Is this submission valid and eligible?
2. How useful is this submission for aggregation?

Those should not rely on the same single accuracy score.

### 5. If no evaluation dataset exists, current scoring collapses

Without a test dataset:

- the current auditor service cannot score at all
- the contract design still expects a score
- the protocol has no fallback notion of contribution quality

That is the main architectural gap.

## What FL Evaluation Should Actually Do

The protocol should separate:

### A. Eligibility checks

These are binary or rule-based checks:

- model file loads correctly
- architecture matches the expected genesis model
- tensor shapes match
- update norm is within expected bounds
- submission is not obviously corrupted or adversarial
- training metadata is complete

This answers: should the model even be considered?

### B. Utility scoring

This is the contribution score used for ranking, approval, or rewards.

This answers: how much useful signal does this update contribute?

### C. Auditor consensus

This determines whether auditor reports are consistent enough to trust.

This answers: are the auditors seeing the same thing, or is the evaluation unstable?

## Recommended Scoring Direction

The recommended direction is a layered mechanism, not a single test-set accuracy number.

## Proposed Scoring Stack

### Layer 1: Conformance and safety gate

A model should be marked `eligible = true` only if it passes basic checks such as:

- loadability
- schema and architecture match
- bounded update norm
- no NaNs or invalid tensors
- optional anti-poisoning heuristics

This should remain auditor-driven and can still finalize by quorum.

### Layer 2: Utility score on trusted evaluation data

If trusted labeled evaluation data exists, use it, but use it better:

- prefer one hidden evaluation pool over ad hoc small shards
- use stratified sampling instead of naive random sampling
- evaluate each model on multiple shards or multiple rounds
- aggregate with median or trimmed mean across auditors instead of raw mean
- score relative improvement over the genesis model or previous global model

The score should be based on task-appropriate metrics:

- classification: loss, macro-F1, balanced accuracy, calibration, not only accuracy
- regression: MAE, RMSE, R2
- ranking/retrieval: NDCG, MAP, recall@k

### Layer 3: Contribution-based score

The most meaningful FL score is not only "how good is this model alone?" but also "does this update help the global model?"

Better options include:

- delta score against the baseline model on the same hidden evaluation set
- marginal contribution to the aggregated model
- leave-one-out contribution after aggregation
- approximate Shapley-style contribution in later iterations if cost is acceptable

This is more faithful to FL than standalone local-model accuracy.

### Layer 4: Agreement and anomaly score

Even when using evaluation data, auditors should compute consistency signals:

- score variance across auditors
- disagreement with peer auditors
- deviation of model update from cohort distribution
- cosine similarity or norm-based anomaly detection on model deltas

This is useful for slashing, dispute handling, and poisoning detection.

## What If No Test Dataset Is Available?

This needs an explicit answer in the protocol.

If no trusted labeled test dataset exists, the system should not pretend it can produce a reliable utility score from nothing.

Instead, the protocol should fall back to one of these modes:

### Option 1. Public or third-party benchmark set

Use a benchmark dataset outside the private training pool.

Pros:

- simple
- reproducible
- easy to compare models

Cons:

- may not match the real task distribution
- can be gamed if exposed

### Option 2. Hidden server-side holdout owned by model owner

This is the cleanest practical option when available.

Pros:

- direct task relevance
- strong utility measurement

Cons:

- requires centralized labeled data
- partially undermines the claim that all useful data is decentralized

### Option 3. Client-provided validation with secure aggregation of metrics

Clients evaluate candidate models on their local validation slices and only share aggregated metrics.

Pros:

- keeps raw validation data local
- closer to FL principles

Cons:

- harder to trust
- vulnerable to collusion or dishonest reporting without extra cryptographic work

### Option 4. Proxy scoring without labels

If no labeled data exists anywhere, only use proxy signals such as:

- update norm and stability checks
- agreement with cohort updates
- improvement on synthetic or weakly labeled challenge data
- confidence and consistency metrics on unlabeled reference inputs

Pros:

- works without labels

Cons:

- this is not a true utility score
- should be treated as risk screening, not model-quality proof

### Protocol conclusion

If there is no trusted evaluation dataset, the protocol should downgrade from "performance scoring" to "conformance and anomaly screening".

That is the honest design boundary.

## Is Small-Dataset Scoring Fair?

Only sometimes.

It can be acceptable for DevNet smoke testing, but it is not robust enough as the main production scoring mechanism unless the system adds:

- stratified sampling
- repeated evaluation across multiple shards
- uncertainty or confidence intervals
- robust aggregation of auditor scores
- metric selection per task

Without those protections, a 5% shard score is too brittle to determine rewards or aggregation approval.

## Better Mechanisms For DevNet

A pragmatic path for DevNet is:

### Phase 1. Improve the current dataset-based approach

- stop hardcoding `5%`
- define evaluation policy per task
- support stratified shard generation
- evaluate against multiple shards per model
- submit metric bundles, not only one score
- use median or trimmed mean for final score
- record variance across auditor reports

### Phase 2. Separate eligibility from utility

- keep `eligible` for conformance and safety
- define `utilityScore` independently
- allow approval logic to depend on both

Example:

- `eligible == true`
- `utilityScore >= threshold`
- `auditorVariance <= maxVariance`

### Phase 3. Add contribution-aware scoring

- compare each submitted local model to the baseline model
- measure whether it improves the post-aggregation result
- consider leave-one-out contribution for reward weighting

### Phase 4. Support dataset-free fallback mode

If no trusted test set exists:

- skip utility scoring
- run only conformance and anomaly checks
- mark results as `screened` rather than `performance-validated`

## Contract And Service Implications

The current contract and service interfaces are too narrow for this direction.

Likely changes:

### Auditor service

`Score_model_by_auditor(...)` should evolve from returning just:

- `score`
- `eligible`

to returning a richer result such as:

- `eligible`
- `utility_score`
- `baseline_delta`
- `anomaly_score`
- `metric_bundle_cid`

The detailed metrics can stay off-chain, with only compact summary values on-chain.

### Model-owner service

`create_audit_testDataCIDs(...)` should become policy-driven:

- dataset source
- shard count
- shard size
- stratification rules
- metric type
- fallback mode when no test dataset exists

### Smart contract

`DINTaskAuditor.sol` should stop assuming that evaluation always means one `testDataCID` plus one scalar score.

Better directions:

- replace or supplement `testDataCID` with an `evaluationSpecCID`
- allow dataset-based and dataset-free evaluation modes
- store a compact summary of score components
- finalize approval using policy, not only `avg(score) >= passScore`

## Recommended Policy

For DevNet, the recommended policy is:

1. Keep auditor-based evaluation.
2. Separate eligibility checks from utility scoring.
3. Treat the current 5% test-set shard approach as a temporary baseline only.
4. Move to stratified multi-shard evaluation with robust aggregation.
5. Add a fallback mode for tasks where no trusted labeled evaluation dataset exists.
6. Do not claim strong performance scoring when only proxy signals are available.

## Proposed Scope Of Work

Contributors working on this issue should aim to:

- document evaluation modes supported by the protocol
- define required versus optional scoring signals
- replace hardcoded 5% batch sampling with configurable policy
- define task-specific metric bundles
- add robust score aggregation across auditors
- define a no-test-dataset fallback mode
- update contract storage and workflow to support richer evaluation outputs
- define how reward and aggregation approval consume those outputs

## Bottom Line

The current mechanism is acceptable as a demo path, but not as the long-term scoring design.

The protocol should move from:

- one batch dataset
- one accuracy score
- one average threshold

toward:

- explicit eligibility checks
- robust utility scoring
- contribution-aware evaluation
- honest fallback behavior when no trusted evaluation dataset exists
