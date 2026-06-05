# DIN Roadmap

## P3: Cryptoeconomic Layer and Network Hardening

**Timeline:** May 1, 2026 to August 30, 2026  
**Duration:** ~16 weeks

### Goal

Deliver the economic, governance, and security foundations required to make DIN testnet-ready. This phase introduces staking, slashing, rewards, scoring, tokenomics, fee flows, DAO-governed protocol controls, and stronger network-level security guarantees.

### Topics and Milestones

#### 1. Staking Infrastructure

Build the validator staking layer that enables economic commitment, stake-weighted participation, and configurable validator selection across subgroups.

**Focus areas**
- Validator staking contracts
- Deposit, withdrawal, and lock-period logic
- Two-phase validator exits with enforced unbonding windows
- Pending-withdrawal slashability until exit finalization
- Minimum stake thresholds
- Validator registry integration
- Randomized validator selection
- Validator rotation and subgroup assignment
- Validator-to-participant ratio enforcement

**Target window:** May 2026

**Execution flow**
- Validators stake tokens to participate in aggregation and evaluation
- Staking acts as an economic reliability signal
- Participation is stake-weighted where subgroup policies require it
- Validator selection is dynamic per subgroup rather than globally static
- Minimum stake thresholds and validator-to-participant ratios gate assignment

**Work packages**

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
- Implement randomized validator selection
- Design subgroup assignment logic
- Implement validator rotation
- Define validator-to-participant ratio

Deliverables:
- Validator selection engine
- Rotation mechanism
- Fairness testing report

#### 2. Differential Privacy and Contribution Scoring

Implement and validate the core mechanisms used to evaluate contributions while balancing privacy, accuracy, and performance across the network.

**Focus areas**
- Baseline differential privacy integration
- Noise injection strategies
- Privacy versus model performance evaluation
- Median-based contribution scoring
- Shapley-value approximation
- Benchmarking scoring cost versus accuracy
- Validator ratio tuning across different network conditions

**Target window:** May 2026

#### 3. Reward Distribution

Introduce contribution-aligned incentives for participants and validators, with distribution logic tied to measurable model impact and protocol activity.

**Focus areas**
- Contribution-weighted participant rewards
- Aggregation and evaluation rewards for validators
- Reward split logic
- Fee-based validator incentives
- Reward claims, payout automation, and tracking
- Anti-free-rider protections

**Target window:** June 2026

#### 4. Slashing and Fault Attribution

Define and enforce accountability mechanisms for invalid aggregation, incorrect evaluation, and inactivity, supported by deterministic verification and dispute handling.

**Focus areas**
- Slashing rules and deviation thresholds
- Partial and full penalty models
- Slashability across active stake and unbonding stake
- Penalty redistribution
- On-chain and off-chain dispute triggers
- Re-execution and consensus mismatch checks
- Re-evaluation and validator reassignment workflows
- Public documentation for slashing rules, known validator failure modes, and operator-safe recovery steps

**Target window:** Late June to mid July 2026

#### 5. Tokenomics and Fee Layer

Establish the protocol’s economic backbone, including token utility, emission strategy, treasury design, and fee routing between model owners, validators, and the protocol treasury.

**Focus areas**
- Token utility for staking, rewards, and settlement
- Incentive loop design
- Emission and distribution model
- Inflation versus sustainability modeling
- Treasury allocation
- Protocol fee structure and routing
- Dynamic fee logic

**Target window:** Mid July to early August 2026

#### 6. Security, Integration, and Testnet Readiness

Harden the full system through integration testing, adversarial validation, optimization work, and audit preparation to support broader ecosystem rollout.

**Focus areas**
- Devnet integration of all P3 components
- Production-grade staking hardening, including delayed withdrawals and post-service penalty windows
- Validator operator readiness checklist covering key handling, resource ceilings, restart behavior, and monitoring basics
- Contract upgrade flows
- End-to-end integration testing
- Collusion, Sybil, and reward manipulation simulations
- Stress testing
- Smart contract audits
- Gas optimization and L2 readiness
- Public-facing documentation for staking, slashing, validators, and tokenomics

**Target window:** August 2026

### Phase Outcome

By the end of P3, DIN should have a functional cryptoeconomic layer with enforceable incentives, accountable validator behavior, stronger Sybil resistance, and a hardened testnet foundation suitable for ecosystem expansion.

---

## P4: Daemon and Agentic AI Layer

**Timeline:** September 1, 2026 to November 30, 2026  
**Duration:** ~13 weeks

### Goal

Build `dind`, the DIN daemon, as an always-on agentic execution layer that automates network participation across clients, validators, evaluators, and model owners. This phase turns DIN into a more self-operating decentralized AI network with context-aware task selection and resource-aware orchestration.

### Topics and Milestones

#### 1. Daemon Core Architecture

Create the long-running daemon foundation that can operate reliably across roles with scheduling, persistence, recovery, and reusable shared integrations.

**Focus areas**
- Background worker and event loop design
- Event-based and cron-based scheduling
- Job queue system
- Persistent state and recovery
- Logging and restart handling
- Graceful `SIGTERM` and shutdown handling to avoid local state corruption
- Structured stdout logs suitable for container and service-manager collection
- Shared SDK extraction from CLI components
- CLI-to-daemon integration

**Target window:** September 2026

#### 2. Preference and Capability Engine

Enable context-aware participation by allowing the daemon to reason about user preferences, hardware capacity, privacy constraints, and network suitability.

**Focus areas**
- Preference schema and local configuration storage
- Preference update APIs
- Synchronization between CLI and daemon settings
- Hardware detection for CPU, GPU, RAM, storage, and network
- Capability scoring
- Compatibility filters for task selection

**Target window:** Mid September 2026

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

#### 6. Task Summaries and Performance Insights

Provide visibility into historical participation, earnings, and optimization opportunities so operators can make better decisions over time.

**Focus areas**
- Task summary generation
- Ranking outputs
- Historical earnings and contribution tracking
- Analytics and performance insights
- CLI and daemon-facing insight displays

**Target window:** Early November 2026

#### 7. Networking and Coordination

Improve daemon responsiveness and coordination through event-driven execution and optional peer-aware synchronization.

**Focus areas**
- On-chain event listening
- Trigger-based job execution
- Local state updates
- Optional peer discovery
- Task sharing and state synchronization across daemons

**Target window:** Mid November 2026

#### 8. Security and Privacy Controls

Ensure that daemon-based execution remains safe, isolated, and privacy-aware when handling models, data, and credentials.

**Focus areas**
- Sandboxed or containerized execution
- File and data isolation
- Secure key handling
- No plaintext private keys in `.env`; support passphrase-protected keystores and future vault-backed setups
- Protection against malicious models
- Network isolation guidance for validator containers and task-execution sandboxes
- Task-level privacy controls
- Data sensitivity filters
- Participation policy enforcement

**Target window:** Mid to late November 2026

#### 9. Devnet Integration and Public Release

Complete end-to-end integration with earlier DIN phases and prepare the daemon for external adoption.

**Focus areas**
- Integration with P2 and P3 systems
- Multi-role simulations
- Stabilization and debugging
- Release packaging for binaries and Docker images
- Docker Compose run path with one-command start, stop, and upgrade flows for validator operators
- Basic HTTP `/health` endpoint for monitoring daemon and validator readiness
- `systemd` and `launchd` unit examples for clean restarts
- Installation and usage documentation
- Community onboarding materials

**Target window:** Late November 2026

### Phase Outcome

By the end of P4, DIN should have an operational daemon capable of autonomous task discovery, execution, evaluation, and coordination across roles, significantly improving usability, efficiency, and network participation at scale.
