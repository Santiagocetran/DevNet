# PR draft — Validator Readiness: Keystore Security + Filecoin (Lighthouse) Adapter

**Not opened yet.** Draft body below, ready for `gh pr create --base develop --title "..." --body-file Plans/archive/pr-description-draft.md` once reviewed.

Suggested title: `feat(validator-readiness): keystore security hardening + Filecoin (Lighthouse) provider adapter`

---

## needs-security-review

The wallet/keystore-handling commits must be reviewed by **@umeradl** before merge, per `task_300626_3`: the two feature commits (`5cfd390` in-memory password cache / `--keystore` import / named store, `4c7881a` `--wallet` wiring) plus the follow-up fix (`8436e50` clean invalid-`--name` handling in `connect-wallet`) and the `.gitignore` guard (`3d1bf04` stray root-level key files). Everything else (docs, IPFS/Lighthouse adapter) does not need the same scrutiny.

## Summary

Implements both parts of `task_300626_3`:

- **Part 1 (P3-T0.2b):** keystore security hardening — encrypted named multi-account keystores, `--keystore` import, in-memory password cache (removes on-disk plaintext session cache), burner-wallet + migration guides, production-key callouts across docs.
- **Part 2:** Filecoin-backed IPFS storage via a first-class Lighthouse provider adapter, alongside the existing `env`/`filebase`/`custom` providers.

## Part 1 — Keystore Security

- `connect-wallet --keystore <path>`: imports a standard eth-account JSON keystore, decrypts to verify + derive the checksummed address, preserves the original keystore verbatim (`source: "imported"`).
- `connect-wallet --name <name>`: named multi-account keystores at `wallets/wallet_<name>.json` (shared wrapper schema); legacy `wallet.json` still loads as `default` (named default wins when both exist).
- `--wallet <name>` / `DIN_WALLET_NAME` env / config `wallet_name`: runtime account selection, resolved through `DinContext`; new `dincli system set-wallet <name>` persists a default. Resolution: `--wallet` → env → config → `"default"`.
- Name validation (`^[A-Za-z0-9_-]{1,64}$`) enforced at the filesystem-boundary function (`wallet_path_for_name`) itself, not just at CLI entry points — so it holds regardless of call path.
- In-memory TTL password cache replaces the on-disk `CONFIG_DIR/.session` file (no plaintext password ever written to disk); stale `.session` files are cleaned up automatically. **This intentionally removes cross-invocation password caching** — the only no-reprompt option across separate commands is `DIN_WALLET_PASSWORD` in `.env`.
- `dincli system list-accounts`: enumerates named wallets + legacy fallback without decrypting.
- New guides: `Documentation/guides/wallet-setup.md` (burner wallet rationale, generation via `eth-account`/OWS, funding — 10 DIN stake + ETH gas), `Documentation/guides/keystore-migration.md` (old `.env` pattern → encrypted keystore migration path).
- Production-keystore callouts added to every doc that instructs raw-key `.env` setup (`setup.md`, `GettingStarted.md`, `common.md`, `Model-workflow.md`, `DINCLI_Containerizaton_Guide.md`, `DEVELOPMENT_SETUP.md`, docker node README/`.env.example`).

### OWS (Open Wallet Standard) feasibility

Assessed per the task's ask. OWS (`openwallet.sh`) has a real CLI (`ows wallet create`, `sign message`, `sign tx`, `mnemonic generate/derive`), Node/Python SDKs, and an MCP server — but its documented command reference has **no `export` subcommand**, so `wallet-setup.md` uses it only for keystore *creation*, not export, and points operators to `ows --help`/upstream docs for the current export surface rather than asserting an unverified command. Recommendation: **document-only for now** — full signing delegation (dincli never holding the raw key) is plausible given OWS's MCP/REST/SDK interfaces, but implementing that integration is out of scope for this task.

### Design deviations (flagged for confirmation, not blocking)

| # | Deviation | Why |
|---|---|---|
| D1 | Cross-invocation password caching removed entirely (in-memory only, per-process) | The old on-disk `.session` cache is a real plaintext-on-disk risk; a module-level cache can't replicate cross-command convenience since each `dincli` invocation is a new process. `DIN_WALLET_PASSWORD` env is the only remaining no-reprompt path. |
| D2 | `--account` stays an `int` (dev key index); `--name` labels saved keystores; `--wallet` selects at runtime | Avoids one flag meaning two different things (dev index vs. production keystore name). |
| D3 | Added `dincli system set-wallet <name>` to persist a default wallet name in config | The `--wallet`/env/config three-tier resolution needs a way to actually set the config tier; nothing did before. |
| D4 | Name validation moved into `wallet_path_for_name()` itself | Makes path safety a filesystem-boundary invariant rather than something every caller must remember. |

## Part 2 — Filecoin Provider Adapter (Lighthouse)

- New `dincli/services/ipfs_lighthouse.py`: `upload_via_lighthouse`/`retrieve_via_lighthouse`, verified against Lighthouse's own GitHub docs (not assumed) — `POST https://upload.lighthouse.storage/api/v0/add`, `Bearer` auth, multipart `file` field, **nested** `{"data": {"Hash": ...}}` response (different from Filebase's flat shape — this one place would silently break on a copy-paste from the Filebase code, so it's explicitly tested).
- Wired in as a genuine first-class provider (`"lighthouse"` in `SUPPORTED_IPFS_PROVIDERS`), not the generic dynamic-module `custom` path — matches the task's concrete deliverables (dedicated module, dedicated test file, dedicated env var) better than the discussion doc's more general "use the custom path" framing.
- `IPFS_PROVIDER` env var for provider selection (config wins if set — this is a real, generic addition to `resolve_ipfs_config()`, not Lighthouse-specific) and `LIGHTHOUSE_API_KEY` as an API-key fallback, satisfying the task's literal env-var ask on top of the config-first mechanism every other provider already uses.
- API keys are now stored **per-provider** (`ipfs_api_key_<provider>`) instead of one shared flat field — fixes a real bug found during review: switching `configure-ipfs` from `filebase` to `lighthouse` without a fresh `--api-key` used to silently reuse the Filebase token instead of failing with a clear error. Legacy flat key still resolves for `filebase` (back-compat).
- Docs: `ipfs.md` (new `lighthouse` section), plus `CLAUDE.md`/`ReadMe.md`/`setup.md` updated so they don't keep describing a stale "three provider" picture.
- Tests: 15 across `test_ipfs_lighthouse.py` (new) and `test_ipfs_config.py` (extended) — nested-hash extraction, malformed-response handling, missing-key error, HTTP errors, exact retrieve URL/method, env-var provider selection, config-over-env precedence, cross-provider key isolation.

### ⚠️ Confirmed finding: Lighthouse retrieval is payment-gated, even for the file's own owner

Live-tested with a real account (not just mocks): upload works exactly as documented and returns a valid CID. **Retrieval does not** — `GET https://gateway.lighthouse.storage/ipfs/<cid>` returns `402 Payment Required`, with and without the uploader's own API key attached (identical response either way — this isn't an auth-header issue). A generic public IPFS gateway (`ipfs.io`) also fails for the same CID: "no providers found for the CID" — the content isn't discoverable on the public IPFS network at all.

This contradicts two explicit assumptions this task was built on:
- The discussion doc's framing of Lighthouse as providing "a fast retrieval gateway" as a solved problem.
- The task's own stated fallback: *"Retrieval can fall back to the standard IPFS HTTP gateway; the CID is a CID regardless of which provider stored it"* — not true here; no gateway currently serves this content without payment.

This is not a bug in `ipfs_lighthouse.py` — the adapter matches Lighthouse's documented API contract exactly, and the upload path is fully correct. It's an account/platform-level gate (Lighthouse appears to use HTTP 402 + likely the x402 micropayment protocol for gateway retrieval) that neither the discussion doc nor the task anticipated. **Recommendation:** before relying on Lighthouse for production retrieval, confirm whether this resolves with a funded/paid account or is a structural characteristic of the service — this may affect whether Lighthouse remains the right "first adapter" per the discussion doc, versus Storacha or another option. Raising this with Umer/Abraham directly; flagging here so it's not lost.

## Test plan

```
tests/test_connect_wallet.py + test_ipfs_config.py + test_ipfs_lighthouse.py: 61 passed
Full suite: 68 passed, 1 pre-existing unrelated failure (test_dintoken.py::test_stake_uses_requested_amount),
            1 skipped, 134 environment-specific errors (require /home/azureuser, pre-existing)
```

All new code paths, all previously-existing tests (regression-checked), no new failures introduced.

## Not in scope / deliberately deferred

- SIGTERM handling (T0.2a) — deferred to P4 per the task.
- Sponsored-upload / on-chain storage budget accounting for Lighthouse — P3 fee design work, per the discussion doc's own sequencing.
- Resolving the Lighthouse payment-gate finding above — needs an architectural call, not a code fix.
