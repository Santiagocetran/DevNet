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

### Still to Do 

Migration to Foundry


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


# Discussion


Step 1: Devnet - remaining protocol elements. (Interns to execute)
Step 2: Testnet - how do we achieve, and what do we need to get there.

Advanced Testnet - economics of staking.

net profit of staking and computation resources of validators

Apply a network fee in the testnet - using dummy ETH

Advanced Testnet - economics of staking.

If this is something that Robbert and you come onto, use a dummy fee. Set to something reasonable or explore solutions
Finalize all economics toward advanced testing





Edge City requirements have been met — the funds have been released to us in full.

And thanks for this - perhaps we update it using the below if it is helpful?)
We also previously created a Google Doc here:
 https://docs.google.com/document/d/1t7vC68RtUzPBzn9lySj_TYhxtvgp8s2RTtV6077ar8M/edit?tab=t.0#heading=h.fydl91nws9bi

 An earlier version was shared to keep everything up to date.

From an engineering perspective, auditing and aggregation need to be fully functional across validators (is the basic socring mechanisms implemented? e.g., blockflow,  or substra, or https://github.com/LabeliaLabs/distributed-learning-contributivity - some links and exampels given in the Whitepaper), and we should also take a step back to simplify, fix bugs, and improve documentation before scaling further. We’ll also ask interns to bring in 2–3 validator partners to participate to boost our pool.

What priorities do you see on your side for the next phase? On priorities: slashing, staking, tokenomics, network fees, rewards, scoring, and DAO-governed protocol controls all seem important areas to focus on.

https://github.com/InfiniteZeroFoundation/DevNet/blob/develop/Developer/ROADMAP.md

this is the roadmap but its little stale. to complete edge city requirements, can you clarify what actually we need in writing.

As per my meeting notes at fireflies, since, containerization is done, we should move to tokenization and DAO governance.

but i believe DAO and governance is not the requirement for edge city.

Moreover there is some work based on feedback from advisors/ validators 




Hi Abraham,

Thank you for the follow-up. Glad to be in motion on this.

Before I spin up a node I want to be transparent about the operator-side bar I'm working from, because Venus runs on the same infrastructure that operates Artizen's day-to-day, and the bar has to match that. Going through your setup docs, getting-started guide, and the whitepaper end-to-end before any commit. Strong work on the federated-learning architecture; the Aggregator / Auditor / Client split is clean.

Here is what I would need before I bring a node online. None of this is gatekeeping; these are the same hygiene items any production validator network ends up needing, and getting them in place now will help every validator who comes after me.

 Operational requirements I would treat as blocking
• Containerized run path (Docker / docker-compose, one-command start/stop/upgrade)
• No plaintext private keys in .env (passphrase-prompted keystore or vault-backed; 1Password CLI works)
• Documented resource ceiling (RAM/CPU/disk/network)
• Graceful SIGTERM handling that does not corrupt local state on restart

 Strong preferences (negotiable)
• HTTP /health endpoint for watchdog monitoring
• Structured stdout logs
• Network isolation guidance
• launchd/systemd unit for clean restart
• Slashing rules + known failure modes documented
• Confirmation at least one other validator publicly online before I join





P.S. Feedback from validator:

>Small bug in dincli — it re-approves each time but submits the stake with a stale nonce. The approval already went through, allowance is set. They are setting stake manually




Feedback from developer/validator for us @Umer

Some small notes on installer

- Not obvious how the get the filebase API key (had to create a bucket etc, state this)
- Personally prefer uv so I made some small changes to run like so

```bash
# Check current Global Iteration state
uv run dincli task gi show-state 0

# Explore model info
uv run dincli task explore 0

# Check ETH balance
uv run dincli system --eth-balance

# Connect wallet (if keystore missing)
uv run dincli system connect-wallet --account 0
## Aggregator flow

Only relevant when GI state is DINaggregatorsRegistrationStarted:

uv run dincli aggregator dintoken buy 0.00001
uv run dincli aggregator dintoken stake 10
uv run dincli aggregator register 0
When state reaches T1AggregationStarted:

uv run dincli aggregator show-t1-batches 0 --detailed
uv run dincli aggregator aggregate-t1 0 --submit
Also its not stated what wallets should will be used for; I would guide users to setup a buner wallet explicitlly

https://openwallet.sh/ is dead simple on CLI
OWS - Open Wallet Standard
OWS - Open Wallet Standard
An open standard for secure local wallet storage and agent access. One interface for all chains, all agents, all tools.




Short version: TKNN is the wrong tool for us, and we don't actually need it.

TKNN-Shapley values individual *data samples* — it needs the raw points to score them. Our validators only ever see the model update, not the client's samples, and we've ruled out MPC/TEE/ZKP and any sample disclosure. So there's no way for a validator to run it: the score is a function of the data, and the data never reaches the validator. That's an information-theoretic wall, not an engineering gap. It can only ever live client-side as a curation tool, which doesn't help us.

The good news: for what we actually want right now — detecting poisonous models — none of that matters. Poison detection runs on the model update, which is exactly what our validators already hold.

What to do:
- Our current method (score the update on validation data, reject if it degrades performance) is already a poison detector for the crude attacks — garbage updates, label-flipping, sign-flipping, scaling.
- Harden it with cheap model-space checks: norm bounding (poison updates tend to be abnormally large) + cosine/distance to the consensus/median update (poison points away from where honest clients cluster). Krum or coordinate-wise median formalize this. All on the weights, no crypto, no samples.

One thing to decide — threat model:
- Crude poisoning hurts validation accuracy → val-gating + outlier checks catch it.
- Backdoors don't — a backdoored model keeps normal clean accuracy and only misbehaves on a hidden trigger, so it sails through validation. If backdoors are in scope we'd need model-inspection defenses (activation clustering / spectral signatures / pruning) — still on the model, but more involved.

Which threat are we actually worried about? That decides how far we build detection out.

On rewards — not building it now, but the path is clear and reuses the same machinery. We let the market set the total price (the pool), and distribute it by each client's score weighted by how much their weight update actually improved the global model. So the same number our validators already compute for detection doubles as the reward signal — no extra valuation layer needed. Key detail when we get there: score the *marginal* improvement to the current global model, not the update in isolation, so redundant/duplicate updates earn ~nothing and we get diminishing-returns-on-duplicate-data for free (the one Shapley property worth keeping, without any of the Shapley machinery).

(Footnote: TKNN-Shapley's own benchmark is literally mislabel/noisy-sample detection — so it *is* a poison detector, just one that needs the raw samples. Right idea, wrong layer for us.) (edited) 
[6:31 PM]
Here's the validator-side algorithm. It does both jobs at once — the marginal-gain number is the poison gate and the future reward weight, so there's no separate valuation pass.

python

# Run by each validator, once per round.
# In:  global model M_g, candidate updates {u_1..u_n}, validation set D_val
# Knobs: norm_cap, min_gain (ε), n_perms
def validator_round(M_g, updates, D_val):
    survivors = []
    med_dir = median_direction(updates)        # consensus direction
# 1. Cheap pre-filter — kill obvious poison before any eval
    for i, u in updates:
        if norm(u) > norm_cap:      continue   # scaling attack
        if cos_sim(u, med_dir) < 0: continue   # points against the majority
        survivors.append((i, u))

# 2. Marginal scoring — averaged over a few random orders
    score  = {i: 0 for i, _ in survivors}
    votes  = {i: 0 for i, _ in survivors}
    for _ in range(n_perms):
        M = M_g
        for i, u in shuffle(survivors):
            gain = acc(M ⊕ u, D_val) - acc(M, D_val)   # vs CURRENT model
            if gain > min_gain:        # helps → accept
                score[i] += gain
                votes[i] += 1
                M = M ⊕ u              # fold in → a duplicate now scores ~0
            # gain ≤ min_gain → no help or harmful → poison, dropped
    score = {i: s / n_perms for i, s in score.items()}

accept = {i for i in score if votes[i] > n_perms / 2}
    return accept, score   # score = marginal gain, reused later as reward weight
Then the cross-validator layer (this is what makes "our validators," plural, robust to a malicious validator):



python

final_accept(i) = majority_vote over validators of (i in accept_v)
final_score(i)  = median over validators of score_v[i]        # accepted i only
# when rewards turn on — market sets `pool`:
reward(i) = pool * final_score(i) / sum_j final_score(j)
The pieces that matter:
⊕ is just applying the weight delta. min_gain (ε) is the single dial that does poison detection — anything that doesn't improve the current model is rejected — and the same gain value, normalized, becomes the reward weight. The sequential fold-in (M = M ⊕ u) is what gives you duplicate-data discounting for free: once a good update is in the running model, a copy of it scores ~0. Averaging over n_perms random orders removes the "whoever's evaluated first gets the credit" unfairness — that's literally a few-permutation Monte-Carlo Shapley over the updates. n_perms = 1 is the cheap baseline for detection; bump it only when you turn rewards on and want fairer attribution. median across validators tolerates up to ~half of them being malicious.
Cost is n_perms × n validation passes per validator per round — cheap and fully parallelizable. The one gap to remember: this catches crude poison but not backdoors, since a backdoored update still posts a positive gain on clean validation data.
[6:33 PM]
DP-on-updates is arguably the privacy layer your design was missing. Remember I flagged earlier that raw weight updates leak training data (gradient inversion, membership inference)? DP on the update closes exactly that hole, so "validators only see the model" becomes genuinely private rather than nominally private. The algorithm itself doesn't care — it operates on whatever update arrives, noisy or not.
The clean way to think about the tradeoff: DP has two halves, and they pull in opposite directions for you.
The clipping half (bounding each update to norm C) actually helps robustness — it's the same thing as your norm_cap check, and bounding per-client influence is literally how several poisoning/backdoor defenses work. A malicious client can't move the model much if every update is clipped. So this half is synergistic, not a cost.
The noise half is what degrades detection, and it hits the components unevenly:
• Marginal-gain scoring gets noisier — DP noise adds variance to acc(M ⊕ u). But the gain is a scalar aggregate over many parameters and many validation points, so the zero-mean weight noise largely averages out at the metric level; the effective noise on the score is far smaller than the per-coordinate noise looks. Your n_perms averaging and round-over-round accumulation shrink it further. It survives unless ε is very tight.
• Cosine-to-consensus degrades the most — DP noise and poison both read as "deviation from the majority direction," so the check loses discriminative power. Under strong DP, lean on the gain gate and norm bound, downweight cosine.
• Norm check — fine, even helped, since DP already clips.
• Median across validators — unaffected; it just operates on noisier inputs.
So the real dial is ε. Loose ε → scores and detection stay sharp, weaker privacy. Tight ε → strong privacy, but marginal gains blur toward the noise floor and subtle poison near the threshold becomes uncallable. You tune ε to keep typical gain comfortably above the noise floor — measurable empirically by checking the variance of gain on known-good updates at a candidate ε.
One honest caveat and one bonus. The caveat: combining DP and Byzantine-robustness is a genuinely hard, active research tension — noise that protects privacy also masks malicious deviation, so you can't push both to the extreme for free. The bonus: the clipping that comes with DP is itself a poisoning bound, so strong DP can reduce backdoor effectiveness (no single update can dominate) — which partly offsets the fact that backdoors otherwise slip past the gain gate.
[6:33 PM]
In other words
On privacy — and this is the good part: we can run all of this even with differential privacy applied to the weight updates, and it actually *strengthens* the design. DP on the update closes the gradient-leakage hole that raw weight sharing leaves open, so "validators only see the model" becomes genuinely private. The detection/scoring runs on the noisy updates unchanged. The clipping that comes with DP is synergistic — it's the same norm bound we already use, and it caps how much any single client can move the model, which is a poisoning defense in its own right (it even blunts backdoors). The only real cost is that the added noise blurs the marginal-gain signal slightly, so it's a tunable dial: pick ε loose enough that genuine gains stay above the noise floor. Net — fully doable, with a privacy-vs-sharpness knob we control.
abraham nash  [6:46 PM]
let me think this through - one moment @Umer
[6:47 PM]
Here's the mapping between BlockFLow (MIT, 2020) and our design — it lines up almost point for point:

- Granularity: BlockFLow scores at the model/agent level, not per-sample — the same side of the wall we hit. Confirms per-sample was never the achievable target.
- Privacy: it applies differential privacy directly to the shared model weights (Laplacian noise) — exactly our DP-on-updates step.
- Robustness: it uses a median of scores as its aggregator and tolerates <50% malicious agents — the same principle as our median-across-validators. The only difference is *who* the median runs over: BlockFLow has no validators, so its median is taken over peer evaluations (every agent scores every other), whereas ours is taken over the group of dedicated validators scoring each client. Same robustness principle, different party — and in both cases the median is what bounds a single bad actor's influence.
- Rewards: proportional payout from a pooled bond, paid in crypto — same as our market-pool-weighted-by-score path.
- Detection: malicious models (random data, inverted labels) caught purely by their poor accuracy scores on honest evaluators' data — same mechanism as our marginal-gain / validation gating.

The one piece of theirs we deliberately don't carry over: because their agents evaluate each other, they add a second term — an evaluation-honesty score that caps an agent's payout by how far its scores sit from the median — purely to stop peers from gaming each other. We don't need that. Our clients never evaluate anyone, so a client's reward is just its contribution score, and validator honesty is covered by staking plus the median across validators. Their second score solves a problem our architecture doesn't create. (edited) 
[6:48 PM]
@Umer this seems to work so we can update our roadmap and timing to try implementing this instead for now.

Think it through - let's confirm on todays call
check 64ca3c5f and f11fce22a for WP 3.1 3.2
which is relevant for client and validators rewards but first we need scoring (auditing) for clients on which client rewards rely upon

yeah, I think in this case we can try to replicate and take the approach of blockflow
[6:25 PM]
i.e., apply some median based scoring system for client model contributino, tested against its contribution to updating the global model


Hi @Umer, My thoughts on filebase and filecoin.
I'd appreciate your insights - how would filecoin work in practice? They have funding potentially.



Yes — Filecoin can do this, and it's arguably a stronger fit than Filebase for your use case long term.
What Filecoin offers over Filebase
Filebase is an S3-compatible object storage layer that pins to IPFS — it's centralised infrastructure with an IPFS interface. It works well but Filebase itself is a single point of failure and trust. For a trustless network that's a philosophical tension.
Filecoin is decentralised storage built natively on top of IPFS. Content is stored across a network of independent storage providers with cryptographic proof that data is actually being stored — called Proof of Replication and Proof of Spacetime. No single entity controls it.
For your specific use case
Model weight updates pushed by participants need to survive between training rounds — permanency matters. Filecoin handles this well through storage deals with configurable duration. You pay storage providers in FIL to store content for a defined period, and the network cryptographically verifies they're keeping their end of the deal.
The practical bridge
You don't have to choose immediately. Lighthouse, Web3.Storage, and Storacha all offer Filecoin-backed IPFS pinning with APIs similar to what you're likely using with Filebase now. Migration would be relatively low friction.
One consideration
Filecoin retrieval can be slower than Filebase depending on the provider. For model weights that are written once and read during aggregation rounds that's probably fine — latency on retrieval matters less than permanency and trustlessness.
Worth exploring as a natural next step given your architecture. Want me to draft a technical note comparing the two for your documentation?

I imagine the model_owner will pay for this as a part of the network fee in the future. (edited) 
4 replies

abraham nash  [9:05 PM]
Filecoin storage cost
Filecoin costs approximately $0.19 per TB per month — making it the cheapest decentralised storage option available. For your use case, model weight updates are tiny — typically kilobytes to low megabytes per client update. You are nowhere near TB scale for a long time.
What this means in real numbers
If you have 100 validators each pushing 10MB model updates per training round, that's 1GB per round. At Filecoin's pricing that's roughly $0.0002 per round. Essentially negligible.
How it gets paid via network fee
The flow would be simple. Model owner pays a network fee to initiate a training job. A small portion of that fee — tiny, fractions of a cent per round — is routed automatically to cover Filecoin storage deals for that job's client updates. The smart contract handles the routing. No client ever pays directly.
This fits cleanly into your P3 tokenomics design — the fee mechanism you're already building covers storage as a line item without anyone noticing it exists.
Honest bottom line
Keep Filebase for now — it's free and the storage costs at your current scale are so small they're rounding errors. But when you design the fee mechanism in P3, build Filecoin storage costs in from the start. The numbers are so low they'll never be a meaningful burden on model owners. (edited) 
Umer  [9:08 PM]
Thanks @abraham nash I will explore filecoin and follow on this
Umer  [8:49 PM]
https://manus.im/share/file/48a96a47-403b-436b-b8f1-187af4490d71
manus.im
Filebase vs. Filecoin: A Comparative Analysis for IPFS Uploads - Manus
Manus is the action engine that goes beyond answers to execute tasks, automate workflows, and extend your human reach.

abraham nash  [12:35 AM]
Great summary, @Umer

Pros
• Trustlessness: The decentralized nature and cryptographic proofs ensure that data is stored without relying on a single trusted third party.
• Verifiable Storage: PoRep and PoST provide strong guarantees that data is indeed being stored and is accessible.
• Cost-Effective for Long-Term Storage: Filecoin can be very cost-effective for long-term storage, with costs as low as approximately $0.19 per TB per month 
• Thecost for small updates (e.g., 1GB per round for 100 validators pushing 10MB updates) is negligible, around $0.0002 per round 

Cons
•Retrieval Latency: Retrieval of data from Filecoin can sometimes be slower than from centralized services like Filebase, depending on the storage provider
. However, for data that is written once and read less frequently, this might not be a significant issue.
•Complexity: Integrating directly with Filecoin can be more complex than using an S3-compatible service like Filebase, as it involves managing storage deals and FIL cryptocurrency.

I think because of its decentralized nature, it meets our requirements for fully decentralized system at InfiniteZero!
