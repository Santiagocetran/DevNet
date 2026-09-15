# Proposal: CI/CD Phase 1 — automated checks on every PR to `develop`

## Context

There's currently no CI/CD in this repo — no `.github/workflows/`, no branch protection, nothing enforced. Builds and tests are run manually by contributors, documented only in prose (`CLAUDE.md`). With several PRs touching overlapping files, regressions currently surface only at manual-review time.

This proposal scopes **Phase 1 only**: a single workflow that runs automatically when a PR is opened/updated against `develop`. It intentionally leaves heavier checks (integration harness, fuzz/invariant tests, static analysis, a stricter pre-merge gate, `develop` → `main` promotion) for a follow-up discussion once Phase 1 is in and working.

## Proposed Phase 1 workflow

Trigger: `pull_request` targeting `develop` (runs on open, and again on every new commit pushed to the PR).

| Job | Command | Notes |
|---|---|---|
| Foundry build + test | `cd foundry && forge build && forge test` | Already the documented primary workflow (`CLAUDE.md`) — just automating what contributors run locally |
| Hardhat build + test | `cd hardhat && npx hardhat compile && npx hardhat test` | Documented secondary/complementary toolchain |
| Python unit tests | `pytest -m "not integration"` | One test suite (`dincli`), not two — excludes the `tests/dincli/` suite, which is marked `integration` in `pyproject.toml` because it needs a live Hardhat node, Anvil, IPFS, and Docker. That suite is out of scope for a PR gate; see Phase 2. |
| Upgrade validation | `cd foundry && forge test --match-contract UpgradeValidationTest` | Proxy storage-layout safety check (`foundry/test/UpgradeValidation.t.sol`) — cheap, high consequence if skipped |
| Solidity lint | `cd foundry && forge lint` | `foundry.toml` already has a `[lint]` section with `exclude_lints` configured — the linter is half set up already, it's just never invoked anywhere. No new tooling needed. |
| Python lint | `ruff check .` | No `[tool.ruff]` config exists yet — `Developer/CONTRIBUTING.md` documents "Python: PEP 8" as a standard with nothing enforcing it. This adds a minimal ruff config alongside the workflow. |
| Doc-link check | simple relative-link checker over `Documentation/` | Catches dead cross-references as the doc tree gets reorganized (there's a live one today: `Documentation/README.md` → `technical/ARCHITECTURE.md`, which doesn't exist) |

## Explicitly out of scope for this proposal (future discussion)

- `tests/dincli/` end-to-end integration suite — real value, but needs Docker + IPFS + a running chain; belongs on a schedule (nightly against `develop`), not a PR gate
- Foundry fuzz/invariant tests, Slither/Aderyn static analysis, gas-snapshot regression
- A stricter check gating the actual merge (via GitHub's merge queue) beyond what runs on the PR
- Any `develop` → `main` promotion flow — the project is devnet-only right now, no release/deployment automation exists or is being proposed here

## Open questions for this discussion

1. Should Phase 1 checks be made *required* status checks on `develop` immediately, or run informationally for a trial period first?
2. Any objection to adding a minimal `ruff` config as part of this work, given there's no linting precedent in the repo yet?

@umermjd11 @robertocarlous @abrahamnash 

