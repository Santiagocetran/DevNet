# Containerization and Sandboxed Execution

## Summary

This issue covers how DIN should containerize `dincli` and isolate execution of model-owner supplied service code and protect auditors, aggregators from malicious local models.

The roadmap already calls out:

- sandboxed or containerized execution
- file and data isolation
- secure key handling
- protection against malicious models
- release packaging for Docker images

This is important because model owners can submit manifests that include Python service scripts. Those scripts are later downloaded and executed by clients, aggregators, and auditors. A malicious model owner could include code that attempts to:

- read local files, wallets, API keys, or datasets
- exfiltrate private training data
- modify local DIN cache or manifests
- manipulate training, aggregation, or evaluation behavior
- consume excessive CPU, RAM, GPU, disk, or network resources
- persist malware on participant machines

Similarly, aggregators and auditors may need to work with submitted models or model artifacts that could be malicious, malformed, or intentionally resource-exhausting.

Containerization is one practical mitigation, but it increases RAM, storage, compute cost, operational complexity, and development time. DIN should treat this as a required security direction, but implement it in phases.

## Why This Matters

DIN execution is decentralized, but that also means untrusted participants may cause other participants to execute untrusted code or load untrusted artifacts.

Without isolation:

- clients may run malicious model-owner training services on machines containing private data
- aggregators may run malicious aggregation logic or load malicious updates
- auditors may run malicious evaluation logic or inspect hostile submitted models
- node operators must trust model owners far more than the protocol should require
- one bad task can compromise a participant's whole machine

The long-term goal is that participating in DIN should not require giving arbitrary model-owner code full access to the host system.

## Current State

Today, parts of the CLI can load task-specific service code from manifests and execute Python functions locally.

Examples include workflows where the model owner provides or controls service scripts for:

- client local model training and IPFS upload
- aggregator logic
- auditor scoring and evaluation logic
- model architecture and task-specific helpers

The CLI currently runs these inside the same Python process as `dincli`. That means the loaded code can potentially access the same filesystem, environment variables, Python process memory, network access, and user credentials that `dincli` can access.

This is acceptable for early devnet development, but it is not acceptable as a production security model.

## Threat Model

DIN should assume that a submitted task, manifest, service script, model artifact, or model update may be malicious.

Important threats include:

- arbitrary code execution through Python service scripts
- data exfiltration from local datasets or cache directories
- wallet or private key theft
- poisoning local task state
- tampering with outputs before submission
- denial of service through large models, memory pressure, disk writes, or infinite loops
- dependency confusion or malicious package installation
- GPU abuse or excessive compute use
- network scanning or unexpected outbound connections

Containerization does not solve every issue, but it can reduce the blast radius when combined with least-privilege mounts, resource limits, and explicit I/O contracts.

## Role-Specific Isolation Needs

### Clients

Clients are the highest privacy-risk role because they may train on private local data.

Client containers should:

- mount only the task input data that the user explicitly allows
- mount a task-specific cache directory, not the full DIN cache
- avoid mounting wallet files or global config directly
- receive only the minimum network and contract context needed for the job
- write outputs to a controlled output directory
- support CPU-only and GPU-enabled execution profiles

### Aggregators

Aggregators process submitted updates and may run aggregation services or load submitted model artifacts.

Aggregator containers should:

- isolate downloaded model updates from the host filesystem
- apply CPU, RAM, disk, and timeout limits
- avoid access to wallet material during untrusted aggregation logic
- produce deterministic output artifacts that the host process can inspect and submit
- separate untrusted aggregation computation from trusted transaction signing

### Auditors

Auditors may evaluate submitted models, run scoring code, and inspect artifacts from clients or model owners.

Auditor containers should:

- isolate evaluation datasets from unrelated local files
- run submitted models with strict resource limits
- protect audit keys and wallet state from evaluation code
- capture logs and metrics for dispute/debug workflows
- support deterministic re-execution where possible

## Required Capabilities

At minimum, DIN needs a container execution layer that can:

- run task-specific service code outside the main `dincli` process
- define explicit input, output, cache, and artifact directories
- mount files read-only by default
- keep wallet files, private keys, and global config outside untrusted containers
- avoid plaintext private keys in `.env`; use passphrase-protected keystores, host-side signing, or future vault-backed integrations
- pass required runtime metadata through a structured file or environment contract
- enforce CPU, RAM, disk, process, and timeout limits
- document expected and maximum resource ceilings for each role
- optionally restrict network access
- support GPU access only when explicitly enabled
- capture stdout, stderr, exit code, resource usage, and output artifacts
- clean up temporary containers and volumes
- work from both CLI commands and future `dind` daemon jobs
- handle graceful stop signals so containers can exit without corrupting local state or partial outputs

## Docker Packaging Requirements

DIN should support at least two Docker image categories.

### 1. Trusted DIN Runtime Images

These are official images maintained by DIN.

Examples:

- `dincli` base image
- client runtime image
- aggregator runtime image
- auditor runtime image
- GPU-enabled variants where needed

These images should include:

- Docker Compose examples for one-command start, stop, upgrade, and log inspection
- pinned Python version
- pinned `dincli` version
- required ML/runtime dependencies
- non-root default user
- minimal OS packages
- reproducible build process
- image version tags tied to DIN releases
- documented RAM, CPU, disk, network, and optional GPU expectations
- healthcheck definitions where the image runs a long-lived daemon or validator service

### 2. Task Execution Images

These are images or runtime environments used to execute task-specific code.

Possible approaches:

- use a DIN-maintained base image and mount downloaded service scripts into it
- allow model owners to specify an image digest in the manifest after governance or allowlist approval
- build per-task images from a restricted manifest format

For devnet, the safest first step is a DIN-maintained base image with mounted service scripts and strict runtime limits.

## Manifest and Runtime Requirements

Manifests may eventually need fields for container execution policy.

Possible fields:

- required runtime type: local, docker, or wasm later
- Python version or runtime profile
- dependency list or approved image digest
- CPU and RAM minimums
- optional GPU requirement
- maximum disk usage
- maximum execution time
- network access requirement
- expected input and output paths
- deterministic execution flag

These fields should be validated before a node accepts a task.

Important default:

- untrusted task code should not receive wallet access
- trusted host code should remain responsible for transaction signing and final submission

## Architecture Direction

The clean separation should be:

- host `dincli` or `dind` handles wallet, network, contracts, task selection, and final submissions
- containerized worker handles untrusted task computation
- host passes inputs through controlled mounts or serialized job files
- worker writes outputs to a controlled output directory
- host validates outputs before uploading to IPFS or submitting transactions

This means untrusted code should compute artifacts, scores, or model outputs, but should not directly sign transactions or freely call host-side DIN APIs.

## Cost and Complexity Tradeoffs

Containerization improves safety but creates real costs.

Expected costs:

- higher RAM usage due to duplicated runtime environments
- higher storage usage from Docker images, layers, caches, and model artifacts
- slower cold starts
- more complicated GPU support
- more complex developer setup
- CI and release complexity for multi-platform images
- harder debugging for model owners and operators
- more operational support burden

These costs should be documented clearly so node operators can choose appropriate hardware and execution profiles.

## Phased Implementation

### Phase 1: Local Docker Worker Prototype

- Add an internal container runner abstraction.
- Run one client training service through Docker with controlled input/output mounts.
- Keep transaction signing and IPFS submission on the host.
- Add CPU, RAM, timeout, and read-only mount controls.
- Document local Docker requirements and minimum resource ceilings.
- Add Docker Compose examples for start, stop, upgrade, and log collection.

### Phase 2: Role Coverage

- Extend the worker flow to aggregator services.
- Extend the worker flow to auditor evaluation/scoring services.
- Add role-specific runtime profiles.
- Add structured job input and output schemas.
- Add logs and error reporting that are usable from CLI and daemon flows.

### Phase 3: Manifest Policy

- Add manifest fields for runtime requirements and limits.
- Validate requirements before accepting or executing a task.
- Add user policy controls for whether a node accepts Docker-required, GPU-required, or network-enabled tasks.
- Add clear rejection messages when local hardware or policy does not match.

### Phase 4: Hardened Execution

- Add stronger network isolation and explicit outbound access policy.
- Add non-root containers by default.
- Add seccomp/AppArmor profiles where practical.
- Add disk quotas and cleanup policies.
- Add image digest pinning and allowlist policy.
- Add reproducible official DIN runtime images.

### Phase 5: Daemon Integration

- Use the same container runner from `dind`.
- Add scheduling based on hardware capability and resource availability.
- Track resource usage per task.
- Add retry and recovery behavior for failed containers.
- Support long-running node operation without cache or container buildup.

## Open Questions

- Should Docker be required for all untrusted task execution, or optional during devnet?
- Should DIN support Podman or another rootless runtime in addition to Docker?
- Should model owners be allowed to specify custom images, or only DIN-approved base images?
- How much network access should task containers receive by default?
- How should GPU access be requested, validated, and limited?
- What manifest fields are required for v1 versus later phases?
- Should execution eventually move toward WASM or another stronger sandbox for some workloads?

## Recommended Near-Term Decision

For devnet, DIN should make Docker-based sandboxing optional but strongly recommended.

The first implementation should:

- use official DIN-maintained runtime images
- run untrusted service code in a container
- keep wallet and transaction signing on the host
- enforce basic CPU, RAM, timeout, and filesystem isolation
- support clients first, then aggregators and auditors

This gives DIN a practical path toward safer execution without blocking current development on a fully hardened production sandbox.
