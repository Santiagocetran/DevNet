# Testnet readiness meeting: start here

**When:** Friday 18 September 2026, 9:00 Argentina time (12:00 UTC, 13:00 WAT). Half-day block.
The time was confirmed with the team outside the thread. The thread only records
[our availability](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132#discussioncomment-18376460).

**Where the conversation lives:** [Discussion #132](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132)

**Facts checked against:** `develop` @ `5d258e0`, `feat/din-sdk` @ `ab1ba24`, `feat/din-daemon` @ `27885d7`.
PR states and thread comments were read live from GitHub on 16 Sep 2026. **Re-check them Friday morning.**

> **Revision 2** (16 Sep, after the review in [AUDIT.md](AUDIT.md)). What changed:
> - The daemon is now described as a *framework*. It doesn't run the node roles yet.
> - Merging no longer "closes" checklist items. Each requirement now has evidence and a check.
> - The hardware doc is now a measurement plan, not a table of answers.
> - The key fixes are called "two confirmed defects", not "all that's left".
> - A docs inventory was added (doc 04).
> - Sources are linked, and suggestions are marked as suggestions.

---

## What the meeting is for

DIN wants to open its network to people outside the team. That's the "testnet". Before that
happens, we need to agree on two lists:

- **What must be finished first**, because without it outside people could lose their keys, their
  staked tokens or their data, or have their machines put at risk.
- **What can come later**, because it's missing or unpolished but not dangerous.

Umer already drafted most of that list in the thread:

- [his sequencing idea](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132#discussioncomment-18402720)
  (DevNet 2.0 → 3.0 → Testnet)
- [his A/B/C breakdown](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132#discussioncomment-18425893)
- [a research list of topics nobody owns yet](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132#discussioncomment-18426014)

We walk out with **one checklist** where every item has:

- an **owner**,
- a **status**, and
- a label: **"blocks launch"** or **"can come later"**.

**One rule worth proposing:** keep four statuses separate, because they aren't the same thing.

- **Built**: the code exists.
- **Reviewed**: someone else checked it.
- **Merged**: it's in the main code.
- **Proven**: we tested that it does what the requirement asks.

An item only counts as done at "proven".

---

## What each person brings on Friday

These are **suggestions based on the thread**, not assignments anyone has accepted.

| Who | Suggested contribution | Source |
|---|---|---|
| **Everyone** | Read Umer's A/B/C list. Come ready to label your items. | [A/B/C comment](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132#discussioncomment-18425893) |
| **Abraham** | Decide **who keeps the checklist** and **who gives the final go-ahead**. Answer the open question on merge timing (the thread has no reply from him yet). | [#139 question](https://github.com/InfiniteZeroFoundation/DevNet/discussions/139#discussioncomment-18402481) |
| **Umer** | The first version of the checklist (his section C). Answers to Roberto's two open questions. He's also the named security reviewer for the key work (roadmap, P3-T0.2b). | [A/B/C comment](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132#discussioncomment-18425893) |
| **Roberto** | Status of the money and penalty rules: his open PRs, the random-selection fix (BL-11) and when stress testing can start. | [Roberto's A2 comment](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132#discussioncomment-18436266) |
| **Santiago (us)** | The "keep operators safe" section (A1): the four documents below. | [Our A1 comment](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132#discussioncomment-18435058) |

---

## Our part, explained simply

We took the "keep operators safe" section: their keys, their machines and their data. Here's the
honest picture.

**What's true:** we've built a background service (the "daemon") that can shut down cleanly, report
whether it's alive, write logs and start with the computer. It's waiting in two pull requests,
[#31](https://github.com/InfiniteZeroFoundation/DevNet/pull/31) and
[#32](https://github.com/InfiniteZeroFoundation/DevNet/pull/32).

**What we must not overstate:** the daemon doesn't run the actual node work yet. It can't train,
audit or aggregate. Today an operator does all of that with the command-line tool. So:

- merging the daemon **doesn't** automatically tick the checklist items, and
- we **can't** skip making the command-line tool safe just because the daemon exists.

### What we bring

1. **An honest status of the node software**, with a table showing, for each requirement, what's
   done, what isn't and how we'd prove it.
   → [01: Node software status and merge plan](01-node-software-merge-plan.md)
2. **A plan to measure "what computer do I need"**, not a finished table. One test run isn't
   enough to promise anyone a minimum.
   → [02: Hardware requirements measurement plan](02-hardware-requirements-proposal.md)
3. **Two confirmed key-safety defects** and a small fix with clear checks. This is not a claim that
   key safety is finished.
   → [03: Private key fixes](03-private-key-fixes.md)
4. **An inventory of the operator guides**: what exists, what's missing, and which gaps should
   block launch.
   → [04: Operator docs inventory](04-operator-docs-inventory.md)

---

## Our own action list

Dates are proposals. Adjust them before sharing.

| # | What | Output | Target | Depends on | Decision needed Friday |
|---|---|---|---|---|---|
| 1 | Open the key-fix PR, or an issue if it isn't ready | PR or issue link, added to doc 03 | Thu 17 Sep | nothing | Umer confirms he'll review |
| 2 | Re-check live PR states and thread comments | Updated status lines in docs 01 and README | Fri 18 Sep, morning | nothing | none |
| 3 | Bring #31/#32 up to date with `develop` and re-run tests | Test counts with date and commit in the PR body | Proposed: week of 21 Sep | nothing | Merge timing (Abraham) |
| 4 | Run the hardware measurements | Filled-in table plus raw numbers | Proposed: by 2 Oct | Workload and deadlines agreed Friday | What workload and deadlines to measure against |
| 5 | Check the command-line tool's interruption risk | Short findings note: which commands are risky if stopped | Proposed: by 25 Sep | nothing | Whether this blocks launch |
| 6 | Turn the docs inventory into issues | One issue per agreed gap, with owners | After Friday | Friday's labels | Which gaps block launch |

---

## Good to know before walking in

**Roberto's side (live on 16 Sep):**
- [#140](https://github.com/InfiniteZeroFoundation/DevNet/pull/140) and
  [#141](https://github.com/InfiniteZeroFoundation/DevNet/pull/141) were merged on 16 Sep.
- [#146](https://github.com/InfiniteZeroFoundation/DevNet/pull/146) and
  [#149](https://github.com/InfiniteZeroFoundation/DevNet/pull/149) are open. By his own account,
  stress testing waits on both.
- No PR exists yet for the random-selection weakness (BL-11).

**Umer's research list:** it raises topics with no owner yet: legal risk around the airdrop, terms
of use, fake-identity protection for the airdrop, an incident plan, and model-owner onboarding.

**Roberto's two open questions:**
1. The dispute process for encrypted test data: a gap, or deliberately left for later?
2. The new contract events: part of the indexer work, or a separate task?

**Why this matters to operators:** under the current design, auditors and aggregators who miss
assigned work can have **stake slashed** (`Developer/design/MECHANISM_DESIGN.md`, liveness
slashing). On testnet that stake is test tokens, not real money. Still, it's the reason hardware
minimums must mean "meets the deadlines".

---

## Suggested opening line for our part

> "The SDK and daemon framework are built on branches, but they don't yet run the validator
> roles. Operators still use the command-line tool. I'd like us to agree on the supported way to
> run a node, what evidence we need before calling each safety item done, and owners and dates for
> the hardware measurements and the missing operator guides. I've also confirmed two key-handling
> defects with a small fix."

---

## The documents in this folder

| # | Document | In one line |
|---|---|---|
| 01 | [Node software status and merge plan](01-node-software-merge-plan.md) | What the daemon does and doesn't do, the evidence for each requirement, and the merge steps |
| 02 | [Hardware requirements measurement plan](02-hardware-requirements-proposal.md) | How we get trustworthy "what computer do I need" numbers |
| 03 | [Private key fixes](03-private-key-fixes.md) | Two confirmed defects, the fix and how we check it |
| 04 | [Operator docs inventory](04-operator-docs-inventory.md) | What guides exist, what's missing and suggested launch importance |
| — | [AUDIT.md](AUDIT.md) | The independent review that led to revision 2 |
