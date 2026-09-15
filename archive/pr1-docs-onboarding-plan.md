# PR 1 — Onboarding docs fold-in (`setup.md`, `GettingStarted.md`, `connect-wallet` help text)

**Branch:** `docs/aggregator-onboarding-walkthrough` (off `main` @ `e83c589`)
**Base / target:** `main` on `InfiniteZeroFoundation/DevNet` — per Umer, not `develop`
**Origin:** [discussion #79](https://github.com/InfiniteZeroFoundation/DevNet/discussions/79), Umer's review comment 2026-08-11
**Status:** rev 4 — audited, amended, ready to hand to an implementing agent.

> **Rev 2 changelog.** A design review found four merge-blocking issues in rev 1. All four were
> re-verified against the tree and **all four were upheld**. Rev 1's S1, S4, S14 and the
> `setup.md`-vs-`GettingStarted.md` split were wrong as written and are rewritten below.
> Corrections to the review itself are recorded in §11.
>
> **Rev 3 changelog.** Rev 2 treated four open questions (D3, D5, D6, D7) as authoring blockers.
> They are not. See §0 — each is resolved by a workaround that requires no decision from Umer,
> and each is surfaced in the PR body instead (§8). Nothing in this plan is now blocked.
>
> **Rev 4 changelog.** Final audit; six amendments applied, all verified against the tree first:
> (1) buy/stake ownership was left homeless by rev 3's restructure — role flows keep their
> role-specific `dintoken` commands (§4.2.2); (2) slashing language is now governed by one rule
> applied everywhere, since deployed enforcement cannot fire (§4.2.6); (3) IPFS verification is one
> positive Filebase test plus three negative characterization tests (§7.4); (4) Google Cloud is an
> **L1** funding source and moves to the bridge subsection (§4.2.5); (5) the XDG isolation check now
> validates *resolved* platformdirs paths (§7.1); (6) §10 evidence is a merge gate. Also: the
> readiness checklist uses `task explore 0 --update`, because a plain `explore` can pass against a
> cached manifest without exercising retrieval at all (`cli/utils.py:508`).

---

## 0. Guiding principle — why nothing here is blocked

Rev 2's error was treating *"we don't know the right answer yet"* as *"we can't write anything."*

This PR's job is **not** to declare policy. It is to stop the current docs from actively hurting
readers. Every open question below is resolved the same way:

> **Describe what is true and tested today; mark the open question where a reader will trip over it;
> never imply an answer we cannot support.**

The only thing that genuinely requires Umer is *declaring an official supported configuration* —
a policy call. Nothing in this PR needs that. Where a question remains open, the doc says so
plainly, which is strictly safer than the current text, which implies a wrong answer.

Consequence: this PR is partly **a question posed in the form of a diff**. That is deliberate —
concrete text is far easier to react to than an abstract ask — but it means the install section
may come back for a second round. Accepted trade.

---

## 1. Goal

Fold the walkthrough that actually worked on `agent@10.10.20.37` into the participant docs as the
primary recommended sequence, and slot every doc-level fix from the discussion into its correct
place in context.

Umer's framing: *"Easier for you to place these correctly in context than for us to hand you a patch
to slot in."*

**The single highest-value change is fixing the prerequisite boundary.** The role flows in
`GettingStarted.md` are not merely mis-ordered — as written, **Step 1 cannot run**. `task explore 0`
calls `get_en_w3_account_console` (`cli/task.py:128`), which requires a connected wallet and a
working RPC, and then `cache_manifest(...)` → `retrieve_from_ipfs(...)` (`cli/utils.py:508-510`),
which requires a configured IPFS provider. All three are established in Step 3 (`:264-284`). A
reader following the document top-to-bottom fails on the first command.

## 2. Scope

**In:**

- `Documentation/setup.md`
- `Documentation/GettingStarted.md`
- `dincli/cli/system.py` — **help text only** (`connect_wallet` docstring + one `--account` help
  string). Umer asked for this under Docs. Nothing outside docstrings and Typer `help=` strings.

**Out — deliberately:**

| Excluded | Why | Goes to |
|---|---|---|
| `pyproject.toml:7` version, `dincli/__init__.py:1` version, `dist/*.whl`, `setup.md:30,32` wheel filename | Umer cuts 0.2.0 after reviewing these PRs. The wheel is a committed binary — any PR rebuilding it conflicts with all the others | Umer, post-merge |
| Whitelist, `buy()` retry, demo styling, chain-id, IPFS GET, backports | Separate PRs | PRs 2–6 |
| Making `ipfs node` a settable provider | Code change. D7 resolved as option (a): document reality here, fix the code separately | PR 6 |

**Everything here describes behaviour as it is on `main` today.** Where a later PR changes that
behaviour, §6 records the coupling.

## 3. Preconditions — done

- [x] Fork synced: local `main` == `origin/main` == `upstream/main` @ `e83c589`
- [x] Branch `docs/aggregator-onboarding-walkthrough` created off `main`
- [x] Working tree clean; 56 `feat/din-sdk` commits confirmed pushed to `origin`
- [x] `Plans/` archived (21 files in `Plans/archive/`); `Plans/` is in `.git/info/exclude`

## 4. Change inventory

Findings reference `aggregator-onboarding-report.md` IDs (B1–B13); see §10 for the evidence
appendix. Every B-finding below was confirmed by Umer against the code.

### 4.1 `Documentation/setup.md`

| # | Location | Problem | Change |
|---|---|---|---|
| **S1** | §2 Option A, `:28-33` | **Rewritten in rev 2, unblocked in rev 3.** `pip install <wheel>` resolves deps freely. But rev 1's fix — "install `cache_model_0/requirements.txt` first" — is wrong as a universal instruction: that file is a 121-line `pip freeze` of a Linux/CUDA dev box, including **13 `nvidia-*` packages, `triton`, `pytest`, `ruff`**. On macOS or ARM it fails outright, and it contradicts Umer's own "CPU-only" pinning direction | **Workaround, §4.1.1.** Do not declare a supported lock. Document the exact tested configuration, state why versions matter, and route unsupported platforms to the team |
| S2 | §2 Option B, `:38` | `pip install git+…@main#subdirectory=dist` — `dist/` holds only the wheel and tarball, no `pyproject.toml`. Suspected broken | **Test first** (§7). If broken: fix or remove. Do not keep a dead install path |
| S3 | §1 `:11-17` + all later examples | venv created once, never mentioned again; every later example is a bare `dincli` | One line on re-activating per session |
| **S4** | §1 `:19-20` | **Softened in rev 2.** Rev 1 proposed promoting 3.12.3 from recommendation to *requirement*. Unsupportable: the verified host ran **3.13.5**, and the pinning decision is open (D3). A version alone also cannot guarantee bit-exactness across BLAS backends and CPU arch — Umer's own point | Use **"tested configuration"**, not "required". Record what was actually tested (3.13.5 here; 3.12.3 documented) and note a supported matrix is pending |
| S5 | §4 `:65-77` | `> [!NOTE]` sits **inside** the ```bash fence → renders as shell text | Move the note outside the fence |
| S6 | §4 `:69` | Lists `sepolia_devnet`; `din_info.json` has only `local`, `sepolia_op_devnet`, `mainnet` | Drop it, or mark unimplemented |
| S7 | §5 `:82` | "root directory of your project" — actually `Path(os.getcwd()) / ".env"` (`cli/utils.py:118`). Wrong cwd during T1 = no submission (B5) — phrase per §4.2.6 | State plainly: read from **the directory you run `dincli` from** |
| S8 | §5 `:110-126` | Assumes you already have a private key; a fresh headless box has none | Add the `eth_account` keygen snippet |
| S9 | §5 | `.env` holds a raw private key with no permissions guidance | Add `chmod 600 .env` |
| S10 | §5 `:122-133` | `connect-wallet --account 0` at `:125` precedes the IMPORTANT note at `:128-133` saying demo mode must be off first | Reorder: demo-off before any `connect-wallet` |
| S11 | §5 `:92-108` | No warning that a wrong-chain RPC is accepted silently (B13) | Warn: `optimism-mainnet` vs `optimism-sepolia` is one word; only symptom is `ETH Balance: 0`. Revise when PR 5 lands (D2) |
| S12 | §6 Option A `:147` | `--api-key <your_api_key>` — `<` is shell redirection (B12) | `YOUR_API_KEY`, no brackets |
| S13 | §6 | No mention that `configure-ipfs` currently demands a connected wallet it never uses (B1) | Order IPFS setup **after** wallet connection — correct both before and after PR 2 |
| **S14** | §6 Option B `:154-168` | **Rewritten in rev 2.** Rev 1 said to "correct the command" to `--provider "ipfs node"`. **That command does not exist**: `configure_ipfs` validates against `{"filebase", "custom"}` and exits 1 on anything else (`cli/system.py:779-784`). The node path is selected *only* when `ipfs_provider` is absent or already equals `"ipfs node"` (`services/ipfs.py:68`) | **Workaround, §4.1.2:** document Filebase as the working path; mark self-hosting not-selectable; note the stale-provider trap. No invented commands |
| S15 | §6 | No statement that an aggregator **needs** upload capability — a read-only gateway cannot submit | Add it: upload capability is necessary to meet the intended submission duty. This is why Filebase is on the critical path. Phrase per §4.2.6 |

#### 4.1.1 — S1/S4 workaround: "tested configuration", not "supported configuration"

What the section must **stop** doing is the dangerous part: today it implies any Python ≥3.9 works
and that dependency versions are a matter of taste. For an aggregator, dependency drift can put your
output out of consensus with your batch. That implication has to go regardless of what the eventual
policy is.

Ship this instead:

1. **A "why this matters" line — phrased as four distinct steps, not one causal chain.** Dependency
   drift *can* change serialized output; a changed output produces a different CID; a CID differing
   from the finalized batch CID is a consensus divergence; that divergence is *intended* to be
   slashable. Do **not** write "a numpy drift is a slash" — see §4.2.6. Not every version difference
   changes output, and enforcement is currently non-functional.
2. **The tested configuration, labelled as such.** Presented as *"verified end-to-end on this
   configuration"*, never *"required"* or *"supported"*. Record all of: Python version, OS and
   version, architecture, CPU model, torch and numpy versions, whether CUDA was available or used,
   any thread/determinism settings, and the full resolved package set (§7.5).
3. **What the wheel pins and what it does not.** `torch==2.6.0` is pinned exactly; `numpy>=2.2.0` is
   open-ended (`pyproject.toml:18-28`). Name numpy as the known drift risk.
4. **An honest routing line for everyone else.** *"A supported platform matrix is being finalised.
   If you are on macOS or ARM, or cannot match the tested configuration, check with the team before
   registering as an aggregator — a mismatch risks putting your output out of consensus with your
   batch."* True, useful, and costs a reader nothing.
5. **`cache_model_0/requirements.txt` referenced with its caveat, not as the instruction.** Note what
   it is — a Linux/CUDA freeze including GPU and dev tooling — and that CPU-only operators should not
   install it wholesale. Mention `--no-deps` only in the context of the tested Linux path, where it
   was actually exercised.

**Not doing:** authoring a curated lock file. That is inventing policy, it would be untested, and it
is Umer's call. §8 asks the question with this section as the concrete starting point.

S4 follows the same rule: **"tested with"**, never "requires". The verified host ran Python 3.13.5
while the doc recommends 3.12.3 — state both and flag the gap rather than picking a winner.

#### 4.1.2 — S14 in detail: the actual state of IPFS configuration on `main`

Three separate defects, only one of which rev 1 had right:

1. **`ipfs node` cannot be selected.** `--provider` accepts only `filebase` or `custom`. The node
   implementation runs only when no provider has ever been configured. So the real procedure is
   *"set `IPFS_API_URL_ADD`/`IPFS_API_URL_RETRIEVE` in `.env` and **do not run `configure-ipfs`**"* —
   plus handling the case where a stale `ipfs_provider` already sits in the global config.
2. **`custom` is selectable but unusable.** Rev 1's "not reachable from the CLI" was imprecise — the
   command *does* write `"custom"` (`system.py:788`). It is unusable because `ipfs_service_path` has
   no CLI setter on `main` and is only ever read (`services/ipfs.py:124`).
3. **New finding, beyond B11:** even hand-editing `config.json` will not save it. `_load_custom_fn`
   calls `importlib.util.spec_from_file_location` at `services/ipfs.py:23`, but `importlib` is
   **never imported** — `services/ipfs.py:1-7` has no such import. Any `custom` provider raises
   `NameError`. This is a real code bug not in the original report; it belongs in PR 6 and should be
   raised in the thread.

The global-config caveat matters: because `CONFIG_DIR = Path(user_config_dir("dincli"))`
(`cli/utils.py:23`), provider state is **machine-global**, not per-project. A user who once ran
`configure-ipfs --provider custom` cannot get back to the node provider through any documented
command.

**Rev 3 workaround — document reality, do not invent a procedure.** There is no honest way to write
"how to select the local-node provider" because the software does not offer it. So:

- **Filebase** is documented as the working path, properly, with the `YOUR_API_KEY` fix (S12) and the
  upload-capability requirement (S15).
- **The self-hosted option** is marked *"currently not selectable — fix in progress"*, with a one-line
  explanation and a pointer to the follow-up. Do not print a command that exits 1.
- **The stale-provider trap** gets a short note: provider choice is stored per machine, not per
  project, and there is currently no documented way back to the default.
- **`custom`** is described as non-functional on `main`, citing both causes (no `--service-path`
  setter, and the `importlib` `NameError`).

This needs no decision and no code. **D7 is resolved as option (a).** The code fixes — accepting
`"ipfs node"` as a provider, and the missing import — go to PR 6, and both are raised in the PR body.

### 4.2 `Documentation/GettingStarted.md`

| # | Location | Problem | Change |
|---|---|---|---|
| G1 | Faucets `:198-210` | No statement that Ethereum Sepolia (L1) ETH does not work (B8) | Bold callout: must be **Optimism** Sepolia (L2), chain `11155420` |
| G2 | Faucets `:202-208` | All five gate on MetaMask/Coinbase/WalletConnect, several on mobile. Alchemy wants ≥0.001 ETH on mainnet plus history. A headless operator cannot self-serve (B9) | Say so, then give the bridge route |
| **G3** | Faucets — new | **Hardened in rev 2.** Bridge route undocumented | New subsection, with the safety rails in §4.2.1 |
| **G4** | Faucets `:204-208` | **Corrected in rev 4.** Google Cloud is missing from the funding guidance | It is an **Ethereum Sepolia (L1)** source. It goes in the *bridge* subsection, **not** the OP Sepolia faucet list — see §4.2.5 |
| **G5** | Structure `:198` vs `:215`, role flows `:250+` | **Escalated in rev 2.** Not just faucets-before-install: the role flows are **unexecutable** (§1) | See §4.2.2 — prerequisite boundary |
| G6–G8 | Aggregators `:264-284`, Auditors `:350-370`, Clients `:511-529` | `connect-wallet --account 0` with no preceding `configure-demo --mode no` → publicly known Hardhat key in plaintext (B2, 🔴 security) | **Superseded by §4.2.2**: wallet setup leaves the role flows entirely. Umer's `--mode no` still appears in each section, in the prerequisite block — see §4.2.2 and §8.1 |
| G9 | Aggregators `:274`, Auditors `:360` | `buy 0.00001` mints exactly 10 DIN = `MIN_STAKE` (B3) | **Qualified in rev 2** — see §4.2.3 |
| G10 | Aggregators Step 3 | No IPFS setup before the first `show-state` | **Superseded by §4.2.2** — and rev 1 had the boundary in the wrong place (`explore`, Step 1, needs it too) |
| G11 | `:156` | "Typical setup time is around 10–15 minutes" | Adjust honestly, or scope to "once funded and configured" |
| G12 | `:229-242` | `<your_rpc_url>` / `ETH_PRIVATE_KEY_0=...` — inside ```env fences, so not shell-hostile, but inconsistent | Normalise placeholder style doc-wide |
| **G13** | Aggregators — new | **Rewritten in rev 2.** Rev 1 would have described a full-stake slashing duty as current behaviour while knowing the deployed path reverts — contradicting §2 | See §4.2.4 |

#### 4.2.1 — G3 bridge route, with mandatory preflight

Document as a procedure with checks, not a recipe to paste:

- **Do not hardcode gas.** Estimate and apply a buffer. State the *expectation* — roughly 600k, not
  21,000 — so a 21k limit is recognised as the error it is. (Observed here: 616,165. Umer asked for
  this gotcha specifically; framing it as "estimate, expect ~600k" satisfies that without turning one
  observation into a constant.)
- **Timing:** Optimism documents L1→L2 as typically 1–3 minutes. Observed here: ~75 s. Document the
  range, not the observation.
- **Preflight checks, all mandatory:** L1 RPC `chain_id == 11155111`; L2 RPC `chain_id == 11155420`;
  destination address has bytecode; address taken from the current official registry; sender is an
  EOA and is the intended L2 recipient.
- **Post-flight:** verify receipt status *and* the resulting L2 balance.
- Keep the `OTHER_BRIDGE()` caveat — it returns the same `0x4200…0010` predeploy on every OP-Stack
  chain, so it confirms nothing about which chain you are on. It supplements the checks above; it
  does not replace them.

#### 4.2.2 — G5/G6–G8/G10: the prerequisite boundary

Replace per-role setup with a hard boundary:

1. `setup.md` owns **shared machine setup**, and only that: install, wallet creation and connection,
   RPC configuration, IPFS configuration, OP Sepolia ETH funding, readiness verification.
2. `setup.md` ends with a **readiness checklist** the reader must pass: wallet connected and address
   matches the funded one; RPC chain id is 11155420; ETH balance non-zero; **manifest retrieval works
   — `dincli task explore 0 --update`**. The `--update` is required: `cache_manifest` only calls
   `retrieve_from_ipfs` when `update` is set or the manifest is absent (`cli/utils.py:508`), so a
   plain `explore` can pass against a cached file without proving retrieval works at all.
3. `GettingStarted.md` role sections **begin after that boundary** and keep every **role-specific**
   operation.

**What stays in the role flows — corrected in rev 4.** Rev 3 said "no buy/stake duplication", which
left those commands homeless: `setup.md`'s sequence ends at funding, so nothing owned them.

| Role | Retains |
|---|---|
| Aggregator | `aggregator dintoken buy` / `stake` / `read-stake`, `aggregator register`, then the T1/T2 operations |
| Auditor | `auditor dintoken buy` / `stake` / `read-stake`, `auditor register`, then evaluation |
| Client | No validator staking steps at all — training and submission only |

Aggregator and auditor commands look duplicated but are **different command namespaces**
(`aggregator dintoken …` vs `auditor dintoken …`) and cannot be hoisted into a shared section. The
goal is removing duplicated *machine setup*, not removing required *role operations*. G9 (the buy
amount) therefore lands in both role sections, and that is correct.

This is the only structure that removes the two-competing-sequences problem *and* the unexecutable
Step 1.

**Rev 3 workaround — satisfy Umer's ask and the better structure at once.** Rev 2 framed this as a
choice: his literal request (add `--mode no` inside each role section) *or* the boundary (remove
setup from those sections). It is not a choice. Do both:

- The **full sequence** lives once, in `setup.md`.
- Each role section opens with a short **prerequisite block** — not a duplicate sequence — that names
  the critical steps and links to the checklist. **`configure-demo --mode no` is named explicitly in
  that block.**

So the security fix Umer asked for still appears in the aggregator, auditor, and client sections,
exactly where he asked for it. What disappears is the *duplicated full sequence* that let the two
copies drift apart — which is what produced B2 in the first place.

This also makes the change cheap to reverse: if he wants the full steps inline again, it is a small
edit to three prerequisite blocks, not a re-architecture. **D6 is resolved** — proceed, and flag the
divergence prominently in the PR body (§8) so he can push back on structure without the security fix
being at stake either way.

#### 4.2.3 — G9: buy amount, correctly qualified

Two qualifications rev 1 missed:

- The rate is **owner-mutable**: `dinPerEth = 1_000_000 * 1e18` (`DinCoordinator.sol:18`) with
  `updateDinPerEth` at `:81`. So "0.00001 ETH = 10 DIN" holds only at the current rate. Document the
  conversion *and* how to check the live rate.
- **Buying more does not increase your staked margin.** `stake()` ignores its `amount` argument and
  always approves and stakes `MIN_STAKE` (`cli/aggregator.py:74`, `:91` — this is issue #37, fixed on
  `develop`, backported in PR 3). Extra DIN is a **liquid reserve** — useful for re-staking after a
  slash, or for a second account — not a bigger stake. Rev 1's word "headroom" was ambiguous.

#### 4.2.4 — G13: slashing, split into intent vs deployed reality

Rev 1 would have presented intended enforcement as current behaviour. Also, **"full `minStake()`" is
ambiguous** — there are two different values with that name:

| Value | Where | Amount |
|---|---|---|
| Coordinator `minStake` | `DINTaskCoordinator.sol:17` | `1_000_000` (1e6) |
| Staking `MIN_STAKE` | `DinValidatorStake.sol:28` | `10 * 1e18` (10 DIN) |

`slashAggregators` passes the coordinator's value (`:522`) into a function that rejects anything below
the staking contract's (`:119`) — which is why the call always reverts. Document three things
separately: (a) the intended duty and penalty, (b) that enforcement is currently non-functional on the
deployed contracts and under remediation, (c) the exact unit intended after the fix. Do not present
future enforcement as current behaviour.

#### 4.2.5 — G4: Google Cloud is an L1 funding source, not an OP Sepolia faucet

Rev 1–3 carried this over from the original report's proposed fix, which suggested adding
`cloud.google.com/application/web3/faucet/optimism/sepolia` to the OP Sepolia list. **Drop that.**

**Why, and on what evidence.** The URL could not be verified either way from a headless shell —
`cloud.google.com` soft-404s (a deliberately bogus path returns a near-identical 200 HTML shell), and
the faucet UI is JS-rendered behind sign-in. So neither "it exists" nor "it does not exist" is
provable here. That is precisely the reason to drop it: **the recorded run never used it.** What was
actually used was `cloud.google.com/application/web3/faucet/ethereum/sepolia`, and it delivered
0.05 ETH to **Ethereum Sepolia L1** while the OP Sepolia balance stayed at `0x0`
(`aggregator-onboarding-report.md:390-393`). Publishing the other URL would recommend something never
tested — exactly what §0 forbids.

**What to write instead:**

- Place Google Cloud under **"Fund on Ethereum Sepolia, then bridge"**, alongside the bridge
  procedure (§4.2.1).
- State that funds arrive on **chain 11155111** and **cannot pay `dincli` transactions** until
  bridged to **11155420**.
- Keep it out of the direct OP Sepolia faucet list entirely.
- Do not call it "lowest friction" — faucet gating and availability change; that was one observation
  in August 2026, not a durable property.
- The L1-vs-L2 warning (G1) is what makes this section safe; it must appear above both lists.

#### 4.2.6 — Slashing language: one rule, applied everywhere

Rev 3 split intent from reality in G13 but still wrote "that's a slash" casually elsewhere (S15, the
install rationale, the `.env`-cwd warning). **Every mention of slashing in this PR must use the same
formulation**, because the deployed path cannot slash anyone today (§4.2.4).

**Canonical wording:**

> Non-submission, or submitting a CID that differs from the finalized batch CID, violates the
> intended aggregator duty and is intended to be slashable. Enforcement on the currently deployed
> contracts is non-functional and under remediation.

**Rules:**

- Never assert a slash as a present-tense consequence. Use *"intended to be slashable"*.
- Never collapse the causal chain. Environmental difference → output difference → CID divergence →
  intended enforcement are four steps, and the first does not guarantee the second.
- Where a slash is mentioned, the enforcement caveat goes with it — not three sections away.
- **Do mention the real present-tense consequence**, which is arguably worse and is *not*
  hypothetical: a missed or divergent submission means `slashAggregators` reverts, and since `endGI`
  requires the state only that call can produce, **the global iteration cannot be ended at all**. So
  "nothing happens to you today" is wrong — the round wedges for everyone.

**Applies to:** S7 (`.env` cwd), S15 (upload capability — phrase as *"necessary to meet the intended
submission duty"*), §4.1.1 (install rationale), G13, and the readiness checklist.

### 4.3 `dincli/cli/system.py` — `connect_wallet` help text

Umer asked for the `"(Recommended)"` label. Reading the whole block, there are **four** defects.

| # | Location | Current text | Problem | Change |
|---|---|---|---|---|
| C1 | `:172` | `# Interactive prompt (Recommended)` | Recommends the form that can silently desync from the funded key (B7). Umer's ask | Drop the label |
| C2 | `:167` | `--account` help: `"Hardhat dev account index (0-69)"` | Describes only the demo-mode meaning. With demo off it reads `ETH_PRIVATE_KEY_N` (`:215-216`) — the production path | Describe both branches |
| C3 | `:181` | `# Connect Hardhat dev account by index (auto demo mode)` | **Factually wrong.** `--account` does not auto-enable demo mode; it branches on the existing config (`:208`) | Rewrite; show the non-demo `.env` usage first |
| C4 | `:186` | `In demo mode (--yes)…` | No `--yes` flag exists on this command | Correct the reference |

**Scoped in rev 2:** do **not** label `--account` universally recommended. `--key-file` is presented
as the secure option (`:173`) and `--account` depends on keeping a raw key in `.env`. Wording:
*"recommended for the `.env`-indexed onboarding flow in `setup.md`, with demo mode disabled."*

C3 is the substantive one: fixing C1 alone leaves `--account` described as a Hardhat-only flag that
turns demo mode on, so nobody would switch.

**Boundary with PR 4:** PR 4 changes demo-mode *runtime output* and the `configure-demo` default.
This PR changes only help text. No overlapping lines.

### 4.4 New content to author

1. **Working walkthrough** in `setup.md`, ending in the readiness checklist (§4.2.2).
2. **Bridge funding subsection** with preflight (§4.2.1).
3. **Faucet reality callout** (G1, G2, G4).
4. **Slashing note**, split intent vs deployed (§4.2.4).

## 5. Proposed structure

`setup.md` — the single authoritative sequence:

```
1. Requirements (tested configuration; supported matrix pending — §4.1.1)
2. Virtual environment (+ re-activate every session)
3. Install dincli (tested configuration + why versions matter — §4.1.1)
4. Initialize + configure (demo off, network, logging)
5. Generate a key + write .env (+ chmod 600 + .env-is-cwd warning)
6. Connect wallet (--account N)
7. Configure IPFS (after wallet — B1; provider caveats per §4.1.2)
8. Fund the address — OP Sepolia faucets, or L1 + bridge with preflight; L1/L2 warning above both
9. READINESS CHECKLIST — wallet address matches funded; chain id 11155420; ETH balance non-zero;
   `dincli task explore 0 --update` succeeds (Filebase is the verified working provider on `main`)
```

`setup.md` stops there. It does **not** buy or stake — that is role-specific (§4.2.2).

`GettingStarted.md` — protocol explanation, a prerequisite block per role naming
`configure-demo --mode no` and linking to the checklist, then role operations: buy/stake/register for
aggregators and auditors, training and submission for clients.

## 6. Decisions — all resolved for authoring

Per §0, none of these gate the work. Each is resolved by describing what is true, and each is
surfaced in the PR body (§8) so Umer decides with concrete text in front of him.

| # | Question | Resolution for this PR | Raised in PR body |
|---|---|---|---|
| D1 | IPFS wording — document now or wait for PR 6? | **Document now** (§4.1.2). A reader hitting the failure deserves to know it is known | yes |
| D2 | Wrong-chain RPC — warn now or wait for PR 5? | **Warn now.** PR 5 turns it into a startup error; soften the wording then | no |
| D3 | Python version | **"Tested with", never "requires"** (§4.1.1) | yes, with D5 |
| D4 | `connect-wallet` docstring | **Folded in** (§4.3); C2–C4 flagged as beyond the literal ask | yes |
| D5 | What is the supported install? | **Do not answer it.** Document the tested configuration and route unsupported platforms to the team (§4.1.1) | **yes — prominently** |
| D6 | Role-flow restructure | **Do both** (§4.2.2): full sequence once in `setup.md`, prerequisite block naming `--mode no` in each role section | **yes — prominently** |
| D7 | Does IPFS force code into this PR? | **No — option (a).** Document reality; code fixes go to PR 6 | yes |

**Still genuinely Umer's, and deferred to him:** declaring an official supported platform/version
matrix, and the reproducibility test that would back it. That is policy, and this PR neither needs
nor pre-empts it — it only stops the docs implying an answer we cannot support.

## 7. Verification

Rev 1's plan was not isolated. `CONFIG_DIR = Path(user_config_dir("dincli"))` and `WALLET_FILE =
CONFIG_DIR / "wallet.json"` (`cli/utils.py:23,27`) are **machine-global** — a fresh directory and
venv reset neither config nor wallet.

1. **Isolate properly — and verify the isolation itself.** Fresh user account or container, or
   overridden `XDG_CONFIG_HOME` / `XDG_CACHE_HOME`. Do **not** then check `~/.config/dincli`: once
   the overrides are set those paths are no longer authoritative, so a broken override would pass
   silently. Instead: resolve the actual paths under test (`python -c "from platformdirs import
   user_config_dir, user_cache_dir; print(user_config_dir('dincli'), user_cache_dir('dincli'))"`),
   confirm **those** start absent, confirm all generated state lands inside the isolated location,
   and confirm no machine-global wallet or provider config is read.
2. **Test the whole prerequisite boundary**, not just `connect-wallet`: run through
   `task explore 0 --update` and `task gi show-state 0`. Stopping earlier is exactly what hid G5.
3. **Test install Options A and B separately** — they are mutually exclusive; one verbatim run
   cannot exercise both. Confirm S2 is broken before removing it.
4. **IPFS — one positive test, three negative characterization tests.** Rev 3 listed three cases as
   if all could pass; on `main` they cannot (§4.1.2).
   - **Filebase — positive.** Configure, upload, retrieve, and `dincli task explore 0 --update`, all
     succeeding. This is the provider the readiness checklist names as verified working.
   - **Node provider — negative.** Set `IPFS_API_URL_*` in `.env`; confirm and **record** the current
     retrieval failure; confirm the docs label it unavailable on `main`.
   - **`custom` — negative.** Confirm it stays unsupported: no `--service-path` setter, plus the
     `importlib` `NameError`.
   - **Stale provider — limitation test.** Confirm provider state is machine-global and that no
     supported CLI command recovers from it. Reset the isolated test config **manually** between
     cases, and do not describe that reset as a user-facing recovery path.
5. **Record during validation:** L1 and L2 chain ids, connected wallet address, `dincli --version`,
   full `pip freeze`, OS and version, architecture, CPU model, torch/numpy versions, whether CUDA was
   available or used, and any thread/determinism settings. `pip check` is recorded as
   dependency-consistency evidence only — it says nothing about reproducibility.
6. **Paste-test S12** in a real shell.
7. **Help text (§4.3):** run `dincli system connect-wallet --help` against the edited tree and read
   the rendered output — Typer reflows docstrings, so the diff is not what the user sees.
8. **No behavioural drift:** `git diff dincli/` must contain only docstring and `help=` lines.
9. **Placeholder sweep — fixed pattern.** Rev 1's `<[a-z_]*>` misses hyphens, including `<model-id>`
   and `<start-client-index>` at `GettingStarted.md:423-429`. Use `grep -rnE '<[A-Za-z0-9_-]+>'
   Documentation/` and triage shell vs non-shell contexts.
10. **Automated render + link check** rather than manual preview alone.
11. **Funded steps** (buy, stake, register, bridge) are covered by the recorded run; re-running costs
    real funds. Cite it per §10 instead of re-executing.

## 8. PR description outline

- Link discussion #79 **and Umer's specific comment anchor**, not just the discussion
- State: documentation and CLI **help text** only — no behavioural change, no version changes
- Table of changes → finding ID → confirmation in Umer's comment
- Flag C2–C4 as beyond the literal ask, easy to drop
- Raise the **`importlib` `NameError`** (§4.1.2) as a new bug for PR 6
- Note for Umer: the version lives in **four** places — `pyproject.toml:7`, `dincli/__init__.py:1`
  (feeds `dincli --version`), the `dist/` wheel filename, and `setup.md:30,32`
- Separate what was verified live in this PR's validation run from what is carried from the
  2026-08-09/10 run

### 8.1 The two things to put at the top of the PR body

Both are cases where the diff answers a question that is formally Umer's. Lead with them so he can
push back without hunting.

**1. Install / versions (D5 + D3).** Say plainly: this PR does *not* declare a supported
configuration — it documents the one that was tested and routes everyone else to the team. Then ask
the real question, with the evidence attached: `cache_model_0/requirements.txt` is a 121-line
Linux/CUDA freeze including 13 `nvidia-*` packages, `triton`, `pytest` and `ruff`, so it cannot be
the cross-platform lock, and it contradicts the CPU-only direction from his own reproducibility
answer. The wheel pins `torch==2.6.0` but leaves `numpy>=2.2.0` open. **What should a new aggregator
actually install?** This is the same question as his open pinning item, now with a concrete starting
point rather than an abstract ask.

**2. Role-flow restructure (D6).** State the divergence up front: he asked for
`configure-demo --mode no` inside the aggregator/auditor/client sections; those sections now carry a
prerequisite block that names it and links to the full sequence, rather than a duplicated sequence.
Give the reason — the role flows are currently **unexecutable** (`task explore 0` at Step 1 needs the
wallet, RPC and IPFS that Step 3 sets up), and the duplication is what let B2 happen. Note it is
cheap to reverse: three prerequisite blocks, not a re-architecture.

Also flag, lower down: the **`importlib` `NameError`** (§4.1.2) as a new bug for PR 6, and the
**pinned-stack deadline** — the other four GI 2 aggregators need to converge on a stack before T1
opens, and this node runs Python 3.13.5.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Large diff on two heavily-read docs invites bikeshedding | Ship structure and safety fixes; avoid rewording correct prose |
| The §4.2.2 restructure is a bigger change than Umer asked for | Lead the PR body with it (§8.1); keep it cheap to reverse (three prerequisite blocks) |
| Docs describe behaviour PRs 2–6 will change | §6 tracks every coupling; prefer wording valid before *and* after (S13 is the model) |
| Conflicts with Umer's release commit | This PR touches no version state |
| Touching a `.py` makes the PR look behavioural | Confine to docstrings/`help=`; verification step 8 proves it; say so in the PR body |
| The walkthrough encodes one host's experience | Present as tested configuration, not the only one; flag the 3.13.5-vs-3.12.3 gap |
| `GettingStarted.md` last changed 2026-06-12 — others may have in-flight edits | Check open PRs touching `Documentation/` before opening |

## 10. Evidence appendix — a merge gate, not a nicety

> **"Ready to author" is not "ready to merge."** Evidence-dependent statements cannot be finalised
> until this appendix is assembled. Any claim that cannot be evidenced is either **removed** or
> **labelled explicitly as a single observed run** — never published as a general property.

Applies to every number and URL in the funding, faucet, conversion-rate, timing, and slashing copy.

The review correctly noted that the supporting artifacts are not reviewable from inside this repo:
`aggregator-onboarding-report.md` and `aggregator-onboarding-post.md` live in the **parent** directory
(`/home/santi/InfiniteZero/`), not in `DevNet/`. Assemble before authoring:

- Bridge deposit: L1 tx hash, gas used, L1 and L2 balances before/after, timestamps
- `buy` / `stake` / `register` tx hashes, and the on-chain `isDINAggregator` read
- Environment fingerprint: OS/arch, Python, `pip freeze`, `dincli --version`
- Faucet attempts: which gate was hit on each of the six, with dates
- Permalinks for every claim attributed to Umer — comment anchors, not the discussion URL

Claims that cannot be evidenced get dropped from the docs or marked as observed-once.

## 11. Where the reviews needed correcting

Recorded so later revisions do not re-litigate.

**From the rev 4 audit:**

- **"The Google Cloud OP Sepolia URL is nonexistent."** Not provable from here — `cloud.google.com`
  soft-404s (a deliberately bogus path returns a near-identical 200 HTML shell) and the faucet UI is
  JS-rendered behind sign-in. The **conclusion is adopted anyway**, on stronger grounds: the recorded
  run never used that URL, so publishing it would recommend something untested (§4.2.5).

**From the rev 2 review:**

- **"Neither file is present in the workspace."** Both exist in the parent directory. The underlying
  ask — an evidence appendix with permalinks — is right, and is now §10.
- **"A wheel-only user does not have `cache_model_0/requirements.txt`."** The walkthrough `wget`s it,
  so access is solved. The *real* objection stands and is the blocking one: it is a CUDA/dev freeze,
  unsuitable as a cross-platform lock.
- **"`--account` is too broad"** — correct, but note the wheel already pins `torch==2.6.0` exactly
  (`pyproject.toml:23`); only `numpy>=2.2.0` is loose. So `--no-deps` matters less for torch than
  rev 1 implied, and more for numpy.
- **Python `>=3.9` cited as evidence against requiring 3.12.3** — true, but that floor is itself the
  B4 bug being backported in PR 3, so it is weak evidence. The conclusion is right for other reasons.
- **Minor line-number drift** in the review: `updateDinPerEth` is `:81` (not `:80`), `slashAmount`
  `:522` (not `:518`), `MIN_STAKE` `:28` (not `:27`), the slash guard `:119` (not `:115`). Substance
  unaffected.

## 12. Follow-ups this PR does not close

- PR 2 whitelist (also needed on `develop` — Umer scoped it `main`-only)
- PR 5 chain-id: belongs in `get_w3()` (`cli/utils.py:198`), not `get_en_w3_account_console()`, which
  is skipped for whitelisted subcommands
- PR 6 IPFS GET, both branches — **plus the `importlib` `NameError`** (§4.1.2) and making
  `ipfs node` selectable (§4.1.2)
- `dincli` bridge command — after this PR settles how funding is described
- Non-PR: raise the pinned-stack question in-thread so the other four GI 2 aggregators see it before
  T1 opens. This node is on Python 3.13.5 — a consensus-divergence risk with a deadline (and, today,
  a GI-wedging risk rather than a slashing one; see §4.2.6)
