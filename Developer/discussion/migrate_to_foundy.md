---
title: "Migrate DIN contracts to Foundry-only vs. upgrade to Hardhat 3"
date: 2026-06-30
status: open
participants:
  - Umer Majeed (Principal Engineer) — @/home/azureuser/projects/HR/Umer
  - Robbert Abimbola (Solidity Engineer) — @/home/azureuser/projects/HR/Robbert
assigned-to: Robbert Abimbola (investigate and deliver recommendation)
decision-target: TBD
---

## Context

The DIN DevNet repo currently maintains **two parallel Solidity toolchains**:

- `foundry/` — Forge build + test + Anvil, `foundry.toml` (`solc 0.8.28`, `via_ir = true`, `optimizer_runs = 200`)
- `hardhat/` — Hardhat 2 + `@nomicfoundation/hardhat-toolbox`, TypeScript tests, `hardhat-contract-sizer`, `evmVersion: cancun`

Both are pointed at the same contracts. Running two toolchains in parallel adds CI overhead, dependency drift risk, and contributor confusion (which directory is authoritative?). This discussion evaluates whether to consolidate — and if so, which direction.

Two options are on the table:

1. **Go Foundry-only** — drop Hardhat, migrate remaining Hardhat tests to Forge (Solidity), use `forge script` for deployment.
2. **Upgrade Hardhat 2 → Hardhat 3** — keep the TypeScript ecosystem, benefit from Hardhat 3's speed improvements and ESM support, retire the Foundry parallel track (or keep it only for fuzz testing).

---

## Option 1: Go Foundry-only

### Benefits

- **Speed** — `forge build` and `forge test` are significantly faster than Hardhat 2 (Rust-based pipeline vs. JS).
- **Native fuzz testing** — `forge test` with `vm.assume()` / property-based inputs; zero extra config. This directly addresses the current test coverage gap called out in Umer's onboarding review.
- **Gas snapshots** — `forge snapshot` produces a `.gas-snapshot` file that catches regressions in CI automatically.
- **Solidity-native tests** — no context-switch into TypeScript; validators/auditors writing Solidity day-to-day stay in one language.
- **Forge script** — deployment scripts in Solidity (`script/`) replace Hardhat deploy tasks; already partially present in `foundry/script/`.
- **`forge coverage`** — built-in line coverage with LCOV output, useful for audit prep.
- **Robbert already uses Foundry** at Byro; migration cost for him is low.
- **Already partially set up** — `foundry/` is live, `anvil.sh` is the local devnet chain.

### Blockers / Risks

- **Upgradeable contracts (PR #13)** — `feature/platform-upgradeable` uses OZ Transparent Proxy. The Hardhat OZ upgrades plugin (`@openzeppelin/hardhat-upgrades`) validates storage layout automatically on deploy. The Foundry equivalent (`foundry-upgrades` / `openzeppelin-foundry-upgrades`) is newer and less battle-tested for complex proxy patterns. This is the **primary blocker** — Robbert should validate that `forge` can reliably check storage layout safety before we commit to dropping Hardhat.
- **TypeScript typechain-types loss** — `hardhat/typechain-types/` gives typed contract bindings used by any off-chain TS consumers. If there are none today this is a non-issue; if there are, `wagmi generate` or `viem` ABIs from `foundry/out/` JSON are the replacement path.
- **Test migration effort** — existing Hardhat TS tests need to be rewritten in Solidity. Volume should be assessed before committing.
- **Hardhat verification plugin** — `hardhat-verify` for Etherscan/Blockscout is well-supported; Forge's `--verify` flag works but is less configurable. Verify the Optimism Sepolia (Blockscout) flow works with `forge verify-contract`.

---

## Option 2: Upgrade Hardhat 2 → Hardhat 3

### Benefits

- **Faster compilation** — Hardhat 3 ships a new task runner and parallel compilation.
- **ESM-native** — cleaner `import` structure, drops CommonJS edge cases.
- **TypeScript stays** — `typechain-types` and typed deployment scripts remain, no migration of existing tests.
- **OZ upgrades plugin continuity** — storage layout checking for `feature/platform-upgradeable` stays exactly as-is.
- **Hardhat Network improvements** — better EVM tracing, improved `hardhat_getAutomine` / interval mining, more reliable Cancun hardfork support.

### Blockers / Risks

- **Breaking changes** — Hardhat 3 has a new config format and drops some v2 plugins. A migration pass on `hardhat.config.ts` and existing test helpers is required.
- **Plugin ecosystem lag** — `hardhat-contract-sizer`, `hardhat-toolbox`, and third-party plugins may not have stable v3 releases yet. Check current compatibility before committing.
- **No fuzz testing** — still requires a separate tool (Foundry or Echidna) for property-based testing; doesn't resolve the test gap natively.
- **Speed ceiling** — Hardhat 3 is faster than v2 but still slower than `forge`; for a contract suite growing in P3/P4, this matters as CI time grows.
- **We already have Foundry** — upgrading Hardhat keeps two toolchains alive rather than consolidating.

---

## Key Questions for Robbert to Investigate

1. **Upgradeable contracts compatibility** — can `openzeppelin-foundry-upgrades` reliably validate storage layout for the Transparent Proxy pattern in PR #13? Test with a dry-run upgrade simulation in Forge before recommending migration.
2. **Test inventory** — how many Hardhat tests exist in `hardhat/test/`? Estimate rewrite cost in Forge equivalents.
3. **Verification** — does `forge verify-contract` work cleanly against Optimism Sepolia Blockscout with our current contract setup?
4. **Hardhat 3 plugin compatibility** — are `hardhat-contract-sizer` and `@nomicfoundation/hardhat-toolbox` available and stable for Hardhat 3 as of today?
5. **Typechain consumers** — are the `typechain-types` used anywhere outside the `hardhat/test/` directory (off-chain scripts, backend, etc.)?

---

## Initial Position (Umer)

Leaning toward **Foundry-only** given that:
- Anvil is already the devnet chain (`foundry/anvil.sh`)
- Foundry is already set up and partially in use
- Fuzz testing is a stated high-priority gap (Umer onboarding review)
- Robbert has Foundry experience and is the primary contract engineer going forward
- Advisors recommend foundry

The upgradeable contracts question is the deciding factor. If `openzeppelin-foundry-upgrades` covers our proxy pattern cleanly, Hardhat can be retired. If there are gaps, we either keep a thin Hardhat wrapper for OZ upgrade validation only, or we defer migration until the OZ Foundry plugin matures.

Hardhat 3 upgrade is only worth pursuing if the OZ upgrade blocker is unresolvable AND we want to stay TypeScript-native for some reason not yet identified.

---

## Open Items

- [ ] Robbert: investigate upgradeable contract compatibility with `openzeppelin-foundry-upgrades` (primary blocker)
- [ ] Robbert: audit `hardhat/test/` — test count and rewrite estimate
- [ ] Robbert: verify Optimism Sepolia Blockscout verification via `forge verify-contract`
- [ ] Robbert: check Hardhat 3 plugin ecosystem status (fallback path)
- [ ] Robbert: deliver written recommendation with rationale
- [ ] Umer: review Robbert's recommendation and make final call

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| — | — | Pending Robbert's investigation |
