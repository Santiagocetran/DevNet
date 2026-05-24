# Validator Selection and Capability Matching

## Summary

This issue defines how DIN should move from registration-only validator participation to capability-aware selection and assignment.

Today, when a model opens validator registration:

- any active validator can register as an aggregator
- any active validator can register as an auditor
- batch creation uses the registered pool plus local shuffle logic
- missed work or bad submissions can be slashed

That is acceptable for a lightweight devnet, but it is too weak for production workloads where training, auditing, and aggregation may have very different memory, storage, compute, and bandwidth requirements.

## Why This Matters

Right now DIN mostly treats validator participation as:

- stake check
- registration
- assignment
- slash if work is not completed

That is not enough when task feasibility depends on off-chain hardware and artifact size.

If a node never had enough RAM, disk, or compute to do the assigned work in the first place, slashing is acting as a late punishment for a predictable scheduling failure.

DIN needs a better answer to:

- who is eligible to register
- who is eligible to be assigned
- what resource requirements a model owner can publish
- how a node can verify it is capable before becoming slashable

## Current State

The implemented contracts already support stake-gated registration and slashing:

- `DINTaskCoordinator.registerDINaggregator(...)` only checks that the caller is an active validator
- `DINTaskAuditor.registerDINAuditor(...)` only checks that the caller is an active validator
- `DINTaskCoordinator.autoCreateTier1AndTier2(...)` assigns aggregation batches from the currently active registered pool after shuffling
- `DINTaskAuditor.createAuditorsBatches(...)` assigns audit batches from the currently active registered pool after shuffling
- aggregators are slashed for no submission or non-matching consensus
- auditors are slashed for missing required votes in their assigned batch

What is missing is any notion of:

- validator hardware capability
- validator availability
- task-specific memory or storage requirements
- role-specific assignment constraints
- pre-registration compatibility checks

There is also a direct responsibility mismatch today:

- a registering validator does not know the concrete hardware capability it may need for future assigned work
- the protocol still treats that validator as responsible once it is assigned
- if the assigned work later exceeds the node's real memory, disk, compute, or bandwidth budget, the validator may still end up slashable

Important context:

- current public docs still describe `Model_0` participation as lightweight and not requiring specialized hardware
- the roadmap already points toward a later preference and capability engine with hardware detection and compatibility filters

## The Main Problem

Validator selection currently depends mostly on registration, not on demonstrated fitness for the assigned work.

That creates four distinct risks.

### 1. Registration is not the same as capability

A validator can honestly want to participate and still be unable to execute the assigned task.

More specifically, the validator currently registers without a reliable task-level declaration of the hardware profile it may need later, but the burden of execution still falls on that validator after assignment.

### 2. Batch sizing is blind to workload cost

The current batching logic uses fixed or locally configured counts such as:

- auditors per batch
- models per audit batch
- aggregators per T1 batch
- models per T1 batch

Those counts do not currently adapt to model size, artifact size, or memory pressure.

### 3. Aggregation and auditing have different resource profiles

Auditing may be feasible with serialized evaluation over assigned models.

Aggregation is more demanding because the aggregator often needs all assigned model artifacts or updates in memory at once, especially if the merge strategy is not serialized.

### 4. Slashing happens after assignment, not after capability proof

Today a validator is exposed to slashing once it is assigned and fails to complete the work, even if there was no reliable preflight step to prevent under-capable nodes from entering the assignment set.

## Core Questions This Issue Should Answer

1. How should a model owner calculate and publish the resource requirements for a task?
2. Which requirements are model-known versus participant-local?
3. How should auditors and aggregators declare their capability before registration?
4. How should clients determine whether they can train locally before joining a task?
5. Should registration itself be blocked when a node is incompatible, or should only assignment be filtered?
6. At what point should a node become slashable: on registration, on assignment, or only after explicit acceptance of the assignment?

## What A Model Owner Can Actually Know

A model owner cannot know every required input directly.

Some inputs are known by the model owner:

- model architecture size
- expected artifact size limits
- training recipe and recommended batch size
- audit-batch size
- T1 and T2 aggregation batch sizes
- whether evaluation is serialized
- whether aggregation requires all assigned models in memory
- test dataset size or shard size for auditors

Some inputs are private or local to the participant:

- client dataset size
- client storage layout
- available RAM
- available disk
- CPU and GPU characteristics
- network bandwidth
- whether the machine is already busy with other work

That means the model owner cannot compute a full feasibility decision alone.

The correct design is:

- the model owner publishes a machine-readable workload specification
- the participant combines that with local hardware and local data facts
- DIN only allows registration or assignment once the compatibility check passes

## Role-Specific Requirement Model

### Clients

For clients, total workload depends partly on private local data, so the model owner should publish a training cost model rather than a single universal requirement.

Important factors:

- local dataset size
- example size and preprocessing cost
- model size
- training epochs
- local batch size
- optimizer and precision mode
- output artifact size

The model owner can publish:

- recommended minimum RAM
- recommended minimum disk
- expected runtime class
- expected output artifact size
- whether GPU is optional or required
- a cost formula that scales with local dataset size

The client should then evaluate:

- whether the local dataset is too large for the configured training recipe
- whether enough disk exists for dataset, environment, checkpoints, and upload artifacts
- whether enough RAM exists for the model plus dataloader plus temporary buffers

Important note:

- clients are not the main slashing surface in the current contracts
- but they still need the same compatibility logic for reliable participation

### Auditors

Auditor work is usually more predictable because the model owner controls:

- number of models per audit batch
- test dataset shard size
- evaluation procedure
- whether scoring can be serialized one model at a time

Important factors:

- number of local models in the audit batch
- size of each model artifact
- size of the test dataset shard
- whether evaluation is serialized or parallel
- score-computation cost

For a serialized auditor path, peak RAM may be close to:

- one model artifact
- one evaluation dataset shard
- one inference workspace

For a parallel auditor path, peak RAM grows with concurrent model evaluations.

The model owner should publish:

- `auditorsPerBatch`
- `modelsPerBatch`
- `maxModelArtifactBytes`
- `testDatasetBytes`
- `serializedEvaluation = true/false`
- `minRamBytes`
- `minDiskBytes`
- `estimatedCpuClass` or `estimatedGpuClass`
- expected wall-clock budget per batch

### Aggregators

Aggregators are the highest-risk role for capability mismatch.

Important factors:

- number of local models in a T1 batch
- size of each local model artifact or update
- number of T1 outputs in T2
- merge algorithm
- whether the aggregator can stream or serialize inputs
- whether all assigned models must be loaded into memory together

In the current architecture, aggregation is the role most likely to need all assigned inputs available in memory at once.

That means peak memory can scale roughly with:

- number of assigned models
- maximum artifact size per model
- merge workspace overhead

The model owner should publish:

- `t1ModelsPerBatch`
- `t2InputsPerBatch`
- `maxModelArtifactBytes`
- `requiresFullInMemoryAggregation = true/false`
- `estimatedAggregatorWorkspaceBytes`
- `minRamBytes`
- `minDiskBytes`
- expected download volume
- expected time budget

## Recommended Architecture

### 1. Publish a task capability spec

Each task or model should expose a machine-readable capability document, ideally through manifest-linked IPFS metadata.

This should be future-oriented rather than just human-readable prose. The manifest should become the canonical place where a model owner publishes role-specific hardware and workload requirements in a structured format that tools can consume automatically.

This spec should include:

- role-specific requirements for client, auditor, and aggregator
- static model facts
- batch sizing parameters
- artifact size limits
- serialization assumptions
- deadline assumptions
- version number and hash

This spec should be referenced by the on-chain task or manifest flow, but the detailed data should stay off-chain.

In the longer-term DIN architecture, the DIN daemon should be able to:

- read the manifest capability spec
- inspect the local node's hardware profile
- determine whether the node is compatible with the role
- register on the validator's behalf only when the capability match passes

### 2. Add participant capability profiles

Validators and clients should publish or locally maintain capability profiles such as:

- RAM
- disk
- CPU class
- GPU/VRAM
- bandwidth
- supported roles
- max artifact size supported
- max concurrent tasks

For `v1`, this can start as self-reported metadata plus local CLI or daemon checks.

DIN should not wait for perfect trustless hardware proofs before adding capability-aware selection.

### 3. Run pre-registration compatibility checks

Before a node registers for a role, the CLI or daemon should compare:

- task capability spec
- participant hardware profile
- participant local data facts

If the node does not meet the requirement, the tool should refuse registration or warn strongly and require explicit override.

For the future daemon path, this same check should gate automated registration so DIN does not auto-enroll validators into slashable work they were never capable of performing.

### 4. Separate registration from assignment eligibility

Registration should not automatically mean "safe to assign."

The selection engine should filter by:

- active validator status
- role opt-in
- capability match
- availability
- stake
- optional reputation or historical reliability

Then it should randomize or rotate only within the compatible subset.

### 5. Add assignment acceptance before slashing

The safest flow is:

1. node registers as interested for a role
2. DIN or the model owner computes candidate assignments
3. assigned node receives the concrete batch description
4. node explicitly accepts within a deadline after local preflight
5. only then does the node become fully slashable for that assignment

This is important because a node may satisfy general role requirements but still fail a specific batch due to:

- unexpectedly large artifacts
- temporary disk exhaustion
- connectivity problems
- concurrent local workloads

### 6. Use slashing for dishonesty or post-acceptance failure

Slashing should mainly cover:

- accepting an assignment and then failing to execute
- malicious submission
- repeated false capability advertisement
- intentional no-show behavior

It should not be the first-line tool for filtering obvious hardware mismatch.

## Suggested Requirement Fields

A first useful requirement schema could include:

- `role`
- `specVersion`
- `minRamBytes`
- `minDiskBytes`
- `minCpuCores`
- `gpuRequired`
- `minVramBytes`
- `maxModelArtifactBytes`
- `maxBatchArtifactBytes`
- `expectedDownloadBytes`
- `expectedUploadBytes`
- `serializedProcessing`
- `estimatedWallClockSeconds`
- `deadlineSeconds`
- `requiresPersistentStorage`
- `supportsStreaming`

Role-specific extensions:

- clients: `recommendedDatasetShardLimit`, `epochs`, `trainBatchSize`
- auditors: `modelsPerBatch`, `testDatasetBytes`, `minScoreQuorum`
- aggregators: `t1ModelsPerBatch`, `t2InputsPerBatch`, `requiresFullInMemoryAggregation`

## What Should Happen Before Registration

### Client flow

1. Load task capability spec.
2. Detect local hardware and local dataset size.
3. Estimate peak RAM, disk, and runtime for the local dataset.
4. Participate only if the node passes local policy.

### Auditor flow

1. Load auditor requirement spec.
2. Detect local hardware.
3. Verify that batch evaluation fits RAM, disk, and time budget.
4. Register only if the node can satisfy the declared batch profile.

### Aggregator flow

1. Load aggregator requirement spec.
2. Detect local hardware.
3. Verify that assigned model artifacts can fit in memory and on disk.
4. Register only if the node can satisfy worst-case T1 or T2 workload.

## Minimum `v1` Scope

The first production-worthy version does not need full on-chain scheduling.

A realistic `v1` could include:

- manifest-linked capability spec for each model or task
- local CLI or daemon hardware detection
- local pre-registration feasibility checks
- role-specific registration opt-ins
- assignment filtering based on declared compatibility
- assignment acceptance before full slashing exposure

This would already be a major improvement over registration-only selection.

## Relationship To The Roadmap

This issue is a concrete precursor to the roadmap's later work on:

- hardware detection
- capability scoring
- compatibility filters
- intelligent task matching

The difference is that this issue focuses on the validator and task-assignment layer first, because validator failure is already tied to slashing.

## Bottom Line

DIN should not rely on "register first, slash later" as its long-term validator-selection policy.

Model owners need a way to publish workload requirements.
Validators need a way to advertise and verify role capability before assignment.
Clients need the same compatibility logic for training feasibility even if they are not slashable today.

The right direction is capability-aware selection:

- publish workload specs
- run preflight checks locally
- filter assignment by compatibility
- require explicit acceptance before slashable work begins
