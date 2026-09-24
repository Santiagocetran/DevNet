# CI next steps, 1 of 4 — Dependabot: stop the pins from rotting silently

**Base:** `upstream/main` on `InfiniteZeroFoundation/DevNet` (see §1 — **not** `develop`)
**Branch:** `ci/dependabot`, cut from `main`
**Origin:** `Plans/archive/ci-cd-phase1-plan.md` §7, follow-up bullet 6 ("`CODEOWNERS`, a PR template, and
Dependabot for `github-actions` and `npm` … Dependabot is what stops the pinned SHAs in §2.9 from
silently rotting")
**Status:** rev 3 — implementation scope unchanged; priority reconciled with the 2026-09-24 push-CI plan.

> **Rev 3 changelog (2026-09-24, Astra audit of `ci-next-05`).** §0 no longer recommends Dependabot
> as the first CI follow-up. The agreed first PR is `ci-next-05`'s `develop` push trigger because recent
> landed revisions have no CI record. Dependabot remains independent and can follow immediately.

> **Rev 2 changelog.**
>
> - **BLOCKER: rev 1 put the config on the wrong branch** (§1). It proposed cutting `ci/dependabot`
>   from `develop` and merging it there. The repository's default branch is **`main`**
>   (`git ls-remote --symref upstream HEAD` → `ref: refs/heads/main`), and GitHub only reads
>   `.github/dependabot.yml` from the default branch. Rev 1's config would have sat in `develop` doing
>   **nothing**, indefinitely, with no error anywhere. Rewritten around `main` + `target-branch`.
> - **The OpenZeppelin policy contradicted the config** (§3, §5). Rev 1 argued at length that OZ
>   updates must not arrive as routine dependency maintenance — then used `patterns: ["*"]` on both npm
>   groups, which sweeps up `@openzeppelin/contracts` in *both* trees plus `contracts-upgradeable`,
>   `upgrades-core` and `hardhat-upgrades`. Verified in both `package.json` files. Now handled with
>   explicit `ignore` rules.
> - **The pip discovery claim was outdated** (§4). Rev 1 asserted `.github/constraints-ci.txt` is
>   outside pip discovery because the filename is not `requirements*.txt`. GitHub's pip updater
>   supports dependencies in `.txt` files generally. A pip entry is now included, with first-run
>   verification rather than an assumption either way.
> - **`FOUNDRY_VERSION` is unmanaged and rev 1 implied otherwise** (§4.3). The `github-actions`
>   updater manages `uses:` references, not arbitrary `env:` values.
> - **Corrections:** a lowered `open-pull-requests-limit` defers updates until capacity frees up, it
>   does not drop them (rev 1 said "silently drops"); `openzeppelin-foundry-upgrades` is tooling, not
>   an inheritance base (§3).

---

## 0. Where this sits

| # | Plan | Needs someone else's judgement? | Blocking on anything? |
|---|---|---|---|
| **1** | **`ci-next-05-develop-push-and-completion-plan.md` — push coverage** | **No** | **No** |
| 2 | **This one — Dependabot** | **No** | **No; independent of push coverage** |
| 3 | `ci-next-02-lint-promotion-plan.md` | No | Needs BL-25 + issue from the timestamp plan filed first (for the cross-reference only) |
| 4 | `ci-next-03-timestamp-escalation-plan.md` | **Yes — a Solidity/security reviewer** | No |
| 5 | `ci-next-04-forge-fmt-plan.md` | No | No |

`ci-next-05` is first by the 2026-09-24 decision, not a technical dependency: this Dependabot PR can
be prepared in parallel and does not wait for lint, formatting or integration.

---

## 1. The branch question — settle this before writing any YAML

**The default branch is `main`.** Verified:

```
$ git ls-remote --symref upstream HEAD
ref: refs/heads/main    HEAD
```

Two consequences, and rev 1 got both wrong:

1. **`.github/dependabot.yml` must exist on `main`.** GitHub reads the config from the default branch
   only. A copy on `develop` and nowhere else is inert — and it fails *silently*, which is the worst
   property a config file can have. Nothing turns red; Dependabot simply never runs.
2. **Without `target-branch`, Dependabot opens its PRs against `main`.** That is wrong for this repo:
   `ci.yml` triggers on `pull_request: branches: [develop]`, so a PR targeting `main` gets **no CI at
   all**. An unverified dependency bump landing straight on the default branch is worse than no
   Dependabot.

So every version-update entry sets `target-branch: develop`.

### 1.1 The asymmetry nobody should discover by surprise

`target-branch` applies to **scheduled version updates**. Dependabot **security updates** — the ones
triggered by an advisory — do not honour it and open against the default branch. This repo's CI does
not run on `main` PRs at all (archived Phase 1 plan §2.8 scoped Phase 1 to `develop` deliberately).

**Therefore: a Dependabot security update will arrive on `main` with zero automated verification.**
That is not a reason to skip this PR — it is the pre-existing state, and today those advisories arrive
as *nothing at all*. But it must be written into the PR body so the first person to see one knows to
check it by hand rather than trusting a green tick that was never going to appear.

It is also a concrete argument for the `push`/`main` coverage follow-up in §8.

---

## 2. Why

Phase 1 (#118) pinned everything deliberately, and that was right. From the merged `ci.yml`:

- `actions/checkout` → `3d3c42e5aac5ba805825da76410c181273ba90b1` (`# v7.0.1`)
- `actions/setup-node` → `820762786026740c76f36085b0efc47a31fe5020` (`# v7.0.0`)
- `foundry-rs/foundry-toolchain` → `908c540300062bd5a7e473851cdb4282204cee09` (`# v1.9.1`)
- `actions/setup-python` → `5fda3b95a4ea91299a34e894583c3862153e4b97` (`# v7.0.0`)
- `FOUNDRY_VERSION: v1.7.1`, pinned rather than `stable`

The reasoning (archived plan §2.9) still holds: an upstream release must not change compilation output
or CI behaviour on an unrelated PR.

The unpaid cost is that **a pin is a decision that stops being re-examined the moment it is made**.
Dependabot does not keep things current; it keeps the staleness *visible and attributable* — a small
PR appears, and a human either merges it or explicitly doesn't.

---

## 3. OpenZeppelin — the policy has to match the config

Rev 1 argued, correctly, that an OZ update is a contract-security event rather than routine dependency
maintenance: the three OZ submodules and npm packages collectively affect **contract source,
deployment, and upgrade validation**, and a green CI gate proves the tests pass — not that the proxy
storage layout is still compatible. That distinction is the whole reason `npm ci` + `Upgrades.validateImplementation`
exist in this repo (CLAUDE.md; archived plan §2.2).

Rev 1 then used `patterns: ["*"]`, which sweeps up exactly those packages. Verified:

```
foundry/package.json   dependencies: @openzeppelin/contracts ^5.6.1
                                     @openzeppelin/upgrades-core ^1.46.0
hardhat/package.json   dependencies: @openzeppelin/contracts ^5.3.0
                                     @openzeppelin/contracts-upgradeable ^5.3.0
              devDependencies:       @openzeppelin/hardhat-upgrades ^3.9.1
```

Note also the two trees are on **different** `@openzeppelin/contracts` majors-in-minor (`^5.6.1` vs
`^5.3.0`) — another reason these should never be bumped by a grouped autopilot PR.

**Correction: `ignore`, not merely "exclude from the group."** Removing them from a catch-all group
does not stop Dependabot opening *separate* PRs for them — it just unbundles them. To make "OZ updates
are manual" real, they need explicit `ignore` entries. That is what §5 does.

**Also corrected from rev 1:** `openzeppelin-foundry-upgrades` (submodule) and `@openzeppelin/upgrades-core`
/ `@openzeppelin/hardhat-upgrades` (npm) are **tooling**, not contract inheritance bases. Only
`openzeppelin-contracts` and `openzeppelin-contracts-upgradeable` are inherited from. The tooling still
belongs under the manual policy — it is what performs upgrade validation, so a silent change to it
changes what "validated" means — but describe it accurately.

### 3.1 Git submodules — still out of this PR

`.gitmodules` pins four by commit: `forge-std`, `openzeppelin-contracts`,
`openzeppelin-contracts-upgradeable`, `openzeppelin-foundry-upgrades`. Dependabot's `gitsubmodule`
ecosystem would work, and three of the four fall under the manual policy above anyway.

Add it later, monthly, with a distinct label and a written storage-layout review rule. It is its own
small piece of work with its own reasoning and should not ride inside a config PR.

---

## 4. Python

### 4.1 `pyproject.toml` runtime dependencies — nothing useful to do yet

All open-ended lower bounds (`typer>=0.9.0`, `web3>=6.0.0`, …). Against `>=` constraints there is
usually nothing for Dependabot to bump — the constraint already admits the new version. The archived
plan §7 flags the real problem ("worth a deliberate policy"); that decision is a prerequisite here, not
something Dependabot substitutes for. **No `pip` entry for the repo root.**

### 4.2 `.github/constraints-ci.txt` — include it, then verify

```
torch==2.6.0
pytest==9.1.1
ruff==0.16.4
```

Exact pins, same rot problem as the action SHAs, and **more load-bearing than they were last week** —
`ci-next-02` makes `ruff==0.16.4` a *blocking* gate, so a stale pin there is a gate nobody is
re-examining.

Rev 1 asserted this file is outside pip discovery because the filename is not `requirements*.txt`.
That assertion was wrong to make: the pip updater supports dependencies in `.txt` files generally, so
a constraints file at this path plausibly *is* processed. Equally, "supported in principle" is not
proof of how a constraints-only file with no direct requirements is handled.

**So: include the entry, and make the first server-side run the verification** (§6 step 3). If it
produces updates, good. If it reports nothing to update, say so in `CONTRIBUTING.md` and treat the
three pins as hand-managed. Either outcome is fine; guessing is not.

### 4.3 `FOUNDRY_VERSION` is not managed by any of this

```yaml
env:
  FOUNDRY_VERSION: v1.7.1
```

The `github-actions` updater manages `uses:` references. It does **not** parse arbitrary `env:` values,
so this pin is invisible to Dependabot no matter how the config is written — and it is the pin that
governs both the Solidity compiler and the diagnostics the lint gate parses (archived plan §2.9).

Treat it as an explicitly manual pin: name it in `CONTRIBUTING.md`, give it a review cadence (quarterly
is plenty), and re-measure the lint output when it moves. Anything more automatic needs tooling with
regex/custom-version support, which is not worth introducing for one line.

---

## 5. Changes

One new file, **on `main`**. No changes to `ci.yml`.

### `.github/dependabot.yml`

```yaml
version: 2

# This file must live on the DEFAULT branch (main) — GitHub reads it nowhere else.
# Every entry targets `develop`, because ci.yml only runs on pull_request against
# develop; a PR opened against main would get no CI at all.
#
# NOTE: target-branch applies to scheduled version updates only. Dependabot
# SECURITY updates ignore it and open against main, where no CI runs. Review
# those by hand until main has its own gate.

updates:
  # The four actions in ci.yml are SHA-pinned (see ci.yml, and the archived Phase 1
  # plan 2.9). Dependabot bumps the SHA and rewrites the trailing `# vX.Y.Z`
  # comment, so the pinning discipline survives the update.
  #
  # Does NOT cover env.FOUNDRY_VERSION — that is a manual pin. See CONTRIBUTING.md.
  - package-ecosystem: github-actions
    directory: /
    target-branch: develop
    schedule:
      interval: weekly
    labels:
      - dependencies
    commit-message:
      prefix: "ci"
    groups:
      actions:
        patterns:
          - "*"

  # Both npm trees are exercised by CI: `npm ci` runs in foundry/ before
  # `forge test` (OZ upgrades-core FFI race) and in hardhat/ before compile.
  # Grouped deliberately: ungrouped, hardhat alone produces enough weekly PRs to
  # train everyone to ignore the label.
  #
  # @openzeppelin/* is IGNORED, not merely ungrouped. Those packages are the
  # contract inheritance base (contracts, contracts-upgradeable) and the upgrade
  # validation tooling (upgrades-core, hardhat-upgrades). A green gate proves the
  # tests pass, not that proxy storage layout is still compatible, so these are
  # bumped by hand with a storage-layout check. Ungrouping alone would still open
  # separate PRs for them.
  - package-ecosystem: npm
    directory: /foundry
    target-branch: develop
    schedule:
      interval: weekly
    labels:
      - dependencies
    commit-message:
      prefix: "chore"
    ignore:
      - dependency-name: "@openzeppelin/*"
    groups:
      foundry-npm:
        patterns:
          - "*"

  - package-ecosystem: npm
    directory: /hardhat
    target-branch: develop
    schedule:
      interval: weekly
    labels:
      - dependencies
    commit-message:
      prefix: "chore"
    ignore:
      - dependency-name: "@openzeppelin/*"
    groups:
      hardhat-npm:
        patterns:
          - "*"

  # The CI tool pins (torch, pytest, ruff). ruff becomes a BLOCKING gate in the
  # lint-promotion PR, so this pin stops being cosmetic. Whether a constraints-only
  # .txt is actually processed is verified on the first run — see the plan 6.3.
  - package-ecosystem: pip
    directory: /.github
    target-branch: develop
    schedule:
      interval: weekly
    labels:
      - dependencies
    commit-message:
      prefix: "ci"
```

**Deliberately omitted:** `gitsubmodule` (§3.1), `pip` at the repo root (§4.1).

**Deliberately not set:** `open-pull-requests-limit`. The default (5 per ecosystem) is already
conservative with grouping on. Correcting rev 1: a lower limit **defers** updates until capacity frees
up rather than dropping them — the objection is that it hides work, not that it loses it.

**Labels are a prerequisite, not a detail.** GitHub silently ignores an undefined custom label rather
than failing the update, so a typo here costs nothing visible and buys nothing. Only `dependencies` is
used above; **confirm it exists before merge** and create it if not. `ci` was dropped from rev 1 —
reportedly absent from the repo, and not worth a second prerequisite for cosmetic grouping.

---

## 6. Verification

Dependabot config runs server-side; it cannot be tested locally. In order:

1. **Schema.** GitHub validates `dependabot.yml` on push and reports errors under Insights →
   Dependency graph → Dependabot. A malformed file surfaces **only there** — it will not turn any PR
   red. **Look at that tab explicitly after merge**, because a broken config is otherwise
   indistinguishable from a quiet week.
2. **It is on `main`.** `git show main:.github/dependabot.yml` must succeed. This is the failure mode
   rev 1 would have shipped, so check it first.
3. **Trigger the first run manually** from the Dependabot tab rather than waiting a week. Per
   ecosystem, expect either PRs or "up to date"; an error banner is a fail. **Record what the `pip`
   entry does with `.github/constraints-ci.txt`** — this is the §4.2 verification, and the answer goes
   into `CONTRIBUTING.md` either way.
4. **The first real PR targets `develop`, not `main`,** and shows a `CI OK` check. Both halves matter:
   the target proves `target-branch` took effect, the check proves the PR is actually gated.
5. **No `@openzeppelin/*` PR appears.** If one does, the `ignore` entry is wrong — fix before it is
   merged on autopilot, which is the exact outcome §3 exists to prevent.

---

## 7. PR body outline

> **Title:** `ci: add Dependabot for github-actions, npm and CI pins`
> **Target: `main`** (not `develop`) — see below.
>
> Phase 1 (#118) SHA-pinned all four actions and pinned `FOUNDRY_VERSION` so an upstream release
> cannot change CI behaviour on an unrelated PR. That reasoning holds — but nothing notices when a pin
> goes stale, so the pins quietly stop being decisions and become defaults.
>
> **Why this targets `main`:** GitHub reads `.github/dependabot.yml` from the default branch only, and
> this repo's default branch is `main`. A copy on `develop` would be inert, silently. Every entry then
> sets `target-branch: develop` so the generated PRs land where `ci.yml` actually runs.
>
> **One asymmetry to know about:** `target-branch` covers scheduled version updates. Dependabot
> *security* updates ignore it and open against `main`, where no CI runs today. Those need a manual
> check until `main` has its own gate — flagging it rather than letting someone discover it while
> looking at a PR with no status checks.
>
> **Covers:** GitHub Actions · both npm trees (`foundry/`, `hardhat/`) grouped one PR per ecosystem per
> week · `.github/constraints-ci.txt` (`torch`, `pytest`, `ruff` — `ruff` becomes a blocking gate in
> the lint PR, so that pin stops being cosmetic).
>
> **`@openzeppelin/*` is explicitly ignored in both npm trees.** Those are the contract inheritance
> base and the upgrade-validation tooling; a green gate proves the tests pass, not that the proxy
> storage layout is still compatible. They get bumped by hand with a storage-layout check. (Note the
> two trees are on different `@openzeppelin/contracts` versions — `^5.6.1` vs `^5.3.0` — which is
> another reason not to let a grouped PR reconcile them.)
>
> **Not covered, deliberately:** git submodules (same policy, worth its own monthly config and review
> rule) · `pyproject.toml` runtime deps (open-ended lower bounds; nothing to bump until that policy is
> settled) · **`env.FOUNDRY_VERSION`**, which the actions updater cannot see at all and stays a manual
> pin.
>
> No changes to `ci.yml`. Nothing here can turn a PR red; a malformed config surfaces in the Dependabot
> tab, which I'll check after merge along with what the pip entry makes of the constraints file.

---

## 8. Follow-ups this deliberately leaves open

- **CI coverage for `main`** — currently zero. This PR makes it matter more, because security updates
  land there unverified (§1.1). Pairs with the post-merge `push` trigger on `develop`.
- **`gitsubmodule` updates**, monthly, distinct label, written storage-layout review rule (§3.1).
- **Record the `pip` / constraints-file outcome** from §6 step 3 in `CONTRIBUTING.md`, whichever way it
  goes.
- **`FOUNDRY_VERSION` review cadence** in `CONTRIBUTING.md` (§4.3), plus a note to re-measure lint
  output when it moves.
- **Runtime dependency pinning policy** for `pyproject.toml` — archived plan §7, unchanged.
- **`CODEOWNERS` and a PR template** — the other two items in that §7 bullet.
