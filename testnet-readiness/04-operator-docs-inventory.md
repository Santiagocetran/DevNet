# Operator docs inventory

← [Back to the meeting overview](README.md)

**Facts checked against:** `develop` @ `5d258e0` (16 Sep 2026). This is a first pass based on page
titles, section headings and keyword searches, not a line-by-line read. Treat "covered" as "there is
a page that addresses it", not "the page is correct".

---

## Why this exists

In the thread we said we'd review the existing guides and list what's missing. Roberto's position
is that the **staking guide and slashing rules must exist before the first outside validators
join**, and that the tokenomics paper and validator guide can come a couple of weeks later
([his comment](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132#discussioncomment-18375312)).

This inventory is meant to help the group decide which gaps actually block launch.

---

## What already exists (public docs)

| Page | What it covers |
|---|---|
| [`getting-started.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/getting-started.md) | Model_0 walkthrough: setup, roles overview, hardware (Model_0 only) |
| [`setup.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/setup.md) | Installing and configuring `dincli` |
| [`guides/client-onboarding.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/guides/client-onboarding.md) | Getting started as a client |
| [`guides/wallet-setup.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/guides/wallet-setup.md) | Creating and choosing a wallet, including the encrypted keystore |
| [`guides/keystore-migration.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/guides/keystore-migration.md) | Moving from plain-text keys to the keystore |
| [`guides/ipfs.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/guides/ipfs.md) | IPFS provider setup |
| [`roles/clients.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/roles/clients.md) | Client commands: train, submit, view |
| [`roles/auditors.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/roles/auditors.md) | Auditor: buy and stake tokens, register, evaluate. The opening paragraph says auditors can be slashed for bad behaviour or missed batches. |
| [`roles/aggregators.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/roles/aggregators.md) | Aggregator: buy and stake tokens, register, aggregate. The opening paragraph says aggregators can be slashed for bad behaviour or missed batches. |
| [`roles/model-owner.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/roles/model-owner.md), [`roles/dindao.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/roles/dindao.md) | Model owner and admin commands, including the ones that trigger slashing |
| [`cli-reference.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/cli-reference.md) | Command reference |
| `technical/mechanisms/staking-mechanism.md`, `technical/testing/containerization-guide.md`, `dincli/docker/node/README.md` | Team-facing technical pages: staking internals, and the container setup |

---

## Gaps, with a suggested launch importance

"Suggested" means for the group to confirm or change on Friday.

| Topic an operator needs | What exists | Gap | Suggested importance | Suggested owner |
|---|---|---|---|---|
| **Staking and unstaking** | How to stake is in the auditor and aggregator pages | **No operator guidance on unstaking or getting stake back** | **Blocks launch** (people need to know how to get out) | Roberto (contracts) |
| **What gets you slashed vs. what just loses rewards** | Both the auditor and aggregator pages mention slashing in one sentence (bad behaviour, missed batches). The detailed rules live only in team design docs. | **No complete operator rules**: how much is slashed, for what, whether there's a warning or appeal, and what only costs rewards | **Blocks launch** (Roberto's position) | Roberto |
| **Rewards: how and when you get paid** | Barely mentioned | No operator-facing explanation | Suggest: can trail by 2 weeks | Roberto / Umer |
| **Validator guide end to end** (wallet → stake → first round) | Pieces spread across role pages | No single journey. The roadmap has it as P3-DOC4 (Umer, Robbert), still Planned. | Suggest: can trail, **if** staking and slashing pages exist | Umer, Robbert |
| **Supported hardware** | Model_0 numbers, no method | See doc 02 | **Blocks launch** (T0.2b) | Santiago |
| **Keeping your key safe and migrating** | Wallet guide and migration guide | Wrong path in `.env.example`; no step to remove old `.env` keys (see doc 03). **The migration guide contradicts itself** (see below). | **Blocks launch** (small fix) | Santiago |
| **Running the node in a container** | Team-facing container guide and README | No public, operator-facing version | Depends on the supported workflow decided Friday (doc 01) | Santiago |
| **Restarting, recovering and upgrading safely** | Nothing public (only the migration guide mentions upgrading) | **No guidance on what to do after a crash, a stop mid-job, or a new release** | Suggest: **blocks launch** for anything that can cause missed work | Santiago |
| **Network and firewall setup** | Container README mentions sandboxed workers | No guide (T0.2e) | Suggest: can trail for an invited cohort | Santiago |
| **Where to get help and what to report** | `getting-started.md` points to a DevNet discussion | No testnet support channel or incident contact | Depends on Umer's research-list items | Abraham / Umer |
| **Tokenomics paper** | Team design docs only | Public paper doesn't exist | Roberto: can trail by 2 weeks | **Team dependency, not ours**. Ask who owns it. |
| **Terms of participation / testnet disclaimer** | Nothing | Raised in [Umer's research list](https://github.com/InfiniteZeroFoundation/DevNet/discussions/132#discussioncomment-18426014) | Group decision | Abraham |

---

## Contradictions found in existing guides

These are pages that exist but say two things that can't both be true.

### The migration guide says the passphrase is never stored, and also tells you to store it

In [`guides/keystore-migration.md`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/guides/keystore-migration.md):

- **Lines 30–33:** to avoid re-typing, put `DIN_WALLET_PASSWORD=your_secure_passphrase` in your `.env`.
- **Line 122:** its own table lists `DIN_WALLET_PASSWORD` as living in the `.env` file.
- **Line 124:** "The passphrase is **never stored on disk**."

If you follow the tip, your passphrase **is** on disk in plain text, right next to your setup. The
wallet guide is more honest here: it rates this option as only "medium" security and meant for
unattended automation (`wallet-setup.md:158`).

**Why it matters:**
- An operator who reads "never stored on disk" might feel safe putting the passphrase in `.env`.
- Anyone who can read that file, plus the keystore file, can unlock the key.

**Proposed fix (in the doc 03 PR):**
- Change line 124 to say the passphrase is not stored **unless you choose to set
  `DIN_WALLET_PASSWORD`**.
- Present that option as automation-only, with the same trade-off wording as the wallet guide.
- Point to safer ways of providing it, for example a secrets manager or file permissions. The
  security reviewer should confirm which ways to recommend.

---

## How we'd know a doc gap is closed

For each gap labelled "blocks launch":

1. The page exists in `Documentation/public/`.
2. The owner of that area reviewed it for accuracy. Contract pages get checked against the
   deployed contract settings.
3. **Someone outside the team follows it** without asking in chat, and succeeds.

---

## After Friday

- Open **one issue per agreed gap**, with the owner and label from the meeting.
- Link those issues from the testnet checklist.
