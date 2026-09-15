# CI/CD Phase 1 — implementation plan

**Base:** `develop` on `InfiniteZeroFoundation/DevNet`
**Origin:** [discussion #74](https://github.com/InfiniteZeroFoundation/DevNet/discussions/74) (revised 2026-08-26 after the audit below)
**Status:** rev 3 — every claim below was verified by running it against `develop` @ `5fc1485`. Rev 1 (7 findings) and rev 2 (3 findings plus 2 editorial corrections and 1 optional hardening) were reviewed; all are fixed here (see changelog). Both remaining decisions (§8) affect PR 3 only; nothing blocks PR 1, PR 2 or PR 4.

> **Rev 3 changelog.** A review of rev 2 found three issues plus two editorial corrections and
> one optional hardening. All were verified and **all hold**:
>
> - **A `TODO` suppression would have promoted an unresolved security question to a permanent
>   green gate** (§2.7, §3.3, §8). Rev 2 let PR 3 suppress the 4 `block-timestamp` findings with a
>   `TODO` if the review ran long. The two promotions are now decoupled: `ruff` becomes blocking in
>   PR 3 regardless; `forge lint` becomes blocking only once those findings are fixed or explicitly
>   accepted with a written rationale.
> - **The lint parser validated JSON syntax, not the diagnostic schema** (§2.7, §3.2). It skipped
>   unrecognised `$message_type` values and treated a diagnostic with a missing `level` as passing,
>   so both `{"$message_type":"changed-schema","level":"warning"}` and `{"$message_type":"diagnostic"}`
>   passed a gate meant to fail closed. Now rejected, with committed tests.
> - **The marker helper ignored subprocess failure** (§3.1). `_collect()` returned stdout without
>   checking `returncode` or setting a timeout. Both added.
> - **Editorial:** the status line mis-assigned the §8 decisions across PRs 3 and 4 (both are PR 3;
>   PR 4 has none), and §0 said every PR waits for its predecessor when PR 4 only needs PR 2.
> - **Hardening taken:** the fence parser now tracks the opening fence's character and length
>   instead of toggling on any run of three.

> **Rev 2 changelog.** A review of rev 1 found seven issues. All seven were re-verified against the
> tree and **all seven hold**, including two that would have defeated the intended rollout:
>
> - **Branch topology contradicted the rollout order** (§0 new). Rev 1's header said all three
>   branches came off `develop` @ `5fc1485` while §2 required PR 1 to be merged first. Rewritten as
>   an explicit sequential topology.
> - **The marker-hook verification verified nothing** (§2.6, §3.1, §4.3). `259/133` is produced
>   whether the hook is correct, absent, or a no-op, because the four files already self-mark. The
>   hook is now load-bearing (the `pytestmark` lines are removed), and a committed test asserts the
>   path classification.
> - **The Foundry binary was left floating** (§2.9) on `version: stable`, while every measurement
>   and the proposed lint gate assume 1.7.1. Now pinned.
> - **The proposed `forge lint` gate failed open** (§2.7). Replaced with `forge lint --json` and a
>   committed fail-closed parser. Two traps found while testing it are documented there.
> - **`exclude_lints` is global** (§3.3, §8) and would have suppressed `unsafe-typecast` in `src/`
>   to serve a test-only convention. Now localized.
> - **The link checker overstated its contract** (§3.2). Narrowed and given fence handling.
> - **Dependency pinning was partial** (§2.4). Torch and the test extra are now pinned via a CI
>   constraints file.

---

## 0. Branch topology

**Sequential, not stacked.** PRs 1–3 run in order, each cut from `develop` after its
predecessor merges. PR 4 is independent and needs only PR 2:

| PR | Branch | Cut from | Opens after |
|---|---|---|---|
| 1 | `ci/phase1-prep` | `develop` @ `5fc1485` | now |
| 2 | `ci/phase1-workflow` | `develop` after PR 1 merges | PR 1 merged |
| 3 | `ci/phase1-lint-cleanup` | `develop` after PR 2 merges | PR 2 merged |
| 4 | `ci/phase1-forge-fmt` | `develop` after PR 2 merges | PR 2 merged (independent of PR 3) |

**Why this ordering is a constraint, not a preference.** The workflow added by PR 2 runs *on PR 2
itself*. If PR 2 were cut from `5fc1485`, its own first run would fail because `[project.optional-dependencies]`
would not exist (so `pip install -e ".[test]"` installs no pytest), the broken documentation link
would still be present, and the marker hook would be absent. "PR 2's first run is green" is only
true if PR 1 is already on `develop`.

PR 4 touches only formatting and PR 3 only semantics, so they are order-independent; whichever
lands second absorbs a trivial rebase.

Stacking (PR 2 targeting PR 1's branch, retargeted after merge) would also work and shortens the
critical path, at the cost of a retarget step per PR and review diffs that shift under reviewers.
Sequential is recommended because these PRs are small and land quickly; use stacking only if PR 1
stalls in review.

---

## 1. Why

`develop` has no `.github/` at all (confirmed: the upstream contents API returns 404). Every check
is manual and documented only in prose. The consequences are ordinary and expensive: contributors
cannot self-verify, regressions surface at review time, and reviewer attention is spent on things a
machine should catch.

The checks themselves are not the problem — they already exist and they are fast. Measured on
`develop`:

| Suite | Result | Wall time |
|---|---|---|
| `forge test` | 162 passed, 0 failed | 7.1s |
| `npx hardhat test` | 32 passing | 3.7s |
| `pytest -m "not integration"` | 259 passed, 133 deselected | 27.3s |
| `forge build --force` (cold, `via_ir`) | success | 45.2s |

The whole gate is roughly a minute of compute. Phase 1 is not new infrastructure; it is stopping
the manual execution of tests that already pass.

---

## 2. Design decisions

### 2.1 Three setup steps are load-bearing and none of them are obvious

Each was found by running the proposed commands in a state resembling a fresh runner. Any one of
them, if missed, produces a red or flaky gate whose failure has nothing to do with the
contributor's diff — the fastest possible way to teach a project to ignore its own CI.

### 2.2 `foundry/` needs Node and `npm ci` **before** `forge test` — reproduced

`forge test --match-contract UpgradeValidationTest` fails today on a machine without
`foundry/node_modules`:

```
Suite result: FAILED. 5 passed; 1 failed; 0 skipped
[FAIL: Failed to run upgrade safety validation: npm warn exec The following package was not
found and will be installed: @openzeppelin/upgrades-core@1.46.0
npm error code EEXIST
npm error path ../node-gyp-build/optional.js
npm error EEXIST: file already exists, symlink ...
] test_validateImplementation_DinCoordinator()
```

**Mechanism.** `Upgrades.validateImplementation` (from `openzeppelin-foundry-upgrades`) shells out
over FFI to `npx @openzeppelin/upgrades-core`. `forge test` runs the six test functions in
parallel; each invokes `npx`; `npx` finds the package absent and races the others installing it
into the shared npx cache. This is why `foundry.toml` carries `ffi = true`, `ast = true`,
`build_info = true`, `extra_output = ["storageLayout"]` and `fs_permissions` for `out/`.

**Fix.** `npm ci` in `foundry/`. `foundry/package.json` already pins
`@openzeppelin/upgrades-core: ^1.46.0`, so nothing new is declared. Verified after:

```
Ran 6 tests for test/UpgradeValidation.t.sol:UpgradeValidationTest
Suite result: ok. 6 passed; 0 failed; 0 skipped; finished in 852.58ms
```

852 ms versus 8.33 s — the npx fetch was also most of the runtime.

**Scope note.** This is not confined to the upgrade tests. `foundry/script/DeployPlatform.s.sol`,
`foundry/script/UpgradePlatform.s.sol` and `foundry/test/DeployPlatform.t.sol` all use `Upgrades`,
so plain `forge test` needs it too.

**Security dividend.** With `ffi = true`, a test can execute arbitrary commands on the runner. The
exposure is bounded — `pull_request` (not `pull_request_target`) gives forks a read-only token and
no secrets, and no check here needs a secret (§2.9) — but a test that *downloads and executes a
package at test time* is a supply-chain hole regardless. `npm ci` resolves from the committed
lockfile and closes it. One fix, two problems.

### 2.3 Checkout must be `submodules: recursive`

All four Solidity dependencies are git submodules (`forge-std`, `openzeppelin-contracts`,
`openzeppelin-contracts-upgradeable`, `openzeppelin-foundry-upgrades`) and `foundry/remappings.txt`
maps `@openzeppelin/contracts/` → `lib/openzeppelin-contracts/contracts/`. Without submodules
nothing compiles. Use `fetch-depth: 1`: `.git` is 173 MB and the OZ submodules dominate it.

### 2.4 `torch` is required, undeclared, and the local pass is an illusion

`tests/test_scoring.py` and `tests/test_cache_client_dp.py` both `raise ImportError` without torch
— they load `cache_model_0/services/scoring.py` and `client.py` via `spec_from_file_location`, and
those modules import `torch`, `torch.nn`, `torch.optim` and `torch.utils.data`.

torch is declared **nowhere**: not in `pyproject.toml` `dependencies`, not in
`dincli/requirements.txt`, and there is no `[project.optional-dependencies]` group.

It passes locally only because `.venv` was created with `--system-site-packages`:

```
.venv/pyvenv.cfg:  include-system-site-packages = true
torch resolves to:  ~/.local/lib/python3.12/site-packages/torch  (2.6.0+cu124)
footprint:          1.6 GB torch + 2.7 GB nvidia
```

This is precisely the class of defect CI exists to expose, and it is worth naming in the PR body.

**Fix.** Declare a `test` extra, and in CI install torch from the CPU index first
(`torch-2.6.0+cpu-cp312` is 178 MB by `content-length`, against ~4 GB for the default CUDA stack).
`python -m pip install -e ".[test]"` then sees torch satisfied and does not re-resolve it.

**Pin it, or the validated environment drifts without a repository change.** Lower bounds in the
extra (`torch>=2.6`) plus a floating `pip install torch` in the workflow mean a future Torch release
silently becomes the tested configuration. Keep the extra's bounds permissive — it is a library
extra and over-pinning it would fight consumers — and pin CI separately with
`.github/constraints-ci.txt`:

```
torch==2.6.0
pytest==9.1.1
ruff==0.16.4
```

Every CI install passes `-c .github/constraints-ci.txt`, so the extra and the workflow cannot drift
apart: one file names the tested versions, and bumping it is a reviewable diff. Use `python -m pip`
throughout rather than bare `pip`, so the interpreter is never ambiguous.

(The same open-ended-bounds issue applies to the existing runtime `dependencies`, and to
`dincli/requirements.txt` pinning a *different* subset at different versions. Out of scope here;
noted in §7.)

**`torchvision` is not needed.** Its only importer is `cid_services/distribute_mnist.py`, which no
unit test loads.

### 2.5 Drop the separate upgrade-validation job

`forge test` already runs those six tests — they are 6 of the 162. A dedicated job re-pays checkout,
submodules, `npm ci` and a cold `via_ir` compile for zero additional coverage. Removed from the
proposal.

### 2.6 The integration filter, the trap in hardening it, and how to actually verify it

`pytest -m "not integration"` works today: 259 selected, 133 deselected, 27.3s. All four files
under `tests/dincli/` carry `pytestmark = pytest.mark.integration`, and `[tool.pytest.ini_options]`
in `pyproject.toml` registers the marker.

The weakness is that this is per-file discipline. A new module in `tests/dincli/` that omits the
line would have CI attempt a test needing Docker, IPFS and a live chain.

**Two traps, both measured.**

*Trap 1 — the hook must be path-scoped.* A subdirectory `conftest.py` receives *every* collected
item in the session, not just its own directory's:

| Hook | Collection result |
|---|---|
| path-scoped | `259/392 collected (133 deselected)` |
| unscoped | `no tests collected (392 deselected)` |

The unscoped version turns the Python job into a permanent silent pass — the exact failure the hook
exists to prevent.

*Trap 2 — while the files self-mark, no collection count can verify the hook at all.* This is the
one rev 1 got wrong. With the four `pytestmark` lines in place, `259/133` is produced when the hook
is correct, when it is missing entirely, and when it is present but a no-op. Rev 1's §4.3 therefore
proved nothing about the hook; it only excluded the over-marking case.

**Fix: make the hook load-bearing.** PR 1 removes the four `pytestmark` declarations, so directory
membership becomes the only mechanism. Measured, in this order:

| Tree state | `-m "not integration"` |
|---|---|
| baseline (files self-mark, no hook) | `259/392 (133 deselected)` |
| `pytestmark` removed, **no hook** | `392 collected` — nothing deselected |
| `pytestmark` removed, **hook present** | `259/392 (133 deselected)` |

and with the hook as sole mechanism, `-m integration` selects `133/392` — the same set, from the
other direction. Now a regression in the hook changes the numbers, which is what makes the check a
check.

**All totals in the two tables above are pre-PR-1.** PR 1 also adds
`tests/test_integration_marker.py` (2 tests), so the totals *after* PR 1 are 261 unit / 133
integration / **394** collected. Use `133/394` as the post-merge expectation; §5 tracks the running
count.

**Belt and braces.** pytest exits **5** on total deselection (verified) rather than 0, so even a
future re-broken hook fails CI instead of passing silently.

### 2.7 Both lint checks ship advisory, and here is the arithmetic

**`forge lint` cannot currently fail.** Verified exit codes:

| Command | Exit |
|---|---|
| `forge lint` | 0 |
| `forge lint --severity high` | 0 |
| `forge lint --severity high med` | 0 |
| `forge fmt --check` | 1 |

It reports 21 findings — 17 `unsafe-typecast` in `test/DinValidatorStake.t.sol`, 4
`block-timestamp` in `src/DinValidatorStake.sol` — and exits 0 for all of them. Marking it
*required* as-is would add a check that can never fail: worse than no check, because it
manufactures assurance. (Note also that `forge build` on forge 1.7.1 already prints this output, so
a separate invocation is partly duplicative — it is kept for a distinct, greppable job log.)

**Do not gate on scraped human output.** Rev 1 proposed
`test -z "$(forge lint 2>&1 | grep -E '^(warning|error)\[')"`. That fails *open*: if `forge lint`
crashes or rejects its arguments, no line matches, `grep` emits nothing and `test -z` succeeds. Two
concrete traps confirmed while testing the replacement:

- **`--json` is mutually exclusive with `--color`.** `forge lint --json --color never` exits **2**
  with `error: the argument '--json' cannot be used with '--color <COLOR>'` and emits no
  diagnostics. Under the rev 1 wrapper that is a silent pass.
- **`--json` writes diagnostics to stderr, not stdout.** `forge lint --json 2>/dev/null` yields 0
  lines; `forge lint --json 2>&1 >/dev/null` yields 21. A gate reading stdout sees a clean tree.

`forge lint --json` emits one rustc-style diagnostic object per line, carrying `level`,
`code.code` and `spans[].file_name/line_start`. Gate on that instead, with a committed parser
(§3.2) that fails closed on **five** conditions, not three — validating the schema it was written
against, not merely that the bytes are JSON:

| Condition | Why it must fail |
|---|---|
| nonzero `forge` exit status | checked by the wrapper before parsing |
| unparseable line, or JSON that is not an object | obvious |
| unrecognised `$message_type` | forge's output format changed; skipping it is how a gate goes blind |
| diagnostic missing `level`, or a `level` outside the known set | an unclassified severity must not default to "passing" |
| diagnostic missing `code.code` | schema drift |
| any diagnostic at `warning`/`error` | the findings themselves |

The middle rows matter because a parser that ignores what it does not understand is a rubber stamp.
Both of these streams passed the rev 2 parser and now fail:

```
{"$message_type":"changed-schema","level":"warning"}
{"$message_type":"diagnostic"}
```

Empty input stays valid — it is what a clean tree looks like. Verified against the current tree:

```
test/DinValidatorStake.t.sol:379:44: warning[unsafe-typecast] typecasts that can truncate ...
::error::forge lint reported 21 finding(s) at level(s) ['error', 'warning']
    17  warning[unsafe-typecast]
     4  warning[block-timestamp]
exit=1
```

and exit 0 on a stream with no findings, exit 1 on `not json at all`. The parser has committed
tests (§3.2); running them against the rev 2 parser fails exactly the four schema cases, which is
the evidence that they test something.

**Promotion is decoupled from the Solidity findings.** `forge lint` becoming blocking depends on
resolving 4 `block-timestamp` findings in `src/`, which is a contract-security question with its own
timeline. `ruff` becoming blocking does not. PR 3 therefore promotes `ruff` unconditionally and
leaves `forge lint` advisory until those findings are **fixed or explicitly accepted with a written
rationale** (§3.3). Suppressing them with a `TODO` in order to turn the gate green would convert an
open security question into a permanent pass — the precise failure mode §2.7 exists to avoid.

**`ruff` is the largest piece of work in the whole proposal.** Measured, ruff 0.16.4:

| Rule set | Findings |
|---|---|
| ruff defaults | 593 |
| `--select F` (pyflakes) | 119 → **120 after PR 1** |
| `--select E,F --ignore E501` (proposed gate) | 125 → **126 after PR 1** |

PR 1 adds exactly one `F401` **by design**: removing `pytestmark` from
`tests/dincli/test_03_registration.py` leaves its `import pytest` unused — it is the only one of the
four files with no other `pytest.` reference (the rest retain 2, 2 and 6). Measured after PR 1:
`F401` 39 → 40, total 119 → 120, auto-fixable 106 → 107. Step 1 of §3.3 clears it with the rest.

Convergence was verified on a copy of `dincli/ tests/ cache_model_0/ cid_services/`:

```
--select F --fix   →  119 errors (106 fixed, 13 remaining)   [pre-PR-1; 120/107 after]
remaining under F  →  13 F841 unused-variable
remaining under the gate set →  19  (13 F841, 3 E402, 3 E722)
```

So the cleanup is: one auto-fix commit clearing 106, then 19 by hand. Tractable, and it does not
belong hidden behind a workflow PR.

Distribution under the gate set: `dincli/` 105, `tests/` 12, `cache_model_0/` 8, `cid_services/` 0.

**No ruff `exclude` is needed.** `dist/` is covered by ruff's defaults. `cache_model_0/services/`
contributes only 8 findings and — despite `CLAUDE.md` describing it as example rather than framework
code — it *is* under test (§2.4 loads it), so linting it is correct.

**Real bug already surfaced:** 5× `PLE2510`, unescaped literal backspace characters in
`dincli/cli/system.py` at lines 306, 314, 408, 417, 433. Fixed in PR 1 (§3.1) rather than waiting
for PR 3, because it is a defect, not a style preference.

**Pin the linter version.** An unpinned `ruff` turns every upstream release into a surprise red
build on an unrelated PR. Pin in the workflow and bump deliberately.

### 2.8 One required check, not seven — the path-filter deadlock

If individual jobs are marked required **and** narrowed with `paths:`, a PR touching only
`Documentation/` waits forever on Solidity checks that will never report. GitHub treats a required
check that never runs as pending, not skipped.

Topology: keep every job unfiltered, and add a `ci-ok` job with `if: always()`, `needs:` all
others, that fails unless every dependency succeeded. **`ci-ok` is the only required status check.**
This keeps branch protection to a single context, survives job renames, and leaves room to add
path filters later without re-opening the settings.

### 2.9 Runner hardening the original proposal omitted

- `permissions: contents: read` at workflow level (default is broader than needed).
- `concurrency` keyed on the PR number with `cancel-in-progress: true`. PRs here get pushed to
  repeatedly — #98, #100 and #101 all landed as multi-commit branches — and without this every
  intermediate commit is paid for in full.
- `timeout-minutes` on every job; an unbounded hung job burns the full 6-hour default.
- **The Foundry binary pinned too, not just the action wrapper.** `version: stable` leaves the
  toolchain floating, so a Foundry release can change compilation, lint output or test behaviour on
  an unrelated PR — and `forge build`/`forge test` are blocking while the §2.7 gate reads Foundry's
  diagnostics. Pin `version: v1.7.1`, the release every measurement here was taken on. Confirmed
  exactly reproducible: the `v1.7.1` tag resolves to commit `4072e48705af9d93e3c0f6e29e93b5e9a40caed8`,
  which is byte-identical to the `Commit SHA` reported by the local `forge --version`. Bump
  deliberately, as with `ruff`.
- Actions pinned to commit SHAs, not floating tags. Resolved for this plan:

  | Action | Tag | SHA |
  |---|---|---|
  | `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
  | `actions/setup-node` | v7.0.0 | `820762786026740c76f36085b0efc47a31fe5020` |
  | `actions/setup-python` | v7.0.0 | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
  | `foundry-rs/foundry-toolchain` | v1.9.1 | `908c540300062bd5a7e473851cdb4282204cee09` |

- **No secrets required — verified.** Neither suite touches an RPC endpoint. `hardhat.config.ts`
  gates its `sepolia_op_devnet` network on `SEPOLIA_OP_DEVNET_RPC_URL` plus two private keys being
  present, and only warns (`Warning: ../.env.local not found`) when absent; the in-process `hardhat`
  network needs nothing. No foundry test forks (`createSelectFork` appears nowhere in
  `foundry/test/`). This keeps fork PRs safe by default and is worth stating so no one later "fixes"
  it by adding secrets.

### 2.10 Pin Python 3.12, no matrix

`pyproject.toml` says `requires-python = ">=3.12"`. `CLAUDE.md` still says ">=3.9" — stale, and
corrected in PR 1. The dev environment is 3.12.3. A version matrix triples the job for no Phase 1
benefit; revisit if the floor ever widens.

### 2.11 Doc-link check: `Documentation/` only

155 inline relative links, exactly 1 broken (`Documentation/README.md:42` →
`technical/ARCHITECTURE.md`, which does not exist). Fixed in PR 1 so the check is green when it
lands.

**Decided, not deferred:** un-link the row. The table describes ARCHITECTURE.md as "first complete
draft tracked as P3-DOC1", i.e. planned rather than lost, and a link to a document that does not
exist yet is precisely what this check exists to catch. Keep the row and its P3-DOC1 note as plain
text; restore the link when the file lands. (Rev 1 left this open in §8 while also assigning the fix
to PR 1 — a contradiction, since PR 1 cannot ship an unresolved decision.)

Extending to `Developer/` finds 3 more real breaks — `Developer/ROADMAP.md` lines 111, 117, 118
point at `../design/` where they mean `design/`. Left out of Phase 1 deliberately: `Developer/` is
explicitly forward-looking working material and churns faster. Tracked in §7.

The checker must unwrap angle-bracket autolinks (`<https://...>`) before testing for a scheme, or
`Developer/issues/DifferentialPrivacy.md` yields 5 false positives. The version in §3.2 does this
and was verified to report exactly the 4 real breaks across both trees.

---

## 3. Changes

### 3.1 PR 1 — `ci/phase1-prep`: make the tree CI-ready

No workflow yet. Every change here is independently justified and reviewable.

| File | Change |
|---|---|
| `pyproject.toml` | Add `[project.optional-dependencies]` with `test = ["pytest>=8.0", "torch>=2.6"]` (§2.4) |
| `dincli/cli/system.py` | Replace 5 literal backspace characters with `\b` — lines 306, 314, 408, 417, 433 (§2.7) |
| `Documentation/README.md` | Line 42: un-link the `technical/ARCHITECTURE.md` row, keeping the text and its P3-DOC1 note (§2.11) |
| `tests/dincli/conftest.py` | Add the path-scoped collection hook (below) |
| `tests/dincli/test_01_platform.py`<br>`tests/dincli/test_02_task_contracts.py`<br>`tests/dincli/test_03_registration.py`<br>`tests/dincli/test_04_gi.py` | **Remove** `pytestmark = pytest.mark.integration` (lines 53, 21, 30, 45) so the hook is load-bearing (§2.6) |
| `tests/test_integration_marker.py` | **New** — asserts the path classification (below) |
| `.gitignore` | Add `node_modules/`, `.pytest_cache/`, `.ruff_cache/`, `.venv/` — and **only** those (see note) |
| `CLAUDE.md` | Python `>=3.9` → `>=3.12`; correct the "no `[tool.pytest]`/`[tool.ruff]` config committed" claim — `[tool.pytest.ini_options]` predates this series, so it is a pre-existing doc inaccuracy PR 1 happens to fix rather than one it creates; keep the `[tool.ruff]` half, true until PR 3; document `npm ci` in `foundry/` as a prerequisite for `forge test` |

`.gitignore` note — corrected after implementation. `foundry/.gitignore` and `hardhat/.gitignore`
**already exist** and already cover `out/`, `cache/`, `artifacts/`, `typechain-types/` and their own
`node_modules`. Rev 1–3 of this plan prescribed nine root entries without checking for those nested
files; five of the nine were pure duplication, leaving two places to look for one rule. Only four
entries do real work:

| Entry | Why it is needed |
|---|---|
| `node_modules/` | `foundry/.gitignore` has `node_modules/*`, which does not match the directory entry itself |
| `.pytest_cache/` | its tool-written self-ignore only exists once pytest has run |
| `.ruff_cache/` | same, for ruff |
| `.venv/` | until now covered only by `.git/info/exclude` — one machine, never another contributor |

`dist/` has 2 tracked files and is left alone — removing it is a separate decision.

**The hook** — append to `tests/dincli/conftest.py` (`Path` and `pytest` are already imported):

```python
# Every test in this directory needs a live chain, an IPFS daemon and Docker.
# Marking happens here rather than per-file so a new module cannot silently
# opt out and get itself run in CI. The path test is essential, not cosmetic:
# this hook receives every collected item in the session, not just ours, so
# without it the whole suite is marked integration and CI passes running
# nothing. See plan 2.6.
_INTEGRATION_DIR = Path(__file__).parent


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = Path(str(item.fspath))
        if path == _INTEGRATION_DIR or _INTEGRATION_DIR in path.parents:
            item.add_marker(pytest.mark.integration)
```

**The regression test** — `tests/test_integration_marker.py`, new. The hook is now the only thing
standing between CI and a Docker-dependent test, so it gets a test of its own. This runs in the
unit suite (it is outside `tests/dincli/`) and asserts both directions:

```python
"""The tests/dincli/ marker hook is load-bearing; assert it actually classifies.

Guards two failure modes, both of which are silent:
  - hook missing or no-op  -> integration tests run in CI and fail on a
                              missing chain / IPFS / Docker
  - hook not path-scoped   -> the entire suite is marked integration and CI
                              passes having run nothing
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COLLECT_TIMEOUT = 60


def _collect(marker_expr):
    """Node IDs selected by `-m <marker_expr>`.

    A non-zero exit is always a failure of the assertion that follows, never
    silently-empty output: pytest returns 5 when a selection is empty, which is
    precisely the broken-hook case this module exists to catch.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", marker_expr],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=COLLECT_TIMEOUT,
    )
    assert result.returncode == 0, (
        f"collection for -m {marker_expr!r} exited {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    return [line for line in result.stdout.splitlines() if "::" in line]


def test_integration_selection_is_exactly_the_dincli_directory():
    """-m integration must select every tests/dincli item and nothing else."""
    selected = _collect("integration")
    assert selected, "no tests carry the integration marker - hook missing or no-op"
    leaked = [line for line in selected if not line.startswith("tests/dincli/")]
    assert not leaked, (
        f"integration marker leaked outside tests/dincli/ - the hook lost its "
        f"path filter: {leaked[:5]}"
    )


def test_unit_selection_is_non_empty_and_excludes_dincli():
    """-m 'not integration' must still select the unit suite."""
    selected = _collect("not integration")
    assert selected, "the unit suite is empty - the hook is over-marking"
    assert not any(line.startswith("tests/dincli/") for line in selected)
```

Deliberately asserts *shape* (every selected item is under `tests/dincli/`, and neither side is
empty) rather than the literal counts, so it does not become a chore to update whenever a test is
added. `_collect()` asserts `returncode == 0` and carries a timeout: a partial collection cut short
by an import error could otherwise leave just enough node IDs for both shape assertions to pass.
The three broken-hook states all surface as pytest's exit 5, so the assertion names the exit code
rather than reporting a vague empty list.

### 3.2 PR 2 — `ci/phase1-workflow`: turn the gate on

**New: `.github/constraints-ci.txt`** (§2.4) — the tested versions, in one reviewable file:

```
torch==2.6.0
pytest==9.1.1
ruff==0.16.4
```

**New: `.github/scripts/check_doc_links.py`** — verified to report exactly 1 finding on
`Documentation/` before PR 1's fix and 0 after. Its docstring states its real coverage rather than
claiming to handle all Markdown link syntax: the corpus was checked and contains 0 links inside
fenced code blocks and 0 reference-style definitions, so the restricted grammar is sufficient today
— and the limits are written down so a future tree that needs more does not silently get less.

Fence tracking remembers the opening run's character and length rather than toggling on any run of
three, because the naive version misclassifies the rest of a file after a ``~~~`` block that
contains a backtick run. Verified on a synthetic corpus covering a tilde fence containing ```` ``` ````,
a four-backtick fence containing a three-backtick run, a closer carrying an info string, an
unterminated fence, and a three-space-indented fence.

```python
#!/usr/bin/env python3
"""Check *inline* relative Markdown links under the given roots.

Scope, stated precisely because a checker that overstates its coverage is worse
than one that admits its limits:

  handled     inline links -- [text](path), [text](<path>), [text](path "title"),
              with an optional #fragment; fenced code blocks are skipped
  NOT handled reference-style links ([text][ref] + [ref]: path), destinations
              spanning multiple lines, destinations containing balanced
              parentheses, single-quoted or parenthesised titles, and
              percent-encoded paths

Anything in the "not handled" list is invisible to this check, not tolerated by
it. The Documentation/ corpus contains none of those forms today (verified: 0
fenced links, 0 reference definitions); widen this script before relying on it
for a tree that does.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)>\s]+)>?(?:\s+\"[^\"]*\")?\s*\)")
# Fence opener/closer. Written with `{3,}` rather than literal backticks so this
# file can itself be embedded in a Markdown fence without terminating it.
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*(.*)$")
EXTERNAL = ("http://", "https://", "mailto:", "tel:", "ftp://", "//")


def iter_prose(text: str):
    """Yield (lineno, line) for lines outside fenced code blocks.

    Tracks the opening fence's character and length: a fence closes only on the
    same character, at least as long, and with no trailing info string. Without
    that, a ``~~~`` block containing a triple backtick toggles the state and the
    rest of the file is misclassified.
    """
    fence_char: str | None = None
    fence_len = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        match = FENCE.match(line)
        if match:
            run, info = match.group(1), match.group(2).strip()
            if fence_char is None:
                fence_char, fence_len = run[0], len(run)
                continue
            if run[0] == fence_char and len(run) >= fence_len and not info:
                fence_char, fence_len = None, 0
                continue
            # a shorter/different run inside a fence is content, not a closer
            continue
        if fence_char is None:
            yield lineno, line


def main(roots: list[str]) -> int:
    repo = Path(__file__).resolve().parents[2]
    broken, checked = [], 0
    for root in roots:
        for md in sorted((repo / root).rglob("*.md")):
            text = md.read_text(encoding="utf-8", errors="replace")
            for lineno, line in iter_prose(text):
                for href in LINK.findall(line):
                    if href.startswith(EXTERNAL) or href.startswith("#"):
                        continue
                    target = href.split("#", 1)[0]
                    if not target:
                        continue
                    checked += 1
                    if (md.parent / target).exists():
                        continue
                    if (repo / target.lstrip("/")).exists():
                        continue
                    broken.append(f"{md.relative_to(repo)}:{lineno} -> {href}")

    print(f"checked {checked} inline relative link(s) in: {', '.join(roots)}")
    if broken:
        print(f"\n{len(broken)} broken link(s):")
        for b in broken:
            print(f"  {b}")
        return 1
    print("all inline relative links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["Documentation"]))
```

**New: `.github/scripts/forge_lint_gate.py`** — the fail-closed parser from §2.7, validating
forge's diagnostic schema and not merely its JSON syntax. It runs advisory in PR 2 so its output is
visible before it can block anything.

```python
#!/usr/bin/env python3
"""Fail closed on `forge lint --json` output.

Reads JSON-lines diagnostics on stdin and exits non-zero if anything is wrong.
This is a required, security-sensitive gate, so it validates the *schema* it was
written against rather than only the JSON syntax:

  * an unparseable line                     -> fail
  * an unrecognised `$message_type`         -> fail (forge's output changed)
  * a diagnostic missing `level` or a code  -> fail (schema drifted)
  * a diagnostic whose `level` is unknown   -> fail (new severity, unclassified)
  * any diagnostic at `warning` or `error`  -> fail (the actual findings)

Empty input is valid and means a clean tree. The caller must check forge's own
exit status separately; this script never sees it.

Pinned against Foundry v1.7.1, whose `forge lint --json` emits only
`$message_type: "diagnostic"` records. A new record type is treated as a
breaking change to be reviewed, not as something to skip silently.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

# Severities forge can emit, partitioned into what fails and what does not.
FAIL_LEVELS = frozenset({"warning", "error"})
PASS_LEVELS = frozenset({"note", "help", "info"})
KNOWN_LEVELS = FAIL_LEVELS | PASS_LEVELS

# Record types this parser was written against.
KNOWN_MESSAGE_TYPES = frozenset({"diagnostic"})


class SchemaError(Exception):
    """forge's output does not match what this gate was written against."""


def _diagnostic_code(record: dict) -> str:
    code = record.get("code")
    if not isinstance(code, dict):
        raise SchemaError("diagnostic has no `code` object")
    value = code.get("code")
    if not isinstance(value, str) or not value:
        raise SchemaError("diagnostic `code.code` is missing or not a string")
    return value


def _primary_location(record: dict) -> str:
    for span in record.get("spans") or []:
        if isinstance(span, dict) and span.get("is_primary"):
            return f"{span.get('file_name')}:{span.get('line_start')}:{span.get('column_start')}"
    return "<no primary span>"


def scan(stream) -> tuple[Counter, int]:
    """Return (failing counts by level[code], number of diagnostics seen).

    Raises SchemaError on anything unrecognised.
    """
    failing: Counter[str] = Counter()
    seen = 0
    for lineno, raw in enumerate(stream, 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SchemaError(f"line {lineno}: unparseable JSON ({exc})") from exc
        if not isinstance(record, dict):
            raise SchemaError(f"line {lineno}: expected a JSON object, got {type(record).__name__}")

        message_type = record.get("$message_type")
        if message_type not in KNOWN_MESSAGE_TYPES:
            raise SchemaError(
                f"line {lineno}: unrecognised $message_type {message_type!r} — "
                "forge's lint output has changed; review before trusting this gate"
            )

        seen += 1
        level = record.get("level")
        if not isinstance(level, str) or not level:
            raise SchemaError(f"line {lineno}: diagnostic has no `level`")
        if level not in KNOWN_LEVELS:
            raise SchemaError(
                f"line {lineno}: unknown severity {level!r} — classify it in "
                "FAIL_LEVELS or PASS_LEVELS before trusting this gate"
            )
        code = _diagnostic_code(record)

        if level in FAIL_LEVELS:
            failing[f"{level}[{code}]"] += 1
            print(f"{_primary_location(record)}: {level}[{code}] {record.get('message')}")

    return failing, seen


def main() -> int:
    try:
        failing, seen = scan(sys.stdin)
    except SchemaError as exc:
        print(f"::error::forge lint output failed validation: {exc}")
        return 1

    if failing:
        total = sum(failing.values())
        print(f"\n::error::forge lint reported {total} finding(s) at {sorted(FAIL_LEVELS)}")
        for key, count in sorted(failing.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {count:4d}  {key}")
        return 1

    print(f"forge lint: {seen} diagnostic(s), none at {sorted(FAIL_LEVELS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**New: `tests/test_ci_scripts.py`** — both scripts become required gates, so they get tests, not
just the synthetic checks run while writing this plan. 21 tests; run against the rev 2 parser,
exactly the four schema cases fail, which is what makes them worth committing.

```python
"""Tests for the CI helper scripts in .github/scripts/.

Both become required gates, so they get the same treatment as the code they
guard. The forge-lint gate in particular must fail closed: a parser that
silently skips what it does not understand turns a security check into a
rubber stamp.
"""
import io
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"


def _load(name):
    path = SCRIPTS / name
    spec = spec_from_file_location(f"ci_scripts_{path.stem}", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


gate = _load("forge_lint_gate.py")
links = _load("check_doc_links.py")


# --------------------------------------------------------------------------
# forge_lint_gate: fail closed
# --------------------------------------------------------------------------

DIAG = (
    '{{"$message_type":"diagnostic","level":"{level}",'
    '"code":{{"code":"{code}"}},"message":"m",'
    '"spans":[{{"file_name":"src/A.sol","line_start":1,"column_start":2,"is_primary":true}}]}}'
)


def _scan(*lines):
    return gate.scan(io.StringIO("\n".join(lines)))


def test_empty_input_is_a_clean_tree():
    failing, seen = _scan()
    assert not failing and seen == 0


def test_blank_lines_are_ignored():
    failing, seen = _scan("", "   ", "")
    assert not failing and seen == 0


@pytest.mark.parametrize("level", ["warning", "error"])
def test_failing_levels_are_counted(level):
    failing, seen = _scan(DIAG.format(level=level, code="unsafe-typecast"))
    assert seen == 1
    assert failing == {f"{level}[unsafe-typecast]": 1}


@pytest.mark.parametrize("level", ["note", "help", "info"])
def test_non_failing_levels_are_seen_but_not_counted(level):
    failing, seen = _scan(DIAG.format(level=level, code="whatever"))
    assert seen == 1
    assert not failing


def test_unknown_message_type_is_rejected():
    """A new record type means forge's output changed; do not skip it."""
    with pytest.raises(gate.SchemaError, match="unrecognised .message_type"):
        _scan('{"$message_type":"changed-schema","level":"warning"}')


def test_diagnostic_without_level_is_rejected():
    with pytest.raises(gate.SchemaError, match="no `level`"):
        _scan('{"$message_type":"diagnostic"}')


def test_diagnostic_with_unknown_level_is_rejected():
    with pytest.raises(gate.SchemaError, match="unknown severity"):
        _scan(
            '{"$message_type":"diagnostic","level":"catastrophe",'
            '"code":{"code":"x"}}'
        )


def test_diagnostic_without_code_is_rejected():
    with pytest.raises(gate.SchemaError, match="no `code` object"):
        _scan('{"$message_type":"diagnostic","level":"warning"}')


def test_unparseable_line_is_rejected():
    with pytest.raises(gate.SchemaError, match="unparseable JSON"):
        _scan("not json at all")


def test_non_object_json_is_rejected():
    with pytest.raises(gate.SchemaError, match="expected a JSON object"):
        _scan("[1, 2, 3]")


def test_missing_primary_span_still_reports():
    failing, _ = _scan(
        '{"$message_type":"diagnostic","level":"warning",'
        '"code":{"code":"x"},"spans":[]}'
    )
    assert failing == {"warning[x]": 1}


# --------------------------------------------------------------------------
# check_doc_links: fence tracking
# --------------------------------------------------------------------------


def _prose(text):
    return [line for _lineno, line in links.iter_prose(text)]


# Fences are built from explicit repeats rather than written literally: it keeps
# the run lengths visible in each test, and lets this file be quoted inside a
# Markdown fence without terminating it.
BT3, BT4 = "`" * 3, "`" * 4
TL3 = "~" * 3


def test_backtick_fence_contents_are_skipped():
    assert _prose(f"a\n{BT3}\nhidden\n{BT3}\nb") == ["a", "b"]


def test_tilde_fence_is_not_closed_by_a_backtick_run():
    """The naive toggle mis-closed here and leaked the rest of the file."""
    assert _prose(f"a\n{TL3}\ncontains {BT3} inside\nhidden\n{TL3}\nb") == ["a", "b"]


def test_longer_fence_treats_shorter_inner_runs_as_content():
    assert _prose(f"a\n{BT4}\n{BT3}\ninner\n{BT3}\n{BT4}\nb") == ["a", "b"]


def test_closing_fence_may_not_carry_an_info_string():
    assert _prose(f"a\n{BT3}\nhidden\n{BT3} python\nhidden\n{BT3}\nb") == ["a", "b"]


def test_unterminated_fence_swallows_the_rest():
    assert _prose(f"a\n{BT3}\nhidden\nalso hidden") == ["a"]


def test_indented_fence_up_to_three_spaces_counts():
    assert _prose(f"a\n   {BT3}\nhidden\n   {BT3}\nb") == ["a", "b"]


def test_prose_is_yielded_when_there_are_no_fences():
    assert _prose("one\ntwo") == ["one", "two"]
```

**New: `.github/workflows/ci.yml`** — parses under `yaml.safe_load`, and every inline `run`
block passes `bash -n`.

```yaml
name: CI

on:
  pull_request:
    branches: [develop]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.event.pull_request.number }}
  cancel-in-progress: true

env:
  # Versions this pipeline was measured against. See plan 2.4 / 2.9.
  FOUNDRY_VERSION: v1.7.1
  PIP_CONSTRAINT: .github/constraints-ci.txt

# Actions already defaults to bash on Linux, but ci-ok's result loop relies on
# word splitting, which zsh (and dash) do not do. Stated rather than assumed.
defaults:
  run:
    shell: bash

jobs:
  solidity:
    name: Solidity
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          submodules: recursive   # forge-std + 3 OZ libs; see plan 2.3
          fetch-depth: 1
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: |
            foundry/package-lock.json
            hardhat/package-lock.json
      - uses: foundry-rs/foundry-toolchain@908c540300062bd5a7e473851cdb4282204cee09 # v1.9.1
        with:
          # Pinned rather than `stable`: forge's diagnostics are parsed by the
          # lint gate and its compiler is blocking. See plan 2.9.
          version: ${{ env.FOUNDRY_VERSION }}

      - name: Record the toolchain actually installed
        run: forge --version

      # Must precede `forge test`: Upgrades.validateImplementation shells out to
      # @openzeppelin/upgrades-core over FFI, and letting npx fetch it at test
      # time races across the parallel tests. See plan 2.2.
      - name: Install foundry npm deps
        working-directory: foundry
        run: npm ci

      - name: forge build
        working-directory: foundry
        run: forge build

      - name: forge test
        working-directory: foundry
        run: forge test

      # Advisory until PR 3. `--json` writes diagnostics to stderr and cannot be
      # combined with `--color`; the gate fails closed on a nonzero forge status,
      # an unparseable stream, or any warning/error. See plan 2.7.
      - name: forge lint (advisory)
        working-directory: foundry
        continue-on-error: true
        run: |
          set +e
          forge lint --json 2> "$RUNNER_TEMP/lint.json"
          forge_status=$?
          set -e
          echo "forge lint exit status: $forge_status"
          if [ "$forge_status" -ne 0 ]; then
            echo "::error::forge lint itself failed"
            cat "$RUNNER_TEMP/lint.json" || true
            exit 1
          fi
          python3 ../.github/scripts/forge_lint_gate.py < "$RUNNER_TEMP/lint.json"

      - name: Install hardhat deps
        working-directory: hardhat
        run: npm ci

      - name: hardhat compile
        working-directory: hardhat
        run: npx hardhat compile

      - name: hardhat test
        working-directory: hardhat
        run: npx hardhat test

  python:
    name: Python
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 1
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.12'
          cache: pip

      # CPU wheel is 178 MB; the default index resolves a ~4 GB CUDA stack that
      # nothing here uses. The version comes from PIP_CONSTRAINT. See plan 2.4.
      - name: Install torch (CPU)
        run: python -m pip install --index-url https://download.pytorch.org/whl/cpu torch

      - name: Install dincli + test deps
        run: python -m pip install -e ".[test]"

      - name: ruff (advisory)
        continue-on-error: true
        run: |
          python -m pip install ruff
          ruff check .

      # Excludes tests/dincli/ (Docker + IPFS + live chain) via the directory
      # hook. pytest exits 5 if this ever selects nothing, so a broken hook
      # fails rather than passes silently. See plan 2.6.
      - name: pytest
        run: pytest -m "not integration" -q

  docs:
    name: Docs
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 1
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.12'
      - name: Relative link check
        run: python .github/scripts/check_doc_links.py Documentation

  # The only required status check. Keeps branch protection to one context and
  # avoids the path-filter/required-check deadlock. See plan 2.8.
  ci-ok:
    name: CI OK
    if: always()
    needs: [solidity, python, docs]
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Verify every job succeeded
        run: |
          results="${{ join(needs.*.result, ' ') }}"
          echo "job results: $results"
          for r in $results; do
            if [ "$r" != "success" ]; then
              echo "::error::a required job did not succeed ($r)"
              exit 1
            fi
          done
          echo "all jobs succeeded"
```

**Branch protection on `develop`** (repo settings, applied after the workflow's first green
run): require `CI OK` as the single status check, and require branches be up to date before
merging. Leave `main` untouched — Phase 1 protects the integration branch only, consistent
with the "no promotion flow" scope.

### 3.3 PR 3 — `ci/phase1-lint-cleanup`: promote the advisory checks

1. `ruff check --select F --fix` → 107 findings cleared mechanically (106 pre-existing plus
   the one PR 1 introduces by design; see §2.7). Review the diff; the `F401`
   removals are the ones worth reading carefully.
2. Fix the remaining 19 by hand (13 `F841`, 3 `E402`, 3 `E722`).
3. Add to `pyproject.toml`:
   ```toml
   [tool.ruff]
   target-version = "py312"

   [tool.ruff.lint]
   select = ["E", "F"]
   ignore = ["E501"]
   ```
4. Clear the 21 `forge lint` findings **with localized suppressions, not a global one.**

   Rev 1 recommended adding `unsafe-typecast` to `foundry.toml`'s `exclude_lints`. That is wrong:
   `exclude_lints` is project-wide, so it would also suppress genuine unchecked truncating casts in
   `src/` in order to accommodate a convention that only exists in tests. The existing entries there
   (`mixed-case-function`, `pascal-case-struct`, …) are naming conventions, where global really is
   the right scope; `unsafe-typecast` is a safety lint and is not comparable.

   All 17 are the same shape — a `bytes32("...")` reason code passed to `slash()` or
   `jailValidator()` in `test/DinValidatorStake.t.sol`, across 7 distinct literals (`test`, `bad`,
   `first`, `second`, `slash`, `penalised`, `offline`). Preferred fix, in order:

   a. Hoist the 7 literals to named `bytes32` constants at the top of the test contract, each
      carrying one `// forge-lint: disable-next-line(unsafe-typecast)` with a one-line "safe because
      the literal is ≤32 bytes" note. Call sites become `REASON_BAD` instead of `bytes32("bad")` —
      more readable, and 7 suppressions instead of 17. Confirm during implementation that
      forge-lint flags the constant initializer (it should; if it does not, the count drops to 0).
   b. Failing that, 17 individual `disable-next-line` annotations.

   The 4 `block-timestamp` findings are in `src/DinValidatorStake.sol` and are about unbonding and
   jail-expiry comparisons. Review them on their merits — a validator-manipulable timestamp in a
   withdrawal window is worth a deliberate decision, not a suppression by reflex.

   (`forge lint` also honours a path-based `ignore` in `[lint]`, which would exclude `test/**`
   wholesale. Rejected: it trades 17 annotations for the loss of lint coverage across every test.)
5. **Promote `ruff` now; promote `forge lint` only when step 4 is genuinely finished.** Remove
   `continue-on-error` from the `ruff` step in this PR. Remove it from the `forge lint` step only
   once the 4 `block-timestamp` findings are either fixed or **explicitly accepted with a written
   rationale** — a sentence naming why a validator-manipulable timestamp is tolerable in that
   specific window, recorded in the suppression comment or in `Documentation/technical/`.

   Do **not** suppress them with a bare `TODO` in order to turn the step green. That trades an open
   security question for a permanently passing gate, and the passing gate is what everyone will see
   afterwards. If the review is unfinished when the rest of PR 3 is ready, ship PR 3 with `ruff`
   blocking and `forge lint` still advisory, and promote it in a one-line follow-up. An advisory
   check that is honestly advisory costs nothing; a blocking check built over an unresolved finding
   costs the credibility of every other check in the file.

### 3.4 PR 4 — `ci/phase1-forge-fmt`: formatting, as its own PR

`forge fmt --check` exits 1 today across 20 files (bare `uint` vs `uint256` and similar). Taking it
is right — the debt only grows — but the diff is large, mechanical, and touches files PR 3 is also
editing.

Give it a **separate PR**, not merely a separate commit inside PR 3. Two reasons: a mechanical
reformat landing beside a semantic lint cleanup makes the semantic half unreviewable, and if the
reformat needs reverting it should not take the cleanup with it. PR 4 is independent of PR 3 and can
land either side of it; whichever lands second absorbs a trivial rebase.

Contents: one commit running `forge fmt`, one commit adding the `forge fmt --check` step to the
solidity job.

## 4. Verification

### 4.1 Before PR 2 opens — reproduce a runner locally

```bash
git clone --recurse-submodules <fork> /tmp/ci-verify && cd /tmp/ci-verify
git checkout develop            # PR 1 already merged; see 0

(cd foundry && npm ci && forge build && forge test)                 # expect: 162 passed
(cd hardhat && npm ci && npx hardhat compile && npx hardhat test)   # expect: 32 passing

python3.12 -m venv /tmp/ci-venv      # NOT --system-site-packages; that is the bug in 2.4
export PIP_CONSTRAINT=.github/constraints-ci.txt
/tmp/ci-venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu torch
/tmp/ci-venv/bin/python -m pip install -e ".[test]"
/tmp/ci-venv/bin/python -m pytest -m "not integration" -q     # expect: 259 passed, 133 deselected

/tmp/ci-venv/bin/python .github/scripts/check_doc_links.py Documentation   # expect: exit 0
```

The clean-venv step is the one that matters most: it is the only way to confirm the `test` extra
actually covers what the suite imports, rather than inheriting torch from `~/.local`.

### 4.2 Prove the gate can fail

A gate never observed failing is not known to work. On a scratch branch, one at a time:

| Break | Expect |
|---|---|
| Add `assert(false)` to a `foundry/test/` function | `solidity` red, `ci-ok` red |
| Add `assert False` to a `tests/test_dintoken.py` test | `python` red, `ci-ok` red |
| Add `[x](nope.md)` to a `Documentation/` page | `docs` red, `ci-ok` red |
| Remove `npm ci` from the solidity job | reproduces the §2.2 failure — confirms it is load-bearing |
| Point `FOUNDRY_VERSION` at a nonexistent tag | `solidity` red at toolchain install, not at test time |

### 4.3 Prove the marker hook is load-bearing — the check rev 1 got wrong

Rev 1 asserted the hook's correctness from the `259/133` collection count. That count is produced
whether the hook is correct, absent, or a no-op (§2.6), so it verified nothing. The committed test
from §3.1 replaces it, and it was validated by breaking the tree three ways:

| Tree state | `tests/test_integration_marker.py` |
|---|---|
| `pytestmark` removed, no hook | **2 failed** — "no tests carry the integration marker" |
| `pytestmark` removed, unscoped hook | **2 failed** — "the unit suite is empty" |
| `pytestmark` removed, path-scoped hook | **2 passed** |

Three distinct states, three distinct outcomes. That is the property rev 1's check lacked.

### 4.4 Prove the forge lint gate fails closed

`tests/test_ci_scripts.py` covers this in the unit suite; the table is what those tests assert.

| Input | Gate |
|---|---|
| current tree (21 findings) | exit 1, grouped as `17 warning[unsafe-typecast]`, `4 warning[block-timestamp]` |
| `--only-lint incorrect-shift` (0 findings) | exit 0 |
| empty input | exit 0 — a clean tree, not a failure |
| `not json at all` | exit 1, "unparseable JSON" |
| `[1, 2, 3]` | exit 1, "expected a JSON object" |
| `{"$message_type":"changed-schema","level":"warning"}` | exit 1 — **passed the rev 2 parser** |
| `{"$message_type":"diagnostic"}` | exit 1 — **passed the rev 2 parser** |
| a diagnostic with `level: "catastrophe"` | exit 1, "unknown severity" |
| a diagnostic with no `code.code` | exit 1, "no `code` object" |
| `forge lint` itself exiting nonzero | exit 1 from the wrapper's status check, before parsing |

Two rows carry the weight. The last is the case rev 1's `test -z "$(… | grep …)"` passed. The two
bolded rows are the cases rev 2's parser passed — and running these tests against that parser fails
exactly those four schema assertions and no others, which is the evidence that the tests test
something.

### 4.5 Confirm no secret dependency

Run the solidity job's steps with a scrubbed environment (`env -i`, PATH only). Hardhat should print
`Warning: ../.env.local not found` and still pass 32 tests.

---

## 5. Tests (committed)

Phase 1 adds two test files, both because it introduces mechanisms that CI then depends on:

| File | PR | Guards |
|---|---|---|
| `tests/test_integration_marker.py` (2 tests) | 1 | the directory hook is the only thing keeping Docker-dependent tests out of CI (§4.3) |
| `tests/test_ci_scripts.py` (21 tests) | 2 | the link checker's fence tracking and the lint gate's fail-closed schema validation (§4.4) |

Unit-suite totals along the way: 259 today → 261 after PR 1 → 282 after PR 2. Both files' ability to
fail was demonstrated by breaking the thing they guard, not assumed (§4.3, §4.4).

Everything else is *execution* of the 453 tests already committed (162 forge + 32 hardhat + 259
pytest).

Deliberately **not** added: a test that asserts the workflow YAML parses. It would test GitHub's
parser, not this repo. (The YAML and its inline shell were nonetheless checked with `yaml.safe_load`
and `bash -n` while writing §3.2.)

---

## 6. PR body outlines

**PR 1 — `chore: make the tree CI-ready`**
Lead with the torch finding: the Python suite passes locally only because of a globally-installed
CUDA build leaking in through `--system-site-packages`. That single fact justifies the series. Then
the marker hook — say plainly that the four `pytestmark` lines are *removed* so the hook is
load-bearing, and that the new test fails if it regresses. Then the backspace-character fix, the
un-linked ARCHITECTURE row, `.gitignore`, and the `CLAUDE.md` corrections. No user-visible behaviour
changes.

**PR 2 — `ci: add PR checks for develop (phase 1)`**
Link discussion #74. State what runs, what is advisory and why, and that `CI OK` is the single
required check. Include the §2.2 reproduction — reviewers should see the failure this avoids. Note
the pinned Foundry version and why a floating toolchain was rejected. Explicitly: no secrets, fork
PRs safe, `main` untouched.

**PR 3 — `style: clear the ruff and forge lint backlog, make both checks blocking`**
Separate the auto-fixed commit from the hand-fixed one so review is tractable. Numbers up front: 107
mechanical, 19 manual, 21 Solidity. Explain why the Solidity suppressions are localized rather than
added to `exclude_lints`.

**PR 4 — `style: forge fmt`**
One mechanical commit plus the `--check` step. Say in one line that it is deliberately separate from
PR 3 so the semantic cleanup stays reviewable.

---

## 7. Follow-ups not in this PR series

- `Developer/ROADMAP.md` lines 111, 117, 118 — `../design/` should be `design/` (§2.11).
- Extend the link check to `Developer/` once that tree settles, and widen the checker's grammar at
  the same time (reference-style links, multi-line and parenthesised destinations, percent-encoded
  paths). Add parser fixtures for those forms rather than trusting the current corpus to stay
  simple; a real Markdown parser becomes worth its dependency at that point.
- `dincli/requirements.txt` duplicates a subset of `pyproject.toml` `dependencies` and pins it to
  *different* versions (e.g. `typer==0.20.0` against `typer>=0.9.0`). Not a CI blocker; it is a trap
  waiting for someone. Decide which file is authoritative and delete the other.
- Runtime `dependencies` are all open-ended lower bounds. The CI constraints file (§2.4) pins the
  *test* environment but says nothing about what a user installs. Worth a deliberate policy.
- `dist/` has 2 tracked files that look like build output; decide whether to untrack.
- `CODEOWNERS`, a PR template, and Dependabot for `github-actions` and `npm` (~10 lines each, and
  Dependabot is what stops the pinned SHAs in §2.9 from silently rotting).
- Phase 2, per discussion #74: the `tests/dincli/` integration suite on a nightly schedule against
  `develop`; fuzz/invariant tests; Slither/Aderyn; gas-snapshot regression; merge queue. Static
  analysis will repeat the §2.7 backlog problem at higher volume — plan the triage before enabling
  it, not after.

---

## 8. Decisions needed

Two remain, **both inside PR 3**. Rev 2's status line split them across PRs 3 and 4; that was wrong
— PR 4 carries no open decision, and the ARCHITECTURE-link question was resolved in §2.11 because
PR 1 cannot ship an unresolved decision. Nothing here blocks PR 1, PR 2 or PR 4.

1. **§3.3 step 4 — how to suppress the 17 test casts.** Approach (a), hoisting the 7 reason codes
   to named `bytes32` constants with one suppression each, or (b) 17 individual annotations?
   Recommend (a): fewer suppressions, more readable call sites. Either way, **not** a global
   `exclude_lints` entry — that would suppress a safety lint in `src/` to serve a test-only
   convention. Low stakes; a reviewer's preference is enough.

2. **§3.3 step 4/5 — the 4 `block-timestamp` findings in `src/DinValidatorStake.sol`.** A genuine
   issue in the unbonding and jail-expiry comparisons, or an accepted risk? This is a
   contract-security judgement and wants a Solidity reviewer, not a CI decision. Timestamps are
   conventional for windows of this kind, so acceptance is a plausible outcome — but it has to be
   *written down*, naming why manipulation within a block-timestamp's drift does not matter for
   these specific comparisons.

   This decision gates only whether `forge lint` becomes blocking, not whether PR 3 lands (§3.3
   step 5). If it is unresolved, PR 3 ships with `ruff` blocking and `forge lint` advisory, and the
   promotion follows in a one-line PR. That separation is deliberate: it removes any incentive to
   close a security question quickly in order to unblock a lint gate.
