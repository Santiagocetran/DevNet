# "What computer do I need?": measurement plan

← [Back to the meeting overview](README.md)

**Checklist item:** P3-T0.2b (resource ceilings) · **Facts checked against:** `develop` @ `5d258e0` (16 Sep 2026)

> **Revision 2 changes:**
> - This is now a **measurement plan**, not a table of answers.
> - "Minimum" must now meet deadlines.
> - A single test run is no longer enough.
> - Corrected: the existing guide **does** say its numbers are for Model_0.
> - Added the fact that work containers are already capped at 2 CPUs and 4 GB of memory.
> - The AlterMundi tools moved to an appendix.

---

## Why this matters

Someone deciding whether to run a DIN node asks: **Can my computer handle it? Will it slow down my
other work? What will it cost me in electricity and data?**

It matters more than usual here. Under the current design, **auditors and aggregators who miss
assigned work can have stake slashed** (liveness slashing, `Developer/design/MECHANISM_DESIGN.md`).
On testnet that stake is test tokens, not real money. But if we publish a minimum that can't keep up,
we set people up to be penalised for our wrong number.

**So "minimum" has to mean "meets the deadlines", not just "it runs".**

---

## What exists today

[`getting-started.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/getting-started.md#-system-requirements)
scopes its numbers to **Model_0** (the small demo model):

- 4 GB of memory
- about 30 GB of disk
- a standard CPU, no graphics card
- a Python environment of about 5 GB

**What's missing:** where these numbers came from, any split per role, internet speed, disk growth
over time, a "recommended" level, and guidance for bigger models.

**A useful fact already in the code:** all three roles (client, auditor and aggregator) do their
heavy work inside a separate container started with **`--cpus 2` and `--memory 4g`**
([`dincli/cli/worker.py:144-146`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/dincli/cli/worker.py#L144-L146)).
Be careful about what that does and doesn't tell us:

- **It's a configured limit, not what Model_0 actually uses.** It says a job isn't *allowed* more
  than 4 GB of memory; it doesn't say a job *needs* 4 GB. Only measuring tells us that. So we can't
  yet say whether the published 4 GB host minimum is too low or fine.
- **Swap isn't explicitly limited.** The command sets no `--memory-swap`. With Docker's default,
  a container given `--memory 4g` may also use swap (disk used as extra memory), up to the same
  amount again, if the host has swap enabled
  ([Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/)).
  Swap is far slower than memory, so a job that spills into it could miss deadlines without
  ever crashing.
- **What it does give us:** a known setting to record alongside our measurements. We'll also know
  if a job ever reaches the limit and gets killed or slowed down.

### Three different numbers, not one

| Number | What it is | Where it comes from |
|---|---|---|
| **Configured limit** | What the software *allows* a job to use (2 CPUs, 4 GB memory, swap not explicitly set) | The code; changeable by us |
| **Observed peak** | The most we actually *saw* used, under the tested workload, on the tested machines | Measurements. A few rounds give an observed peak, **not a guaranteed ceiling**. A bigger dataset, a slower network or a different machine could exceed it. |
| **Recommended host capacity** | What we tell operators to have: observed peak for the job, plus the node and operating system, plus headroom | Observed peaks plus an agreed safety margin |

---

## What the roadmap asks for

From `Developer/ROADMAP.md`, P3-T0.2b:

> Publish resource ceiling table: minimum and recommended RAM/CPU/disk/network per role (aggregator,
> auditor, client), tied to Compose file comments

So the result goes in **two places**: the public guide, and comments in the Docker Compose file
operators use.

---

## Definitions to agree on Friday

| Term | Proposed meaning |
|---|---|
| **Minimum** | The smallest machine that **completes its assigned work within the deadlines**, repeatedly, under the agreed workload |
| **Recommended** | Minimum plus headroom (for example 1.5×), so a slow day or a background task doesn't cause missed work |
| **Ceiling** | What we tell operators to plan for. It's **based on the observed peak plus a margin, not a guarantee**. Where we want a hard guarantee, it has to come from a configured limit (as with the work container), and we must check that the work still meets deadlines under that limit. |
| **Workload** | The exact scenario the numbers apply to (see below). Numbers outside that scenario are not promised. |

---

## The measurement plan

### 1. Fix the workload (agree Friday, or right after)

The numbers only mean something for a clearly described scenario:

| Setting | Proposal | Who can answer |
|---|---|---|
| Model | Model_0, as in `getting-started.md` | — |
| Dataset size per client | Whatever the Model_0 distribution command hands out today | Umer |
| Participants per round | Clients, auditors and aggregators per round in the planned testnet setup | Umer / Roberto |
| **Deadlines** | The submission windows each role must meet, taken from the contract settings for testnet | **Roberto** |
| Concurrency | One role per machine first; then the realistic "several models at once" case, if testnet allows it | Umer |
| Software version | A fixed commit, recorded with the results | Santiago |
| Storage retention | How long downloaded models and cache are kept before cleanup | Santiago / Umer |

### 2. Measure properly

- **Several rounds, not one.** At least 5 full rounds per role, to see disk growth and variation.
  That gives us an **observed peak** for this workload, not a guaranteed maximum.
- **Record the configured limits and swap.** Note the container's CPU and memory settings, whether
  the host has swap, and how much swap the job used. Any swap use during a job is a warning sign
  for deadlines.
- **Cold and warm.** The first run (downloads and container images) and later runs (cached) behave
  very differently. Record both.
- **Measure the whole machine and the work container separately.** The container has its own cap.
  The host needs room for the container plus the node plus the operating system.
- **Internet speed comes from file size and time allowed**, not from total data alone:
  (size of model files to download and upload) ÷ (time the deadline leaves for it). Record the
  total data per round too, for people with data caps.
- **Test at least two machine sizes:** one near the proposed minimum, one comfortable. If the
  small one misses deadlines, it isn't the minimum.

### 3. What we record for each role

| Measure | Why |
|---|---|
| Peak memory: host, and work container (plus swap used) | Observed peak, which feeds the recommended RAM |
| CPU use and time to finish each job | Whether the machine meets the deadline |
| Disk at start, after each round, and after cleanup | Disk needed for a month of running |
| Size of files downloaded and uploaded per round | Internet speed (with the deadline) and monthly data use |
| Whether every deadline was met | The pass/fail test for "minimum" |

### 4. Publish

- Update `getting-started.md` and the Compose file comments, as the roadmap requires.
- **Say where the numbers came from:** date, commit, machines used, and the workload.
- Say that **new models need their own numbers**, and who provides them. That's a question for
  the group.

---

## Draft table: shape only, no promises

| Role | Memory min / rec. | CPU min / rec. | Disk start + growth per round | Internet min / rec. | GPU |
|---|---|---|---|---|---|
| Client | *measure* | *measure* | *measure* | *measure* | Not for Model_0 |
| Auditor | *measure* | *measure* | *measure* | *measure* | Not for Model_0 |
| Aggregator | *measure* | *measure* | *measure* | *measure* | Not for Model_0 |

**Not for Friday:** no numbers go in this table until they've been measured under the agreed workload.

---

## Who and when (proposal)

| What | Who | When |
|---|---|---|
| Agree the workload settings and deadlines | Umer, Roberto, Santiago | Friday or the following days |
| Run the measurements | Santiago | Proposed: by 2 Oct |
| Review the numbers | Umer | After measurements |
| Publish in the guide and Compose comments | Santiago | After review |

---

## Questions for the group

1. **Is a Model_0-only table enough for the first invited cohort?** (Suggestion: yes, clearly labelled.)
2. **What are the testnet deadlines per role?** We can't define "minimum" without them.
3. **Who publishes the numbers for new models?**
4. **Raspberry Pi:** this came up in the AlterMundi conversation.
   - **Unknown for now.** It depends on the Pi model and memory, whether all dependencies (PyTorch,
     Docker images) run on ARM, and whether it meets the deadlines.
   - **Suggestion:** don't promise it. Test it later as a separate item if there's interest.

---

## Appendix: gpu-priorityd and agent-airlock

The question was whether to name these AlterMundi projects. **Short answer: they don't help
produce the hardware numbers, so they're not part of this plan.** They're listed here as optional
things to evaluate later, not as solutions.

**[gpu-priorityd](https://github.com/Mar-IA-no/gpu-priorityd)** lets one machine share its
graphics card, so the owner's own programs keep priority.

- **Might be relevant** once models need a graphics card and people contribute machines they also
  use for other things.
- **Limits today:** an early version, supporting only Linux with systemd and a single NVIDIA card.
  Model_0 doesn't need a graphics card at all.

**[agent-airlock](https://github.com/Mar-IA-no/agent-airlock)** walls off untrusted code from
files it shouldn't see, using a Linux sandbox.

- **A possible approach to evaluate** for running other people's model code safely. That's a
  different topic (roadmap P4-8.1, secure execution).
- **Not a sizing tool.**
- **Not a proof of safety for DIN:** its README says it doesn't protect credentials mounted inside
  the sandbox and doesn't close network access.
- **Very early:** 3 commits and no releases.

⚠️ **Fix in our own notes:** `ALTERMUNDI_DIN_POSSIBLE_CONTRIBUTIONS.md` says agent-airlock provides
"resource limits". Its README doesn't show that. Correct it before sharing.
