# Implementation Plan — Part 1: Keystore Security & Resource Documentation

**Task:** `task_300626_3` (P3-T0.2b)
**Branch:** `feat/validator-readiness` (off `develop`)
**Reviewer gate:** Umer must review all keystore-related changes before merge. PR to be flagged `needs-security-review`.
**Scope of this plan:** Part 1 only (1a–1d). Part 2 (Filecoin/Lighthouse adapter) is planned separately.
**Revision:** v3 — incorporates second review round (consistent wallet schema for all named writes, explicit default precedence, read-wallet/todo wiring, permission handling for existing files, active-wallet visibility, migration-guide flow via `--keystore` import).

> **Note on `Plans/`:** This folder is **not** git-ignored in the current repo (an earlier planning note assumed it was). Add `Plans/` to `.gitignore` or never `git add Plans/`.

---

## 0. Guiding principles (from the task)

1. **Additive, not subtractive.** Every existing key-loading path is preserved: positional `privatekey` arg, `--key-file`, `--account <n>` (`.env` `ETH_PRIVATE_KEY_<n>`), interactive `getpass`, `_get_password` from env, demo-mode plaintext wallet. We *add* secure options and *strengthen warnings/docs*; we do not remove paths.
2. **Classify by security tier.** Make the security/convenience tradeoff explicit in docs, templates, and CLI output; steer production validators toward encrypted keystores / external key management.
3. **No SIGTERM handling.** T0.2a is explicitly deferred to P4 — no process-signal handling in this task.
4. **OWS is an external operator tool**, not a bundled dependency. Link to https://openwallet.sh/; do not vendor it.

### Two decisions locked before coding (were open questions in v1)

**D1 — Cross-invocation password caching is intentionally REMOVED.**
`dincli` is a one-shot CLI. The old on-disk `CONFIG_DIR/.session` cache survived *across* separate command invocations; a module-level in-memory cache **cannot** — it only helps if a single process decrypts more than once. We will **not** describe the in-memory cache as "equivalent convenience." Part 1 removes cross-invocation password caching. The only sanctioned ways to avoid re-prompting across commands become: (a) `DIN_WALLET_PASSWORD` env (automation tier, already supported), or (b) a future OS-keyring / OWS-delegation path **only if Umer approves it**. The in-memory cache is a minor within-process convenience and a security improvement (no plaintext on disk), nothing more. This is stated plainly in the tiers table, `keystore-migration.md`, and the PR description.

**D2 — Account-selection CLI/API is fixed as three distinct surfaces (no overloading):**
| Surface | Type | Meaning |
|---|---|---|
| `connect-wallet --account <index>` | `int` | **Unchanged.** Dev/demo Hardhat index *or* `ETH_PRIVATE_KEY_<index>` from `.env`. |
| `connect-wallet --name <name>` | `str` | **New.** Label under which to save the encrypted keystore (`wallet_<name>.json`). Default `default`. |
| top-level `--wallet <name>` (+ `DIN_WALLET_NAME` env / config fallback) | `str` | **New.** Selects which named keystore commands use at runtime. Default `default`. |

`--account` is **never** widened to a string. This deviates from the task's literal "selectable by name via `--account <name>`" wording — that's a deliberate, documented choice to avoid one flag meaning both "dev private-key index" and "production keystore name." Call it out in the PR for the author/Umer to confirm.

---

## 1. Current state — verified facts (grounding for the changes)

### Key-loading paths in `dincli/cli/system.py::connect_wallet` (lines 261–392)
| Path | Code location | Current behaviour | Target tier |
|---|---|---|---|
| Positional `privatekey` arg | `system.py:332-336` | Raw `0x…` accepted; one-line warning; key enters shell history | Dev only — **strengthen warning** |
| `--key-file` / `-f` | `system.py:317-330` | Reads plaintext key from disk file | Dev/testing — **document as non-production** |
| `--account <n>` (demo) | `system.py:305-311` | `get_demo_private_key(n)` — Hardhat dev accounts | Hardhat/local only — no change |
| `--account <n>` (non-demo) | `system.py:312-315` | `get_env_key("ETH_PRIVATE_KEY_"+n)` from `.env` | Dev/testing — convenient, **document as non-production** |
| Interactive `getpass` | `system.py:338-343` | Prompts for raw key, then `Account.encrypt` at rest | **Acceptable for production** |
| `_get_password` from env | `utils.py:351-354` | `DIN_WALLET_PASSWORD` pre-loaded from env | Dev/automation — **document tradeoff** |
| Demo `WALLET_FILE` | `system.py:357-368` | Saves `"private_key"` plaintext JSON | Hardhat-only, already marked `⚠️ ONLY FOR MOCK!` — no change |

### Storage / loading model
- `WALLET_FILE = CONFIG_DIR / "wallet.json"` — **single** active account (defined in both `system.py:37` and `utils.py:33`).
- `CONFIG_DIR = Path(user_config_dir("dincli"))` (`utils.py:24`) → `~/.config/dincli` on host, `$DIN_STATE_DIR/config/dincli` in the node container.
- Encrypted save: `Account.encrypt(privatekey, password)` → JSON keystore (`system.py:384-388`). **Already a standard eth-account keystore.**
- Load: `load_account()` (`utils.py:306-339`) → demo branch returns `Account.from_key`; encrypted branch `Account.decrypt(data, password)` where `password = _get_password()`.
- `account` is lazily resolved once per process via `DinContext.account` (`context.py:71-80`), which calls `load_account()` with **no selector** today.
- Top-level CLI callback `main()` (`dincli/main.py:34-58`) already has `--network` and does `ctx.obj = DinContext(); ctx.obj.select_network(network)`. `DinContext.select_network(network)` (`context.py:105`) just sets `self.network_arg`. **This is the exact pattern to mirror for `--wallet`.**

### Every direct `WALLET_FILE` / `.session` reference (the closing implementation risk — all must be updated or intentionally left legacy-only)
| Location | Use | Action |
|---|---|---|
| `system.py:37`, `utils.py:33` | `WALLET_FILE = CONFIG_DIR/"wallet.json"` definition | Keep as **legacy default**; add named-store path helpers alongside |
| `system.py:364,368` | demo-mode plaintext save | Leave (demo mock-only) — but honor `--name` if provided so demo wallets can be named too (optional) |
| `system.py:387,392` | encrypted save in `connect_wallet` | **Rewrite** to named path + wrapper schema + perms (see 1c-C) |
| `system.py:401,405` (`read_wallet`) | `WALLET_FILE.exists()` + open | **Rewrite** to honor active `--wallet`/`DIN_WALLET_NAME`; resolve via the same name logic; understand wrapper + legacy forms |
| `system.py:641-644` (`todo`/doctor) | `WALLET_FILE.exists()` existence check | **Rewrite** to check the active named wallet (and list any named wallets); not just legacy `wallet.json` |
| `utils.py:310-313` (`load_account`) | existence + open | **Rewrite** to `load_account(name=...)` resolving named → legacy fallback |
| `docker/node/README.md:247` | file-tree doc lists `wallet.json, config.json, .session` | **Update**: add `wallets/` dir; mark `.session` as legacy-cleanup-only |

### Password caching — the known issue
- `_get_password()` (`utils.py:341-376`): env var → **on-disk** session cache `CONFIG_DIR/.session` (15-min TTL, perms == `0o600`) → `getpass` prompt.
- `_cache_password_if_needed()` (`utils.py:378-395`): writes plaintext password to `.session` (`0o600`). **The disk-plaintext issue → move to in-memory (see D1).**
- `_clear_session_cache()` (`utils.py:397-403`): unlinks `.session`.

### Docs / templates
- **Exists:** `dincli/docker/node/.env.example` (only `DIN_STATE_DIR`/`DOCKER_GID`/`DIN_UID`/`DIN_GID`; no key vars), `dincli/docker/node/README.md` (references wallet/keys/`.session`), `Documentation/guides/ipfs.md`, `Developer/DEVELOPMENT_SETUP.md` (19 lines).
- **⚠️ DISCREPANCY:** task says edit "`.env.example` (repo root and `hardhat/`)" — **neither exists.** Only `dincli/docker/node/.env.example` is tracked. See §2.1.
- **`hardhat/hardhat.config.ts` loads `../.env` then `../.env.<NETWORK>`** — i.e. Hardhat reads the **repo-root** `.env`, *not* `hardhat/.env`. The root template is therefore authoritative (see §2.1).
- **`MIN_STAKE = 10 * 1e18`** (verified in `hardhat/contracts/DinValidatorStake.sol:30` and `foundry/src/DinValidatorStake.sol:28`) → **10 DIN** minimum stake. Gas is paid in **ETH**. The burner-funding section must say "10 DIN to stake + ETH for gas," not "ETH to stake."
- **`.session` referenced in `dincli/docker/node/README.md`** — must be re-described as legacy cleanup only after this change.

---

## 2. Work breakdown

### 2.1 — Sub-task 1a: Audit & classify plaintext key exposure (docs + templates)

**Audit scope (expanded per feedback):** "all user-facing docs that instruct wallet setup or `connect-wallet`/`--account` usage," **not** only raw `ETH_PRIVATE_KEY` mentions. Candidate set to review (from `rg`): `Documentation/GettingStarted.md`, `setup.md`, `common.md`, `Model-workflow.md`, `clients.md`, `services.md`, `ReadMe.md`, `technical/DINCLI_Containerizaton_Guide.md`, `technical/DINCLI_TESTING_GUIDE.md`, `Developer/issues/validator-operations.md`, `Developer/tooling/model-owner-contracts.md`, `dincli/docker/node/README.md`. Walk each; add the production callout wherever it tells the operator to put a raw key in `.env` or to use `--account <index>` for anything beyond local/dev. (Skip pure task/roadmap/design docs like `Developer/tasks/*`, `ROADMAP.md`, `validator_selection/design.md` unless they give setup instructions.)

**Decision on missing `.env.example` files:**
- **Create `/.env.example` (repo root) — authoritative.** Hardhat reads `../.env`, and `dincli` reads `.env` from cwd; the root template serves both.
- **Create `hardhat/.env.example` — minimal + signpost.** It must explicitly state at the top: *"Hardhat loads the repo-root `.env` (`../.env`), not this directory's `.env`. Use the repo-root `.env.example` as the source of truth; this file lists only Hardhat-specific deployment vars for reference."* This avoids the confusion the feedback flagged.

**Root `.env.example` content** — document the dev-only multi-account pattern with the production callout:
```dotenv
# ─── DIN CLI environment (development / testing) ───
# Copy to .env (never commit .env). Values here are for LOCAL DEVELOPMENT.

# RPC endpoints (per network)
LOCAL_RPC_URL=http://127.0.0.1:8545
SEPOLIA_OP_DEVNET_RPC_URL=
MAINNET_RPC_URL=

# ── Wallet keys — DEVELOPMENT / TESTING ONLY ──────────────────────────
# ETH_PRIVATE_KEY_<n> stores RAW private keys in PLAINTEXT on disk.
# Convenient for multi-account local testing; NOT for production validators.
# Production validators: use an encrypted keystore instead — see
#   Documentation/guides/wallet-setup.md
# ETH_PRIVATE_KEY_0=0x...
# ETH_PRIVATE_KEY_1=0x...

# Wallet decryption password for AUTOMATION (encrypted keystore).
# NOTE: dincli no longer caches passwords across commands (see
# keystore-migration.md). For unattended/CI runs set this; for interactive
# production use you will be prompted per command unless this is set.
# DIN_WALLET_PASSWORD=

# Active named keystore selector (optional; default "default").
# Equivalent to the top-level --wallet flag.
# DIN_WALLET_NAME=default
```

**`hardhat/.env.example`:** the signpost header above + only the Hardhat deployment vars actually consumed by `hardhat.config.ts` (confirm exact names before writing), each labelled dev/deploy-only with the same keystore callout.

**`dincli/docker/node/.env.example`:** add a key-management section:
```dotenv
# ─── Key management (read before first run) ───
# din-node never stores raw keys in this file. Production validators import an
# ENCRYPTED keystore via `dincli system connect-wallet` (prompted) or
# `--keystore <path>`. The ETH_PRIVATE_KEY_<n> .env pattern is DEV ONLY.
# See Documentation/guides/wallet-setup.md and keystore-migration.md
```

**Production callout (consistent wording) added wherever a raw key is set:**
> **⚠️ Local development only.** The `ETH_PRIVATE_KEY_<n>` pattern stores raw private keys in plaintext. If you are running a **production validator node**, use the encrypted keystore instead — see [`wallet-setup.md`](./guides/wallet-setup.md).

**`dincli/docker/node/README.md`:** add a dev-vs-production key-management subsection (raw `.env` keys = dev; encrypted keystore on bind-mounted `config/dincli/` = prod; cross-link both new guides). **Also** update the existing `.session` mention to describe it as **legacy cleanup only** — `dincli` no longer writes it.

**Link the new guides** from `Documentation/guides/ipfs.md` and `Developer/DEVELOPMENT_SETUP.md` as a prerequisite step.

**Acceptance:** every doc that instructs wallet/`--account` setup carries the dev-only label + keystore pointer; `.env.example` exists at root (authoritative) + `hardhat/` (signposted) + docker node; docker README `.session` reference updated to legacy-cleanup; no code path removed.

---

### 2.2 — Sub-task 1b: Burner wallet setup guide

**New file:** `Documentation/guides/wallet-setup.md`. Sections:

1. **Why a dedicated burner wallet** — key is loaded into `dincli` to sign on every command; any machine/keystore compromise exposes every asset at that address → use a disposable address.
2. **Recommended tool — OWS (openwallet.sh)** — chain-agnostic, agent-friendly, open-standard keystores; minimal steps to generate a fresh wallet and export its keystore file. **Verify exact OWS commands during 1c-D before finalizing this section** (do not invent commands). If OWS lacks a clean export/CLI, fall back to an `eth-account` generation one-liner and link OWS as optional.
3. **Fund the burner wallet** — Optimism Sepolia faucet for the new address. **Minimum to participate: 10 DIN to stake** (`DinValidatorStake.MIN_STAKE = 10 * 1e18`) **plus ETH for gas** (a small amount for a few txs). Be explicit that staking currency is DIN, gas is ETH; note how DIN is obtained (ETH→DIN via `DinCoordinator`, per `DIN-workflow.md`).
4. **What happens next** — cross-reference `keystore-migration.md` (1d) for how the key file is loaded by `dincli`, and note password is prompted per-command (no cross-invocation cache; D1).

**Link from:** `Documentation/guides/ipfs.md` and `Developer/DEVELOPMENT_SETUP.md` as a prerequisite.

---

### 2.3 — Sub-task 1c: Multi-account support + security/convenience balance (CODE — highest sensitivity)

#### (A) In-memory TTL password cache — replace on-disk `.session` (security-sensitive commit #1)
**Files:** `dincli/cli/utils.py`.

- Module-level `_PASSWORD_CACHE: dict[str, tuple[str, float]] = {}` keyed by account name (default `"default"`), value `(password, expiry_epoch)`.
- TTL via `DIN_PASSWORD_TTL` (seconds, default 900); constant `_PASSWORD_TTL_DEFAULT = 900`.
- `_get_password(name="default")` lookup order: (1) `DIN_WALLET_PASSWORD` env → (2) **in-memory cache** if unexpired → (3) `getpass` prompt. **No disk read.**
- Replace `_cache_password_if_needed` → `_cache_password_in_memory(name, password)`: store with expiry; never touch disk.
- `_clear_session_cache` → clear the in-memory entry; **and** unlink any stale on-disk `CONFIG_DIR/.session` (one-time migration cleanup), then never write it again.
- On `load_account`, if a stale `.session` exists, delete it and log a one-line notice.
- **D1 is explicit in code comments and docs:** this removes cross-invocation caching by design.
- Uses `time.time()` (already imported); no `Date.now`-style hazards.

#### (B) `--keystore <path>` input option (security-sensitive commit #2)
**Files:** `dincli/cli/system.py::connect_wallet`.

- Add `keystore: Optional[Path] = typer.Option(None, "--keystore", help="Import a standard Ethereum JSON keystore file")`; add to mutual-exclusivity list.
- Branch: read JSON keystore → `getpass("Keystore passphrase: ")` → **validate by `Account.decrypt(...)`** to derive the address. On success, **derive checksum address from the decrypted key** and persist with normalized metadata (see below). Re-prompt/exit on wrong passphrase; exit on missing file / malformed JSON.
- **Metadata normalization:** do **not** trust the keystore's own `address` field (may be absent / odd casing). Use the **shared wrapper schema** (below) so `list-accounts` shows a reliable address without decrypting. For imported keystores `source: "imported"` and the original keystore is preserved **verbatim** inside `keystore` ("key never re-encoded").

#### Shared wrapper schema for ALL new named encrypted writes (feedback #2)
Every new named encrypted wallet — whether created from interactive `getpass`, positional arg, `--key-file`, non-demo `--account`, **or** `--keystore` import — is written in one consistent wrapper so `list-accounts` never needs to decrypt:
```json
{
  "version": 1,
  "address": "0x<checksummed-derived-from-decrypted-key>",
  "keystore": { ...standard eth-account keystore (Account.encrypt output, or original for imports)... },
  "source": "created" | "imported",
  "name": "<name>"
}
```
- For non-import paths: `keystore = Account.encrypt(privatekey, password)`, `source="created"`.
- For imports: `keystore =` the original file content (unchanged), `source="imported"`.
- `address` is always derived from the decrypted private key and checksummed — never copied from an untrusted field.
- **`load_account` must read three forms** for back-compat: (1) this wrapper, (2) a legacy bare eth-account keystore (`CONFIG_DIR/wallet.json` from before this change), (3) legacy demo plaintext (`{"demo_mode": true, "private_key": ...}`). A small `_extract_keystore(data)` helper normalizes (1)/(2) before `Account.decrypt`.

#### (C) Named multi-account keystore + runtime selection (security-sensitive commit #2)
**Files:** `dincli/cli/system.py`, `dincli/cli/utils.py`, `dincli/cli/context.py`, `dincli/main.py`.

- **Storage:** `CONFIG_DIR/wallets/wallet_<name>.json`. Legacy `CONFIG_DIR/wallet.json` continues to load as the `default` account (back-compat).
- **Default precedence (feedback #3 — state explicitly):** when resolving `name == "default"`, **`CONFIG_DIR/wallets/wallet_default.json` wins**; legacy `CONFIG_DIR/wallet.json` is used only as a fallback when no named default exists. `connect-wallet --name default` writes the new `wallets/wallet_default.json` (it does **not** overwrite the legacy file). Document this precedence in `keystore-migration.md`.
- **Name validation:** reject anything not matching `^[A-Za-z0-9_-]{1,64}$` (no path separators, no `..`, no empty/Unicode). Single helper `validate_account_name(name)` in `utils.py`, used by `connect-wallet --name`, `--wallet`, and `list-accounts`.
- **File permissions (feedback #5 — handle existing files):** `os.open(..., 0o600)` only sets mode on *creation*; truncating an existing loose-mode file keeps the old mode. So **write atomically**: write to `wallets/.wallet_<name>.json.tmp` created with `0o600`, then `os.replace()` onto the target (and `os.chmod(target, 0o600)` defensively after). Create `wallets/` with `0o700` and `os.chmod` it `0o700` if it already exists. Same atomic-replace + chmod discipline for the legacy `wallet.json` path.
- **Save side:** `connect-wallet --name <name>` (default `default`) writes `wallets/wallet_<name>.json` using the shared wrapper schema for **any** input path (interactive / `--keystore` / `--key-file` / positional / non-demo `--account`).
- **Load side:** `load_account(name="default")` resolves `wallets/wallet_<name>.json` (named default wins), else legacy `wallet.json`. Handles all three forms via `_extract_keystore`; passes `name` to `_get_password(name)` so the in-memory cache is keyed per account.
- **Runtime selection (feedback #3 — the critical wiring):**
  - Add top-level `--wallet <name>` option to `main()` (`dincli/main.py`), mirroring `--network`.
  - `DinContext.__init__` gains `wallet_name` attr; add `select_wallet(name)` mirroring `select_network`; resolution order: `--wallet` flag → `DIN_WALLET_NAME` env → config `wallet_name` → `"default"`.
  - `DinContext.account` calls `load_account(name=self.resolved_wallet_name)` instead of the bare call.
  - Without this, `list-accounts` would exist but commands couldn't actually *use* a non-default account.
- **`read_wallet` (`system.py:394-420`) and `todo`/doctor (`system.py:641-644`) must be updated (feedback #1):** both currently hit `WALLET_FILE.exists()` directly and will mis-report named wallets. Rewrite to resolve the active wallet via the same name logic (`--wallet`/`DIN_WALLET_NAME`/config/`default`) and the wrapper-aware loader. `todo` should also note any named wallets present.
- **Active-wallet visibility (feedback #6):** add the active wallet **name** to `DinContext.get_en_w3_account_console()` (`context.py:86-94`), which already prints the active address/network — so every command surfaces which wallet it's using. `list-accounts` marks the active one too.
- **New command `dincli system list-accounts`:** enumerate `CONFIG_DIR/wallets/*.json` + legacy `wallet.json`; print `name → address` (read from the normalized `address` field — no decrypt needed); mark the **single** active default. **Dedup rule (feedback #3):** if `wallets/wallet_default.json` exists, show it as the default and **do not** also show legacy `wallet.json` as a second "default" row — only surface legacy (labelled `default (legacy)`) when no named default exists.

#### (D) OWS integration feasibility (research + write-up)
**Deliverable:** findings + recommendation in the PR description; keeps `wallet-setup.md` §2 accurate.
- Determine OWS's actual interface (CLI subprocess / local socket / SDK) — **verify externally before documenting commands; behavior may have changed.**
- Assess: can `dincli` (i) enumerate named accounts and (ii) request a **signed transaction** without holding the raw key? Failure modes: OWS not running, account not found, wrong chainId.
- Recommend whether **named multi-keystore (C)** or **OWS delegation** is the production path. **Default: document-only** unless OWS exposes a clean programmatic signing/enumeration interface; if it doesn't, keep integration document-only and say so.

#### Tiers table — emit in PR description **and** `wallet-setup.md`
| Path | Convenience | Security | Recommended for |
|---|---|---|---|
| `ETH_PRIVATE_KEY_<n>` in `.env` | High (multi-acct, no prompts) | Low (plaintext on disk) | Local dev, automated testing |
| Interactive `getpass` + encrypted keystore | Medium (**prompt per command**; in-mem cache only within one process) | High (encrypted at rest, pw in memory only) | Production (current best) |
| `--keystore <path>` JSON keystore input | Medium (passphrase prompt) | High (external keystore, key never re-encoded) | Production validators w/ OWS/external key mgmt |
| `DIN_WALLET_PASSWORD` env | High (no prompts across commands) | Medium (pw plaintext in env/`.env`) | Unattended automation / CI |
| OWS delegation (if feasible) | High (named accts, no raw key in dincli) | Highest (dincli never sees the key) | Production wanting full key isolation |

> Note the deliberate change vs. the task's table: the encrypted-keystore row now says "prompt per command," reflecting D1 (no cross-invocation cache). Added a `DIN_WALLET_PASSWORD` row to show the only no-prompt-across-commands option that exists today.

**Acceptance for 1c:**
- All existing paths still work (regression-tested).
- `--keystore <path>` imports a standard keystore (passphrase prompt) with normalized metadata.
- All new named encrypted writes use the shared wrapper schema; `load_account` reads wrapper + legacy-bare + demo forms.
- Named store + `--name` save + top-level `--wallet`/`DIN_WALLET_NAME` runtime selection + `list-accounts` all work; legacy single-wallet still loads as `default`; named default precedence over legacy is explicit; no duplicate default rows.
- `read_wallet` and `todo`/doctor honor the active wallet (not just legacy `wallet.json`).
- Active wallet **name** surfaced via `get_en_w3_account_console` + `list-accounts`.
- Account names validated (`^[A-Za-z0-9_-]{1,64}$`); wallet files `0o600` even when overwriting an existing loose-mode file (atomic temp + replace + chmod); `wallets/` dir `0o700`.
- Password cache in-memory only; no `.session` written; stale `.session` cleaned up.
- OWS feasibility documented in PR.
- **PR flagged `needs-security-review`; Umer reviews before merge.**

---

### 2.4 — Sub-task 1d: Keystore migration guide

**New file:** `Documentation/guides/keystore-migration.md`. Sections:
1. **What changed** — old `.env` / `PRIVATE_KEY=` pattern vs. new encrypted keystore; **and** that cross-invocation password caching was removed (D1) — passphrase is now entered per command unless `DIN_WALLET_PASSWORD` is set.
2. **How to migrate an existing key (feedback #4 — go through the import path, never hand-write internal files):** the `eth-account` one-liner generates a **standard temporary Ethereum keystore** (`Account.encrypt(...)` → `./keystore.json`), which the operator then imports:
   ```bash
   dincli system connect-wallet --keystore ./keystore.json --name validator
   ```
   `dincli` produces the wrapped internal file; the operator deletes the temp keystore afterward. Same flow for an OWS-exported keystore (commands verified in 1c-D). **Do not** instruct users to hand-create `wallets/wallet_<name>.json` (the wrapper schema is internal).
3. **How to update operator setup** — which env var to replace, where the keystore path/`DIN_WALLET_NAME` goes in `docker-compose.yml` / operator `.env`; keystore lives on the bind-mounted `config/dincli/` volume.
4. **What persists across container restarts** — keystore file persists on the bind-mounted volume; the passphrase is **never stored** and must be entered each `connect-wallet` (and each command, per D1, unless `DIN_WALLET_PASSWORD` is set).

**Cross-link** from `wallet-setup.md` §4 and the docker README.

---

## 3. Tests

Mirror `tests/` style (`monkeypatch` + `typer.testing.CliRunner`, see `tests/test_dintoken.py`). Add `tests/test_connect_wallet.py`:

- **Regression — every existing path still resolves an account:** positional key, `--key-file`, `--account <n>` (demo + env mocked), interactive getpass (monkeypatch `getpass`), demo plaintext wallet.
- **`--keystore <path>`:** valid keystore + passphrase → saved (wrapped metadata, derived checksum address) + loadable; wrong passphrase → exit 1; missing file → exit 1; malformed JSON → exit 1; keystore missing/odd-cased `address` field → still normalized correctly.
- **Named accounts + runtime selection:** save two named keystores → `list-accounts` shows both + addresses (no decrypt); `--wallet <name>` / `DIN_WALLET_NAME` selects the right account through `DinContext.account`; legacy `wallet.json` loads as `default`; **named `wallet_default.json` takes precedence over legacy** and `list-accounts` shows only one default row.
- **`read_wallet` / `todo` named-wallet awareness:** with only a named (non-legacy) wallet present, `read_wallet` succeeds and `todo` reports it (regression for feedback #1).
- **Wrapper schema:** a wallet created via interactive/positional/`--key-file`/`--account` is stored wrapped with a correct derived `address` and `source="created"`; an imported one has `source="imported"` and byte-identical inner `keystore`.
- **Name validation:** `..`, `/`, empty, >64 chars, unicode → rejected with exit 1.
- **File permissions:** created wallet files are `0o600` (`stat` check); **overwriting a pre-existing `0o644` wallet file still ends at `0o600`** (atomic-replace test).
- **In-memory password cache (D1):** prompt called once when one process decrypts twice; cache expires after TTL (monkeypatch `time.time`); **no `.session` created**; stale `.session` removed on run; **no cross-process persistence** (new cache dict ⇒ prompt again — assert this is the documented behavior).
- **Mutual exclusivity:** any two of {positional, `--key-file`, `--account`, `--keystore`} → exit 1.

Run `pytest tests/test_connect_wallet.py -v` + full `pytest`.

---

## 4. Sequencing & commits

Security code split into **two** reviewable commits (feedback): password-cache removal first, then named-keystore/import.

1. `docs(env): add .env.example templates + dev/prod key callouts` (1a)
2. `docs(guides): add wallet-setup burner-wallet guide` (1b)
3. `docs(guides): add keystore-migration guide` (1d)
4. `feat(wallet): in-memory password cache, remove on-disk .session` (1c-A) ← **security-sensitive #1**
5. `feat(wallet): --keystore import + named multi-account store + --wallet selection + list-accounts` (1c-B/C) ← **security-sensitive #2**
6. `test(wallet): connect-wallet regression + new-path coverage` (tests)
7. PR description: tiers table + **OWS feasibility write-up** (1c-D) + the documented deviations (D1, D2).

> Flag the PR `needs-security-review`; do not merge before Umer reviews commits 4–5.

---

## 5. Open questions for the PR (the two big ones are now decided — D1, D2)

1. **Confirm D1** (cross-invocation password caching removed; no OS-keyring added in Part 1) with Umer — acceptable, or should an OS keyring (`keyring`) be in scope?
2. **Confirm D2** (`--account` int stays dev/env; `--name` saves; `--wallet` selects) with the task author, since it deviates from the literal "`--account <name>`" wording.
3. **`hardhat/.env.example`** is signposted as non-authoritative (Hardhat reads root `../.env`) — confirm acceptable vs. not creating it at all.
4. **OWS interface reality (1c-D)** — determines whether OWS delegation is recommended/prototyped or document-only, and the exact commands in `wallet-setup.md` §2.

---

## 6. Files touched (summary)

**New:** `/.env.example`, `hardhat/.env.example`, `Documentation/guides/wallet-setup.md`, `Documentation/guides/keystore-migration.md`, `tests/test_connect_wallet.py`

**Modified:**
- `dincli/cli/system.py` (`connect_wallet`: `--keystore`, `--name` + wrapper save + atomic perms; `read_wallet` + `todo` → active-wallet aware; new `list-accounts`)
- `dincli/cli/utils.py` (`load_account(name=)` + `_extract_keystore` for 3 forms, in-memory password cache, named-store paths + atomic `0o600`/`0o700` writes, `validate_account_name`, `.session` cleanup)
- `dincli/cli/context.py` (`wallet_name` + `select_wallet`; `account` → `load_account(name=...)`; active wallet name in `get_en_w3_account_console`)
- `dincli/main.py` (top-level `--wallet` option → `select_wallet`)
- `dincli/docker/node/.env.example` (key-mgmt note), `dincli/docker/node/README.md` (dev-vs-prod section + `.session` legacy note)
- `Documentation/setup.md`, `GettingStarted.md`, `common.md`, `Model-workflow.md`, `clients.md`, `services.md`, `ReadMe.md`, `technical/DINCLI_*`, `Developer/issues/validator-operations.md`, `Developer/tooling/model-owner-contracts.md` (prod callouts where wallet/`--account` setup is instructed — audit each)
- `Documentation/guides/ipfs.md`, `Developer/DEVELOPMENT_SETUP.md` (link wallet-setup as prerequisite)

**Not touched (deliberately):** SIGTERM/signal handling (T0.2a → P4); demo-mode plaintext wallet path (already mock-only).
