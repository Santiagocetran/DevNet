# Good First Issues

Welcome to the Infinite Zero Network DevNet repository.

This document is a lightweight entry point for contributors who want to work on beginner-friendly tasks across decentralized AI, federated learning, privacy-preserving systems, blockchain coordination, and developer tooling.

Use this page to understand the available issue areas. Each detailed issue lives in `Developer/issues/`.

## About Infinite Zero Network

Infinite Zero Network is a decentralized federated learning and AI coordination protocol built around:

- public blockchain coordination
- validator-based aggregation
- IPFS-based model exchange
- decentralized reward distribution
- privacy-preserving AI training
- scalable subgroup aggregation
- trustless auditing and evaluation

## Contribution Areas

| Area | Description |
|---|---|
| Federated Learning | Local model training, aggregation, optimization |
| Differential Privacy | DP-SGD, clipping, privacy accounting |
| Blockchain | Smart contracts, validator coordination |
| IPFS | Model storage and distribution |
| Aggregation | Validator-based decentralized aggregation |
| Evaluation | Reward scoring and benchmarking |
| Security | Sybil resistance, secure aggregation |
| DevOps | Testing, CI/CD, Docker |
| CLI | `dincli` improvements |
| Documentation | Guides, onboarding, examples |

## Open Issues

### 1. Differential Privacy Improvements

- Difficulty: Beginner -> Intermediate
- Area: Privacy-Preserving Federated Learning
- Detailed issue: [issues/DifferentialPrivacy.md](issues/DifferentialPrivacy.md)

This issue focuses on improving the current differential privacy workflow used in local training and model update submission.

At a high level, contributors will explore:

- stronger privacy mechanisms than post-training weight perturbation
- configurable clipping and noise settings
- privacy accounting and reporting
- better integration with `dincli`, client services, auditor workflows, and aggregation flows

Relevant code paths:

- `cache_model_0/services/client.py`
- `cache_model_0/services/model.py`
- `dincli/`

## How To Contribute

1. Pick an issue from this list.
2. Read the detailed issue document in `Developer/issues/`.
3. Review the relevant code paths before making changes.
4. Implement the change with tests or supporting documentation.
5. Submit a pull request with a clear explanation of the improvement.

Example:

```bash
git checkout -b feature/improve-differential-privacy
```

## Need Help?

Open a discussion or issue if you need:

- onboarding help
- architecture clarification
- research direction
- implementation guidance

We welcome contributors from AI/ML, cryptography, distributed systems, blockchain, privacy-preserving computing, and open-source communities.
