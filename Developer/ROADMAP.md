# DIN Roadmap

---

## P2: Devnet Launch and CLI Release *(Completed — April 2026)*

**Timeline:** November 1, 2025 to April 30, 2026  
**Duration:** ~24 weeks

### Goal

Deploy the DIN devnet on Optimism Sepolia, release `dincli`, and onboard validators and stakeholders to a publicly usable network.

### Phase Goals

**Near-term (Weeks 1–8, November 2025 – January 2026)**  
Smart contract optimization for L1 and L2 cost models; migration from Hardhat to Foundry; USDT flow removal; stake threshold reduction.

**Short-term (Weeks 9–18, February – March 2026)**  
L2 deployment on Optimism Sepolia; wallet provisioning for ~70 test accounts; contract deployment and verification.

**Long-term (Weeks 19–24, April 2026)**  
CIDv1 migration; `dincli` release; full documentation and flow guides; stakeholder onboarding; public devnet launch.

### Phase Outcome

DIN devnet live on Optimism Sepolia. `dincli v0.1.0` released. Validator onboarding flows documented. Public devnet accessible.

---

## P3: Cryptoeconomic Layer and Network Hardening

**Timeline:** May 1, 2026 to August 30, 2026  
**Duration:** ~16 weeks  
**Current week:** Week 8 (June 22–26, 2026)

### Goal

Deliver the economic, governance, and security foundations required to make DIN testnet-ready. This phase introduces staking, slashing, rewards, scoring, tokenomics, fee flows, DAO-governed protocol controls, and stronger network-level security guarantees.

### Phase Goals

**Near-term (Weeks 8–11, June 22 – July 17, 2026)**

- Complete slashing conditions, slashing engine, and dispute resolution — enables enforceable validator accountability
- Implement validator operational readiness (Task 0): containerised run path, keystore security, SIGTERM handling, and resource documentation — blocking requirements for external validators joining the network
- Validate and harden the BlockFLow-inspired contribution scoring: marginal gain gating + cross-validator median aggregation; replaces Shapley approximation which requires per-sample access validators do not have

**Short-term (Weeks 11–13, July 13 – July 31, 2026)**

- Token utility design and emission model
- Protocol fee structure, routing, and dynamic fee logic
- DAO-governed protocol parameter controls

**Long-term (Weeks 14–16, August 2026)**

- Full devnet integration of all P3 components
- Adversarial, collusion, Sybil, and stress testing
- Smart contract audits; gas optimisation and L2 readiness
- Public documentation: staking guide, slashing rules, validator guide, tokenomics paper

---

### Topics and Milestones

#### Task 0: Validator Operational Readiness *(Near-term — Weeks 9–10, Blocking)*

Deliver the infrastructure hygiene required for external validators to safely bring a node online. The following requirements were raised as blocking conditions before any external validator will commit to running a node. Getting these in place now also lowers the bar for every subsequent operator.

**Focus areas**
- One-command containerised run path for validator nodes (Docker / docker-compose)
- Passphrase-prompted keystore management; no plaintext private keys in `.env`
- Documented resource ceiling (RAM, CPU, disk, network) for operator planning
- Graceful SIGTERM handling to prevent local state corruption on restart

**Target window:** Late June to early July 2026

**WP 0.1: Containerised Validator Run Path**  
**Duration:** June 29, 2026 to July 3, 2026 (Week 9)

Activities:
- Write Dockerfile for the `din-node` validator image
- Write `docker-compose.yml` with one-command start, stop, and upgrade flows
- Document environment variable configuration and volume mounts
- Test full validator workflow end-to-end inside the container

Deliverables:
- `Dockerfile` and `docker-compose.yml`
- Operator setup guide for containerised path
- Verified end-to-end test run

**WP 0.2: Keystore Security, SIGTERM Handling, and Resource Documentation**  
**Duration:** July 6, 2026 to July 10, 2026 (Week 10)

Activities:
- Implement passphrase-prompted keystore support; remove plaintext key patterns from `.env` examples and documentation
- Document migration path from plaintext keys to encrypted keystore
- Implement and test graceful SIGTERM handler; verify no state corruption on forced restart
- Document resource ceilings (minimum and recommended RAM, CPU, disk, network)

Deliverables:
- Keystore migration guide
- SIGTERM handler with restart tests
- Updated `.env.example` with no plaintext key references
- Operator resource requirements document

---

#### 1. Staking Infrastructure *(Completed — May 2026)*

Build the validator staking layer that enables economic commitment, stake-weighted participation, and configurable validator selection across subgroups.

**Focus areas**
- Validator staking contracts
- Deposit, withdrawal, and lock-period logic
- Two-phase validator exits with enforced unbonding windows
- Pending-withdrawal slashability until exit finalisation
- Minimum stake thresholds
- Validator registry integration
- Randomised validator selection
- Validator rotation and subgroup assignment
- Validator-to-participant ratio enforcement

**Target window:** May 2026

**WP 1.1: Validator Staking Contract**  
**Duration:** May 4, 2026 to May 8, 2026 (Week 1)

Activities:
- Design staking contract architecture
- Implement deposit and withdrawal logic
- Define lock periods and minimum stake
- Integrate validator registry

Deliverables:
- Staking smart contract (`v1`)
- Unit tests
- Validator registry integration module

**WP 1.2: Validator Selection Logic**  
**Duration:** May 11, 2026 to May 15, 2026 (Week 2)

Activities:
- Implement randomised validator selection
- Design subgroup assignment logic
- Implement validator rotation
- Define validator-to-participant ratio

Deliverables:
- Validator selection engine
- Rotation mechanism
- Fairness testing report

---

#### 2. Differential Privacy and Contribution Scoring *(Completed — May 2026; scoring approach revised June 2026)*

Implement and validate the core mechanisms for evaluating model update contributions while balancing privacy, accuracy, and poisoning resistance. The contribution scoring approach follows the BlockFLow design (MIT, 2020): model-update-level scoring on validation data, requiring no access to raw client samples, and compatible with differential privacy applied directly to weight updates.

**Key design decisions:**

- TKNN-Shapley is not applicable here. It scores individual data samples and requires the raw points; our validators only ever see the model update, not client samples. This is an information-theoretic constraint, not an engineering gap. TKNN-Shapley can only be a client-side curation tool, which does not serve our scoring or reward goals.
- BlockFLow lines up with our architecture point for point: update-level scoring on validation data, DP on shared weights, median aggregation across evaluators, proportional reward payout. The one BlockFLow term we do not carry over is their evaluation-honesty second score, which exists because their agents evaluate each other. Our clients never evaluate each other; validator honesty is covered by staking and the cross-validator median.

**Focus areas**
- Differential privacy applied to weight updates (Laplacian noise + per-update clipping)
- Clipping as a synergistic poisoning defence: bounding per-client update norm caps scaling attacks and is the same as the norm_cap in the scoring pre-filter
- ε tuning: noise floor vs. marginal gain signal sharpness
- Pre-filter before scoring: norm bounding (removes scaling attacks) + cosine similarity to consensus direction (removes directional outliers pointing against the validator majority)
- Marginal gain scoring: each update evaluated by applying it to the current running model and measuring validation accuracy improvement; gain > ε accepts the update; applied sequentially across random permutations of surviving updates
- Sequential model fold-in with permutation averaging (n_perms) for fair attribution; a duplicate update scores near zero once its first copy is folded in, giving duplicate-data discounting without extra machinery
- Cross-validator aggregation: majority vote for accept/reject; median of scores across validators for Byzantine tolerance (tolerates up to ~half of validators being malicious)
- Score reused as reward weight when rewards are enabled — no separate valuation layer needed
- Threat model: crude poisoning (label-flip, sign-flip, scaling, garbage updates) in-scope; backdoor attacks (which maintain clean-data accuracy) noted as a future extension requiring model-inspection defences

**Target window:** May 2026

**WP 2.1: Differential Privacy Integration on Weight Updates**  
**Duration:** May 18, 2026 to May 22, 2026 (Week 3)

Activities:
- Implement DP on shared weight updates (Laplacian noise + clipping)
- Align clipping norm with the norm_cap used in the scoring pre-filter
- Measure ε tradeoff: noise variance on marginal gain scores vs. detection sharpness
- Privacy-performance evaluation: verify gain signal stays above noise floor at chosen ε

Deliverables:
- DP integration module (update-level)
- Privacy-performance evaluation report

**WP 2.2: Contribution Scoring — BlockFLow Approach**  
**Duration:** May 25, 2026 to May 29, 2026 (Week 4)

Activities:
- Implement pre-filter: norm bounding + cosine similarity to consensus direction
- Implement marginal gain scoring with sequential fold-in and n_perms permutation averaging
- Implement cross-validator aggregation: majority vote (accept) and median (score)
- Benchmark: n_perms=1 cheap detection baseline vs. higher n_perms for reward attribution
- Document threat model: crude poisoning in-scope; backdoors as future work

Deliverables:
- Scoring module (pre-filter + marginal gain + cross-validator aggregation)
- Benchmark report (cost vs. detection accuracy)
- Threat model documentation

---

#### 3. Reward Distribution *(Completed — June 2026)*

Introduce contribution-aligned incentives for participants and validators, with distribution logic tied to measurable model impact and protocol activity.

**Focus areas**
- Contribution-weighted participant rewards; marginal gain score used directly as reward weight
- Aggregation and evaluation rewards for validators
- Reward split logic
- Fee-based validator incentives
- Reward claims, payout automation, and tracking
- Anti-free-rider protections; duplicate-update diminishing returns handled naturally by fold-in scoring

**Target window:** June 2026

**WP 3.1: Participant Reward Logic**  
**Duration:** June 1, 2026 to June 5, 2026 (Week 5)

Activities:
- Design contribution-weighted rewards using marginal gain scores
- Implement reward split logic
- Integrate scoring outputs

Deliverables:
- Reward calculation module
- Simulation results

**WP 3.2: Validator Incentive Mechanism**  
**Duration:** June 8, 2026 to June 12, 2026 (Week 6)

Activities:
- Implement aggregation rewards
- Implement evaluation rewards
- Design fee-based incentives

Deliverables:
- Validator incentive module
- Fee distribution logic

**WP 3.3: Reward Distribution Contract**  
**Duration:** June 15, 2026 to June 19, 2026 (Week 7)

Activities:
- Implement claim and payout functions
- Automate reward distribution
- Track rewards on-chain

Deliverables:
- Reward smart contract
- End-to-end payout tests

---

#### 4. Slashing and Fault Attribution *(In progress — Weeks 8–10)*

Define and enforce accountability mechanisms for invalid aggregation, incorrect evaluation, and inactivity, supported by deterministic verification and dispute handling.

**Focus areas**
- Slashing rules and deviation thresholds tied to cross-validator median scores
- Partial and full penalty models
- Slashability across active stake and unbonding stake
- Penalty redistribution
- On-chain and off-chain dispute triggers
- Re-execution and consensus mismatch checks
- Re-evaluation and validator reassignment workflows
- Public documentation for slashing rules, known validator failure modes, and operator-safe recovery steps

**Target window:** Late June to mid-July 2026

**WP 4.1: Slashing Conditions**  
**Duration:** June 22, 2026 to June 26, 2026 (Week 8) — *current week*

Activities:
- Define slashing rules and deviation thresholds
- Set scoring deviation bounds relative to cross-validator median
- Design on-chain event logging for slash-triggering conditions

Deliverables:
- Slashing specification document
- Configurable threshold module

**WP 4.2: Slashing Engine**  
**Duration:** June 29, 2026 to July 3, 2026 (Week 9)

Activities:
- Implement slashing logic in contract
- Define partial and full penalty tiers
- Implement penalty redistribution (treasury or remaining validators)

Deliverables:
- Slashing contract
- Simulation tests

**WP 4.3: Dispute Resolution Layer**  
**Duration:** July 6, 2026 to July 10, 2026 (Week 10)

Activities:
- Implement on-chain and off-chain dispute triggers
- Build re-evaluation workflows with validator reassignment
- Document known failure modes and operator recovery steps

Deliverables:
- Dispute resolution module
- Re-evaluation mechanism
- Operator failure-mode and recovery reference

---

#### 5. Tokenomics and Fee Layer *(Short-term — Weeks 11–13)*

Establish the protocol's economic backbone, including token utility, emission strategy, treasury design, and fee routing between model owners, validators, and the protocol treasury.

**Focus areas**
- Token utility for staking, rewards, and fee settlement
- Incentive loop design
- Emission schedule and distribution model
- Inflation versus sustainability modelling
- Treasury allocation
- Protocol fee structure and routing
- Dynamic fee logic
- DAO-governed protocol parameter controls

**Target window:** Mid-July to July 31, 2026

**WP 5.1: Token Utility Design**  
**Duration:** July 13, 2026 to July 17, 2026 (Week 11)

Activities:
- Define staking, rewards, and fee flows
- Design incentive loops and DAO governance hooks

Deliverables:
- Token utility document
- Economic flow diagrams

**WP 5.2: Emission and Distribution Model**  
**Duration:** July 20, 2026 to July 24, 2026 (Week 12)

Activities:
- Design emission schedule
- Model inflation vs. sustainability tradeoffs
- Allocate treasury

Deliverables:
- Emission model
- Simulation results

**WP 5.3: Fee Mechanism**  
**Duration:** July 27, 2026 to July 31, 2026 (Week 13)

Activities:
- Design protocol fee structure
- Implement fee routing (model owner → validator → treasury)
- Define dynamic fee logic

Deliverables:
- Fee mechanism contract
- Fee distribution tests

---

#### 6. Security, Integration, and Testnet Readiness *(Long-term — Weeks 14–16)*

Harden the full system through integration testing, adversarial validation, optimisation work, and audit preparation to support broader ecosystem rollout.

**Focus areas**
- Devnet integration of all P3 components
- Production-grade staking hardening: delayed withdrawals and post-service penalty windows
- Validator operator readiness checklist: key handling, resource ceilings, restart behaviour, monitoring basics
- Contract upgrade flows
- End-to-end integration testing
- Collusion, Sybil, and reward manipulation simulations
- Stress testing
- Smart contract audits
- Gas optimisation and L2 readiness
- Public-facing documentation: staking guide, slashing rules, validator guide, tokenomics paper

**Target window:** August 2026

**WP 6.1: Integration and Devnet Upgrade**  
**Duration:** August 3, 2026 to August 7, 2026 (Week 14)

Activities:
- Integrate all P3 components into devnet
- Perform contract upgrades
- Run end-to-end integration tests
- Build `dincli` CLI-level test harness: a minimal Python test suite (following the existing `CliRunner`/`monkeypatch` pattern in `tests/`) that deploys the upgraded proxy contracts against a local Hardhat node and asserts that key `dincli` command paths complete without error — covering at minimum `dindao` registry calls, the token/coordinator bootstrap flow, and validator stake operations against the new contract interfaces

Deliverables:
- P3-integrated devnet
- Integration test report
- `dincli` CLI-level test harness covering upgraded contract interfaces (prerequisite for testnet redeployment of proxy contracts)

**WP 6.2: Adversarial and Stress Testing**  
**Duration:** August 10, 2026 to August 14, 2026 (Week 15)

Activities:
- Simulate collusion, Sybil, and reward manipulation scenarios
- Stress test under participant load
- Validate scoring robustness against coordinated malicious validators

Deliverables:
- Security testing report
- Exploit analysis and mitigations

**WP 6.3: Audits, Optimisation, and Documentation**  
**Duration:** August 17, 2026 to August 30, 2026 (Week 16)

Activities:
- Conduct smart contract audits
- Optimise gas usage and prepare for L2 readiness
- Publish complete protocol documentation

Deliverables:
- Audit report
- Gas optimisation report
- Complete documentation:
  - Staking and withdrawal guide
  - Slashing rules and known failure modes
  - Validator operator guide
  - Tokenomics and protocol paper

### Phase Outcome

By the end of P3, DIN has a functional cryptoeconomic layer with enforceable incentives, accountable validator behaviour, BlockFLow-compatible contribution scoring that operates entirely on model updates without sample access, stronger Sybil resistance, and a hardened testnet foundation suitable for ecosystem expansion.

---

## P4: Daemon and Agentic AI Layer

**Timeline:** September 1, 2026 to November 30, 2026  
**Duration:** ~13 weeks

### Goal

Build `dind`, the DIN daemon, as an always-on agentic execution layer that automates network participation across clients, validators, evaluators, and model owners. This phase turns DIN into a more self-operating decentralised AI network with context-aware task selection and resource-aware orchestration.

### Phase Goals

**Near-term (Weeks 1–4, September 2026)**

- Daemon core architecture: event loop, job scheduler, persistent state, and recovery
- HTTP `/health` endpoint for monitoring daemon and validator readiness
- Structured stdout logs suitable for container and service-manager collection
- `systemd` and `launchd` unit examples for clean restarts
- Network isolation guidance for validator containers and task-execution sandboxes
- CLI-to-daemon integration via shared SDK extraction
- Preference and capability engine: hardware detection, capability scoring, compatibility filters

**Short-term (Weeks 5–9, October 2026)**

- Intelligent task matching: on-chain and IPFS task discovery, local indexing, ranking heuristics
- Automation engine: training pipeline, aggregation automation, auditor automation
- Model owner assistant: deployment tooling, IPFS automation, CLI monitoring dashboard

**Long-term (Weeks 10–13, November 2026)**

- Task summaries and historical performance insights
- Networking and coordination: on-chain event listening, trigger-based execution, optional peer coordination
- Security and privacy layer: sandboxed execution, passphrase-protected keystores, data isolation
- Devnet integration, multi-role simulation, and public release as `dind v1.0.0`

---

### Topics and Milestones

#### 1. Daemon Core Architecture

Create the long-running daemon foundation that can operate reliably across roles with scheduling, persistence, recovery, and reusable shared integrations.

**Focus areas**
- Background worker and event loop design
- Event-based and cron-based scheduling
- Job queue system
- Persistent state and recovery
- Graceful `SIGTERM` and shutdown handling to avoid local state corruption
- Structured stdout logs suitable for container and service-manager collection
- Basic HTTP `/health` endpoint for monitoring daemon and validator readiness
- `systemd` and `launchd` unit examples for clean restarts
- Shared SDK extraction from CLI components
- CLI-to-daemon integration

**Target window:** September 2026

**WP 1.1: Daemon Framework (dind)**  
**Duration:** September 1, 2026 to September 6, 2026 (Week 1)

Activities:
- Design daemon process architecture
- Implement event loop and job scheduler
- Build job queue system
- Implement structured logging and state persistence
- Enable graceful `SIGTERM` and recovery
- Add HTTP `/health` endpoint
- Provide `systemd` and `launchd` unit examples

Deliverables:
- Core daemon service (`dind v0`)
- Scheduler and job queue module
- Logging and persistence system
- HTTP `/health` endpoint
- `systemd`/`launchd` unit examples

**WP 1.2: CLI Integration Layer**  
**Duration:** September 7, 2026 to September 13, 2026 (Week 2)

Activities:
- Extract reusable modules from CLI (IPFS, contracts, wallet)
- Build shared SDK
- Refactor CLI into library mode
- Integrate CLI with daemon
- Document network isolation guidance for validator containers and task-execution sandboxes

Deliverables:
- Shared SDK layer
- CLI-library integration module
- Integration test suite
- Network isolation documentation

---

#### 2. Preference and Capability Engine

Enable context-aware participation by allowing the daemon to reason about user preferences, hardware capacity, privacy constraints, and network suitability.

**Focus areas**
- Preference schema and local configuration storage
- Preference update APIs
- Synchronisation between CLI and daemon settings
- Hardware detection for CPU, GPU, RAM, storage, and network
- Capability scoring
- Compatibility filters for task selection

**Target window:** Mid-September 2026

**WP 2.1: User Preference System**  
**Duration:** September 14, 2026 to September 18, 2026 (Week 3)

Activities:
- Design preference schema
- Implement local config storage
- Build preference update APIs
- Sync CLI and daemon preferences

Deliverables:
- Preference management module
- Config schema and storage system

**WP 2.2: Resource and Capability Detection**  
**Duration:** September 14, 2026 to September 18, 2026 (Week 3)

Activities:
- Detect hardware (CPU, GPU, RAM, storage, network)
- Implement capability scoring
- Build compatibility filters

Deliverables:
- Resource detection module
- Capability scoring system

---

#### 3. Intelligent Task Matching

Build the discovery and recommendation systems that identify which tasks are available, feasible, and worthwhile for a given node to execute.

**Focus areas**
- On-chain and IPFS task discovery
- Local indexing and caching
- Matching based on local data, compute, and expected rewards
- Ranking heuristics
- Task summaries
- Recommended, active, and potential task views

**Target window:** Late September to early October 2026

**WP 3.1: Task Discovery**  
**Duration:** September 21, 2026 to September 25, 2026 (Week 4)

Activities:
- Integrate contract queries
- Fetch available tasks from chain and IPFS
- Implement filtering and indexing
- Maintain local cache

Deliverables:
- Task discovery module
- Indexed task cache

**WP 3.2: Task Recommendation Engine**  
**Duration:** September 28, 2026 to October 2, 2026 (Week 5)

Activities:
- Design matching algorithm (local data, compute capacity, expected rewards)
- Implement ranking system
- Generate task summaries

Deliverables:
- Task recommendation engine
- Ranking and scoring heuristics
- Task summary outputs

---

#### 4. Automation Engine

Automate the full participation lifecycle across multiple DIN roles, reducing manual coordination and making continuous network participation practical.

**Focus areas**
- Automated model fetching and training
- IPFS upload and submission handling
- Retry and failure recovery
- Update fetching and aggregation automation
- Batch processing and attestation generation
- Evaluation automation and score submission
- Multi-role execution for client, validator, and auditor workflows

**Target window:** October 2026

**WP 4.1: Client Automation**  
**Duration:** October 5, 2026 to October 9, 2026 (Week 6)

Activities:
- Integrate training pipeline
- Automate model fetching and training
- Implement IPFS upload and CID submission
- Add retry and failure handling

Deliverables:
- Automated training pipeline
- Submission automation module

**WP 4.2: Aggregator Automation**  
**Duration:** October 12, 2026 to October 16, 2026 (Week 7)

Activities:
- Automate update fetching and aggregation
- Implement batch processing
- Generate result hashes and attestations

Deliverables:
- Aggregation automation module
- Attestation and submission system

**WP 4.3: Auditor Automation**  
**Duration:** October 12, 2026 to October 16, 2026 (Week 7)

Activities:
- Implement evaluation pipeline
- Compute performance metrics using BlockFLow scoring
- Submit scores with consistency checks

Deliverables:
- Evaluation automation module
- Scoring submission system

---

#### 5. Model Owner Assistant

Support model owners with tools that streamline deployment, registration, monitoring, and operational oversight of training activity.

**Focus areas**
- Model packaging tools
- IPFS upload automation
- Contract interaction workflows
- Genesis and deployment setup
- Training monitoring dashboard in CLI
- Metrics aggregation and alerting

**Target window:** Late October 2026

**WP 5.1: Model Deployment Helper**  
**Duration:** October 19, 2026 to October 23, 2026 (Week 8)

Activities:
- Build model packaging tools
- Automate IPFS upload
- Integrate contract interactions
- Implement genesis setup flow

Deliverables:
- Model deployment toolkit
- IPFS and contract automation module

**WP 5.2: Training Monitoring Dashboard (CLI)**  
**Duration:** October 26, 2026 to October 30, 2026 (Week 9)

Activities:
- Track participants and rounds
- Aggregate metrics
- Display CLI dashboard
- Implement alerts

Deliverables:
- CLI monitoring dashboard
- Metrics aggregation module

---

#### 6. Task Summaries and Performance Insights

Provide visibility into historical participation, earnings, and optimisation opportunities so operators can make better decisions over time.

**Focus areas**
- Task summary generation
- Ranking outputs
- Historical earnings and contribution tracking
- Analytics and performance insights
- CLI and daemon-facing insight displays

**Target window:** Early November 2026

**WP 6.1: Task Summaries**  
**Duration:** November 2, 2026 to November 6, 2026 (Week 10)

Activities:
- Generate task summaries
- Implement ranking outputs
- Display results in CLI and daemon

Deliverables:
- Task summary engine
- Ranking output system

**WP 6.2: Historical Insights**  
**Duration:** November 2, 2026 to November 6, 2026 (Week 10)

Activities:
- Track earnings and contributions
- Build analytics module
- Generate performance insights

Deliverables:
- History tracking system
- Analytics and insights module

---

#### 7. Networking and Coordination

Improve daemon responsiveness and coordination through event-driven execution and optional peer-aware synchronisation.

**Focus areas**
- On-chain event listening
- Trigger-based job execution
- Local state updates
- Optional peer discovery
- Task sharing and state synchronisation across daemons

**Target window:** Mid-November 2026

**WP 7.1: Event Listening Engine**  
**Duration:** November 9, 2026 to November 13, 2026 (Week 11)

Activities:
- Subscribe to on-chain events
- Trigger jobs dynamically
- Update local state

Deliverables:
- Event listener module
- Trigger-based execution system

**WP 7.2: Peer Coordination (Optional)**  
**Duration:** November 9, 2026 to November 13, 2026 (Week 11)

Activities:
- Implement peer discovery
- Enable task sharing
- Sync state across daemons

Deliverables:
- P2P coordination module
- State synchronisation mechanism

---

#### 8. Security and Privacy Controls

Ensure that daemon-based execution remains safe, isolated, and privacy-aware when handling models, data, and credentials.

**Focus areas**
- Sandboxed or containerised execution
- File and data isolation
- Secure key handling
- No plaintext private keys in `.env`; passphrase-protected keystores and future vault-backed setups
- Protection against malicious models
- Network isolation guidance for validator containers and task-execution sandboxes
- Task-level privacy controls
- Data sensitivity filters
- Participation policy enforcement

**Target window:** Mid to late November 2026

**WP 8.1: Secure Execution**  
**Duration:** November 16, 2026 to November 20, 2026 (Week 12)

Activities:
- Implement sandbox or container execution
- Ensure file and data isolation
- Harden key handling
- Protect against malicious models

Deliverables:
- Secure execution environment
- Isolation and security module

**WP 8.2: Privacy Controls**  
**Duration:** November 16, 2026 to November 20, 2026 (Week 12)

Activities:
- Implement task-level privacy controls
- Add data sensitivity filters
- Enforce participation policies

Deliverables:
- Privacy configuration system
- Policy enforcement module

---

#### 9. Devnet Integration and Public Release

Complete end-to-end integration with earlier DIN phases and prepare the daemon for external adoption.

**Focus areas**
- Integration with P2 and P3 systems
- Multi-role simulations
- Stabilisation and debugging
- Release packaging for binaries and Docker images
- Docker Compose run path with one-command start, stop, and upgrade flows for validator operators
- Installation and usage documentation
- Community onboarding materials

**Target window:** Late November 2026

**WP 9.1: Devnet Integration**  
**Duration:** November 23, 2026 to November 27, 2026 (Week 13)

Activities:
- Integrate daemon with P2 and P3 systems
- Run multi-role simulations
- Debug and stabilise

Deliverables:
- Fully integrated daemon system
- End-to-end test results

**WP 9.2: Daemon Release (v1.0.0)**  
**Duration:** November 23, 2026 to November 27, 2026 (Week 13)

Activities:
- Package binaries and Docker images
- Prepare installation guides
- Publish release notes
- Enable community onboarding

Deliverables:
- `dind v1.0.0` release
- Installation and usage documentation
- Community onboarding materials

### Phase Outcome

By the end of P4, DIN has an operational daemon capable of autonomous task discovery, execution, evaluation, and coordination across roles, significantly improving usability, efficiency, and network participation at scale.
