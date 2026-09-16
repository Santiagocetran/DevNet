# Audit of the Friday meeting preparation

Audit date: 16 September 2026. Scope: the four documents in this folder, checked against the locally available commits they cite (`5d258e0`, `ab1ba24`, `27885d7`) and the accessible discussion opening post.

**Assessment: useful and readable preparation, but revise before sharing as a verified readiness assessment.** The biggest problem is that the daemon framework is presented as an operational replacement for the role commands. The hardware proposal also needs stronger acceptance criteria, and the promised documentation review is missing.

The original four files were left unchanged. This is a document and source inspection, not an execution test or a full security audit.

## Evidence limits

The accessible [discussion #132](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132) opening post asks for decisions on scope, security, operations, documentation, and exit criteria. Its logistics specify a half-day during the week of September 14; they do not establish Friday's exact time. The fetched page omitted replies. GitHub API access returned a rate-limit error, and attempts to retrieve #139 and the PR pages failed.

Consequently, the A/B/C sections, individual commitments, exact meeting time, current PR draft/review status, and latest answers in #139 remain **unverified here**, not disproved. Add direct comment links or a dated meeting invitation. Local source snapshots establish code facts at those commits, not current remote PR state.

## Findings, in priority order

### 1. High: the proposed operator path exceeds what the daemon implements

**Locations:** `01-node-software-merge-plan.md:17`, `:30`, `:91–101`; `README.md:47–49`.

The proposal asks operators to use the daemon and uses that recommendation to justify deferring interruption safety in CLI commands. At `27885d7`, however, the only registered daemon jobs are `demo` and `read_stake`. There are no registered client-training, auditor, or aggregator jobs. The service framework exists, but this is not yet an automated validator runtime.

Evidence: `dincli/dind/jobs.py:56–68` and its callers at `27885d7`; `Developer/ROADMAP.md` at `5d258e0` separately tracks task discovery and role automation under P4. The first operations-layer task explicitly limits itself to a read-only proof of the pipeline.

**Correction:** say “daemon framework implemented; role automation remains separate.” Ask the meeting to choose a supported operator workflow based on commands that actually run today. If CLI commands remain necessary, assess their interruption and recovery behavior. Do not justify deferring that work merely by having a daemon process running.

### 2. High: the plan closes broader readiness requirements after merging narrower features

**Locations:** `01-node-software-merge-plan.md:33–38`, `:85`.

The table compresses T0.2c into a basic health check and T0.2e into service startup. The pinned roadmap includes RPC reachability, signer availability, and disk thresholds in T0.2c, and network-isolation guidance in T0.2e. The daemon health status at `27885d7` is computed from heartbeat age; returning resource values does not enforce a disk threshold or demonstrate signer/RPC readiness.

Likewise, clean shutdown of the scheduler does not establish safe interruption of real training jobs and workers. T0.2a explicitly asks for active-job interruption/restart checks and Docker stop/down verification. The plan itself acknowledges an unresolved CLI half, yet step 8 closes the whole item.

**Correction:** map every original requirement to implementation evidence, remaining work, and an acceptance check. Close only the completed scope after validation on the integrated commit, or record an explicit meeting-approved reduction in scope. Keep “implemented,” “reviewed,” “merged,” and “validated” separate. Preserve the network-isolation portion of T0.2e.

### 3. High: the hardware method cannot yet support the promised minimums or ceilings

**Locations:** `02-hardware-requirements-proposal.md:48–60`, `:66–83`.

One ordinary Model_0 round is useful initial evidence, but cannot establish maximum demand, sustained disk growth, or dependable completion under deadlines. The proposed table also lacks recommended CPU/disk/network values and explicit maximum supported workload. Bytes transferred per round alone do not determine required bandwidth; the transfer time budget matters.

“Minimum means it works; recommended means it works without missing deadlines” is especially problematic for a protocol that penalizes missed work. A minimum supported machine should meet the specified deadlines under the stated workload. Recommended specifications should provide additional headroom.

**Correction:** label Friday's table as a measurement plan, not validated admission requirements. Specify model/data size, participant and batch counts, concurrent jobs, software version, host configuration, cold versus warm caches, repeated rounds, deadlines, and storage retention. Measure workers as well as the daemon/container host. Define minimum as meeting the agreed workload and deadlines; recommended adds headroom. Identify who measures, when, and where results will be published, including the Compose documentation required by T0.2b.

### 4. Medium: a factual criticism of the existing hardware guide is incorrect

**Location:** `02-hardware-requirements-proposal.md:35–36`.

The document says nothing identifies the existing numbers as Model_0-specific. The pinned getting-started guide is titled “Model_0 — Infinite Zero Network Protocol,” and its system-requirements section explicitly introduces participation in Model_0 immediately before the numbers.

**Correction:** replace this with “The guide scopes these figures to Model_0, but provides no measurement evidence, per-role breakdown, or scaling guidance.” Treat 4 GB and ~30 GB as existing published guidance, not verified client-specific measurements.

### 5. Medium: the key fixes are real, but the security closeout claim is too broad

**Locations:** `03-private-key-fixes.md:16–17`, `:45–57`, `:90–106`.

Both reported defects are confirmed: non-demo `connect-wallet --account` reads `ETH_PRIVATE_KEY_<n>`, and `.env.example` points at the wrong wallet-guide path. The data-distribution helper also reads these environment keys outside demo mode. Its treatment is mentioned but not explicitly included in the acceptance criteria.

However, “two small things are left” and “keystore half ... closed” imply a completed audit of the whole requirement. The source also supports plaintext key-file import and a raw key argument (with a warning). Those may be deliberate migration interfaces, but their policy needs to be stated. Disabling a future import route also does not remove existing plaintext copies.

**Correction:** call these “two confirmed defects,” explicitly scope the helper, and define regression checks: demo account selection still works; real-mode selection fails before reading environment key material; encrypted-keystore and hidden-prompt flows still work; help/reference links agree. Check migration guidance for existing plaintext copies and document allowed import routes. Validate the broader key-handling requirement before closing it. The pinned roadmap specifies Umer as security reviewer; use that assignment or explicitly propose changing it instead of “any reviewer.”

### 6. Medium: the promised documentation review has no deliverable

**Location:** `README.md:63–65`.

The overview says you will review existing guides, but no file records that review. The repository does have client onboarding, wallet/migration guides, and client/auditor/aggregator role documentation. “No validator guide” must distinguish missing consolidated operational guidance from existing role pages.

**Correction:** bring a short inventory with existing page, coverage, gap, proposed launch importance, owner, and completion evidence. Include staking/unstaking, slashable behavior versus missed rewards, restart/recovery, upgrades, wallet migration, and supported hardware. Record the tokenomics-paper question as a team dependency, without assuming you own it.

### 7. Medium: several meeting claims are insufficiently traceable

**Locations:** `README.md:3`, `:18–38`, `:73–83`; `01-node-software-merge-plan.md:51–60`.

The overview attributes deliverables and decisions to people without linking the specific replies. PR numbers #31/#32 are not clickable or repository-qualified. The historical 248-test result has no report link. A commit pin cannot substantiate meeting logistics or live PR status.

**Correction:** add comment permalinks, full PR links, and the date/commit/command for recorded test results. Mark proposed assignments as proposals until accepted. Recheck mutable statuses before presenting. Until then, retain the distinction between verified snapshot facts and reported discussion context.

### 8. Medium: the preparation plan still leaves your next actions underspecified

**Locations:** `01-node-software-merge-plan.md:76–85`; `README.md:51–67`.

The merge estimate is still “your estimate”; the hardware work has no date or explicit owner; and the docs review has no output. The reported indexer-first order is only mentioned at the final promotion step, leaving unclear whether it constrains earlier merges or only the final integration.

**Correction:** bring one personal action table covering preparation output, owner, target date, dependency, and decision needed. For the stacked PRs, record each repository/base/head explicitly, clarify where the indexer fits, and distinguish engineering dependencies from preferred merge order. Validate the final combined revision, since separate branch test results do not establish integration readiness.

## Smaller corrections

- Replace “lose money on testnet” with the actual agreed penalty model. Lost test tokens, eligibility/rewards, infrastructure expenditure, and loss of real funds are different claims. The packet does not establish which applies.
- The Raspberry Pi argument confuses an approximately 5 GB installed environment with runtime suitability. Specify the Pi model, RAM, architecture, dependency compatibility, and measured completion time, or leave compatibility unknown.
- Keep the optional AlterMundi project discussion in an appendix. Describe agent-airlock as a possible isolation approach to evaluate, not proof of safe DIN task execution. Its [README](https://github.com/Mar-IA-no/agent-airlock) explicitly excludes protection of credentials mounted inside the jail and does not close network access.
- Replace the speaking-script placeholder “[link, or issue link]” with an actual reference or “proposed; no PR yet.”
- Use commit-pinned source links for snapshot claims; reserve branch links for live references.

## What already holds up

- The documents are easy to read and separate software integration, hardware sizing, and key handling effectively.
- They openly label unmeasured hardware values and stale test evidence instead of inventing results.
- The two key defects match the pinned source.
- The branch comparison reproduces 82 changed files and 12,852 added lines, and 121 develop commits not contained in the cited daemon commit. These counts describe that snapshot, not a future merge.
- The daemon branch contains the cited BL-19–BL-22 remediations, rotating JSON logs, and degraded-health HTTP responses.
- Keeping your contribution focused on operator readiness is reasonable. You need explicit handoffs to the larger meeting decisions, not personal ownership of every launch requirement.

## Recommended preparation before Friday

| Priority | Bring | Desired outcome |
|---|---|---|
| 1 | Corrected daemon scope and actual operator workflow | Agreement on what operators will run and what interruption/recovery work remains |
| 2 | T0.2 requirement-to-evidence table | Each item is implemented, pending validation, missing, or explicitly deferred; no automatic closure after merge |
| 3 | Model_0 measurement plan and clearly provisional hardware table | Named measurement owner, workload, deadline, and publication location |
| 4 | Explicit scope and acceptance checks for the key-fix PR | Reviewable task with security reviewer and target date |
| 5 | Existing-docs/gaps inventory | Agreement on which operator instructions must precede onboarding |
| 6 | Linked PR dependency plan and meeting sources | Clear review/merge sequence and traceable decisions |

Suggested opening: “The SDK and daemon framework are implemented on branches, but they do not yet automate validator roles. I want us to agree on the supported operator workflow, the checks needed to call it ready, and owners and dates for hardware measurements and missing operator guidance. I also confirmed two key-handling/documentation defects to fix.”
