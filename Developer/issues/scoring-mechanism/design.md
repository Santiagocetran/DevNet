# Scoring Mechanism Design

## Goals

This design solves a specific mismatch in the current DIN evaluation model:

- the repo has one auditor contract path;
- real tasks need different scoring behavior depending on labels, task type, and reward policy;
- the current interface only carries one scalar score and one boolean eligibility vote.

The design goals are:

- make scoring mode explicit and scenario-driven;
- separate admission scoring from reward or contribution scoring;
- support dataset-based and dataset-free flows without lying about what the score means;
- keep rich metrics off-chain while making compact decisions on-chain;
- document rejected ideas (e.g., TKNN-Shapley) to ensure future iterations avoid incompatible valuation designs.

## Non-Goals

This design does not try to provide:

- perfect universal metrics for every ML task;
- trustless verification of every off-chain evaluation artifact;
- a complete reward-distribution mechanism in the first iteration;
- per-round exact Shapley valuation for arbitrarily large deep models.

## Current Constraints In This Repository

The design has to fit the code that exists today.

Today:

- `cache_model_0/services/auditor.py` and `dincli/services/auditor.py` return `(score, eligible)`;
- `cache_model_0/services/modelowner.py` and `dincli/services/modelowner.py` generate one test shard CID per batch;
- `DINTaskAuditor.setAuditScorenEligibility(...)` accepts one scalar score and one boolean vote;
- `DINTaskAuditor.finalizeEvaluation(...)` uses mean score and `passScore`;
- `DINTaskAuditor.AuditBatch` stores `testDataCID`, not a richer evaluation spec.

That means the scoring redesign should keep the same broad auditor flow, but widen the artifacts and summary objects that pass through it.

## Scoring Planes

The most important design decision is to stop calling everything "score."

DIN needs three separate scoring planes.

### 1. Eligibility Plane

This answers:

- does the model load;
- does it match the expected architecture;
- are tensor shapes correct;
- are there NaNs or invalid weights;
- is the update obviously corrupted or out of policy.

This is a gate, not a reward score.

### 2. Utility Plane

This answers:

- how useful is this local model for admission to aggregation;
- how well does it perform on a trusted evaluation mechanism for this task scenario.

This is the score that most directly determines aggregation approval.

### 3. Contribution Plane

This answers:

- how much useful signal did the client or shard contribute relative to others;
- how should rewards, reputation, or diagnostics be weighted.

This is where leave-one-out and marginal delta belong (TKNN-Shapley was rejected due to FL privacy constraints).

## Scenario Matrix

The protocol should select scoring mode from scenario, not from one default metric.

| Scenario | Main question | Recommended admission mode | Recommended contribution mode |
|---|---|---|---|
| labeled holdout classification | is the submitted model good enough to aggregate | stratified holdout metrics plus baseline delta | optional post-round delta or leave-one-out |
| imbalanced classification | does the model help across minority classes | macro-F1, balanced accuracy, loss | optional reward reweighting by class-sensitive delta |
| regression | does the model reduce prediction error | MAE, RMSE, R2 | optional leave-one-out or marginal delta |
| ranking or retrieval | does the model improve ranking quality | NDCG, MAP, recall@k | optional contribution on ranking delta |
| no trusted labels | can the model be screened safely | conformance plus anomaly-only screening | reward disabled or weak heuristic |
| data quality diagnostics | which clients or shards are noisy or mislabeled | keep admission separate | leave-one-out or marginal delta (TKNN-Shapley rejected) |
| privacy-sensitive contribution analysis | how can DIN value data without exposing raw examples | keep admission simple | private shard valuation (DP-TKNN-Shapley rejected) |

This matrix is the core reason DIN should not keep a one-size-fits-all `accuracy` path.

## Why TKNN-Shapley is Rejected

TKNN-Shapley is completely incompatible with the Federated Learning setting used in DIN. 

1. **Privacy Violation**: TKNN-Shapley requires direct, centralized access to training features and labels ($x_{train}, y_{train}$) to calculate pairwise distance bounds. Under FL constraints, this data is private and not shared with the auditor or coordinator.
2. **Target Mismatch**: TKNN-Shapley evaluates the marginal contribution of *individual data points*, not local models or clients.

Thus, TKNN-Shapley is officially rejected for the DIN protocol. For a full breakdown of the technical mismatch, see the [TKNN-Shapley Rejection Document](../../rejected-ideas/tknn-shapley.md).

## Recommended Mode Library

DIN should define a small library of scoring modes instead of one hardcoded algorithm.

### Admission modes

- `holdout_metrics`
- `holdout_delta`
- `screening_only`

### Contribution modes

- `none`
- `leave_one_out`
- `marginal_global_delta`
- (Rejected: `tknn_shapley`, `dp_tknn_shapley` - see [Rejected Ideas: TKNN-Shapley](../../rejected-ideas/tknn-shapley.md))

### Aggregation modes for auditor reports

- `mean`
- `median`
- `trimmed_mean`

For production-oriented design, `median` or `trimmed_mean` should be preferred over `mean`.

## Policy Schema

The static configuration should live in the manifest as a `scoring_policy` block.

Example:

```json
"scoring_policy": {
  "spec_version": 1,
  "scenario": "labeled_holdout_classification",
  "admission_mode": "holdout_delta",
  "contribution_mode": "none",
  "fallback_mode": "screening_only",
  "normalization": {
    "utility_scale": "basis_points",
    "max_utility": 10000
  },
  "eligibility_checks": {
    "require_loadable_model": true,
    "require_architecture_match": true,
    "reject_nan_tensors": true,
    "max_update_norm": 25.0
  },
  "metrics": {
    "primary": ["accuracy", "macro_f1", "loss", "baseline_delta"],
    "thresholds": {
      "min_utility_score": 6500,
      "min_baseline_delta_bps": 0,
      "max_auditor_variance_bps": 800
    }
  },
  "aggregation": {
    "auditor_score_aggregation": "median",
    "require_variance_bound": true
  },
  "contribution": {
    "enabled": false,
    "backend": "none"
  }
}
```

This block should define what the task expects, but it should not contain per-round shard assignments or dynamic batch artifacts.

## Dynamic Evaluation Spec

The per-batch execution plan should be a separate off-chain artifact referenced during a GI.

Call it `evaluationSpec`.

Example:

```json
{
  "spec_version": 1,
  "gi": 4,
  "batch_id": 2,
  "mode": "holdout_delta",
  "screening_only": false,
  "dataset_shard_cids": [
    "bafy...",
    "bafy..."
  ],
  "baseline_model_cid": "bafy...",
  "metric_bundle": {
    "primary": ["accuracy", "macro_f1", "loss", "baseline_delta"],
    "normalization": "basis_points"
  },
  "sampling": {
    "strategy": "stratified",
    "repetitions": 2
  }
}
```

Why DIN needs this:

- batch-specific shard assignments are dynamic;
- some scenarios have no dataset shard at all;
- the baseline reference may change by GI;
- the auditor needs more context than a single `testDataCID`.

## On-Chain and Off-Chain Split

DIN should keep detailed evaluation data off-chain and only store compact summaries on-chain.

### Off-chain artifacts

- `scoring_policy` in manifest
- `evaluationSpec` per batch or GI
- full auditor metric bundle
- optional contribution report output

### On-chain summaries

- eligibility vote
- normalized utility score
- optional normalized baseline delta
- optional anomaly or disagreement score
- `metricBundleCID`
- evaluation mode or screening flag

This split keeps the contract practical while still making scoring auditable.

## Normalized Audit Result

To support scenario-specific raw metrics without exploding contract complexity, auditors should submit a normalized summary object.

Conceptually:

```text
AuditResult
- eligible: bool
- utility_score_bps: uint16
- baseline_delta_bps: int32
- anomaly_score_bps: uint16
- screening_only: bool
- metric_bundle_cid: bytes32
```

The rule is:

- raw task-specific metrics stay in the metric bundle;
- off-chain policy maps them into normalized scores;
- the contract only aggregates normalized summaries.

This is the cleanest way to support multiple scenarios without teaching Solidity every ML metric family.

## Robust Auditor Aggregation

The current average-based aggregation is too brittle.

DIN should aggregate auditor summaries using one of:

- median utility score;
- trimmed mean utility score;
- variance or disagreement bound.

Recommended approval policy:

- `eligible_quorum_met == true`
- `median_utility_score >= min_utility_score`
- `auditor_variance <= max_auditor_variance`
- if required, `baseline_delta >= min_delta`

This keeps the approval rule robust even when one auditor is noisy or dishonest.

## No-Label Scenario

When no trusted evaluation set exists, DIN should downgrade honestly.

Recommended semantics:

- do not generate a normal utility score;
- run only conformance and anomaly checks;
- set `screening_only = true`;
- mark submissions as `screened` rather than `performance_validated`.

That avoids the architectural mistake of turning weak proxy signals into false performance claims.

## Contribution Scoring Design

Contribution scoring should be a separate pipeline from admission scoring.

### Supported backends

- `leave_one_out`
- `marginal_global_delta`

*(Note: Advanced backends like `tknn_shapley` and `dp_tknn_shapley` have been rejected due to FL privacy constraints. See [Rejected Ideas: TKNN-Shapley](../../rejected-ideas/tknn-shapley.md) for details.)*

### Output form

Contribution backends should produce a separate `contributionReportCID` that maps:

- client address or local-model index;
- contribution score;
- confidence or privacy parameters;
- diagnostic tags such as noisy, low-value, or suspicious.

This report can later feed reward distribution or governance decisions without changing the admission path.

## Recommended DevNet Defaults

DIN should not try to enable every mode at once.

### Current MNIST-like path

Use:

- `scenario = labeled_holdout_classification`
- `admission_mode = holdout_delta`
- `contribution_mode = none`
- metrics: `accuracy`, `loss`, `macro_f1`, `baseline_delta`
- aggregation: `median`

### First advanced extension

Add:

- `contribution_mode = leave_one_out`

### Later experimental extension

Add other privacy-preserving contribution modes as needed, ensuring they do not leak client training data.

## Contract Direction

The contract should stop assuming that scoring means "one scalar plus one test dataset."

Recommended changes:

- supplement or replace `testDataCID` with `evaluationSpecCID`;
- add a `V2` audit-result submission method that accepts normalized summary fields plus `metricBundleCID`;
- store final normalized utility and agreement summaries on `LMSubmission` or related storage;
- finalize approval from policy-compatible thresholds rather than only `avg(score) >= passScore`.

The contract should not parse metric families like F1, NDCG, or RMSE directly. Those stay off-chain.

## Trust Model

This design is still honest-but-auditable, not fully trustless.

That is acceptable for DevNet because:

- auditors already execute off-chain evaluation;
- metric bundles and evaluation specs can be published by CID;
- normalized summaries make the contract small;
- scenario-aware semantics are still far better than a misleading universal accuracy score.

The immediate goal is accuracy of system design, not pretending that every ML evaluation artifact is fully verifiable on chain.
