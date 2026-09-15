# Part 2 Implementation Summary — Filecoin Provider Adapter (Lighthouse)

**Plan:** `Plans/archive/part2-filecoin-lighthouse.md`
**Branch:** `feat/validator-readiness`
**Date:** 2026-07-03

---

## What was implemented

### 1. New module: `dincli/services/ipfs_lighthouse.py`
- `upload_via_lighthouse(config, file_path)` — POSTs to `upload.lighthouse.storage/api/v0/add` with `Bearer` auth, extracts `response["data"]["Hash"]` (nested shape, different from Filebase's flat response). Raises `RuntimeError` on malformed responses.
- `retrieve_via_lighthouse(config, cid)` — GETs from `gateway.lighthouse.storage/ipfs/{cid}` (no auth), streams response.
- `_raise_for_http_error` — duplicated locally to avoid circular import with `ipfs.py`.

### 2. Dispatch wiring in `dincli/services/ipfs.py`
- `upload_to_ipfs` and `retrieve_from_ipfs` now dispatch to the lighthouse provider via `upload_via_lighthouse` / `retrieve_via_lighthouse`.
- `_provider_label` returns `"Lighthouse (Filecoin)"` for the `"lighthouse"` key.
- Import from `dincli.services.ipfs_lighthouse` added.

### 3. D6 — IPFS_PROVIDER env var for provider selection
- `resolve_ipfs_config()` in `utils.py` checks `IPFS_PROVIDER` env var as a fallback when no `ipfs_provider` is set in config. Config value wins if set (precedence: config > env > default `"env"`).
- Applies to all providers (`env`, `filebase`, `lighthouse`, `custom`), not just Lighthouse.

### 4. D7 — Provider-scoped API keys
- API keys are now stored per-provider: `ipfs_api_key_<provider>` instead of one flat `ipfs_api_key`.
- `resolve_ipfs_config()` resolves keys in order: (1) scoped key, (2) legacy flat `ipfs_api_key` for `filebase` only (back-compat), (3) `LIGHTHOUSE_API_KEY` env var for `lighthouse`, (4) `None`.
- `configure_ipfs` validates each provider's key independently, preventing silent key reuse across providers.
- Legacy flat field still written for `filebase` when `--api-key` is provided (back-compat).

### 5. CLI updates in `dincli/cli/system.py`
- `configure_ipfs` `--provider` help text now lists `lighthouse`.
- No-args display shows Lighthouse source info.
- `configure_ipfs` stores keys per-provider; validates each provider independently.
- `todo()` IPFS diagnostics has a `lighthouse` branch mirroring `filebase`.

### 6. Documentation updates
- `Documentation/guides/ipfs.md`: updated to four modes, added full `lighthouse` section, updated migration notes.
- `CLAUDE.md`: updated to four backends, added Lighthouse.
- `Documentation/ReadMe.md`: updated to four modes.
- `Documentation/setup.md`: added `Option B — Lighthouse`, renumbered env to C and custom to D.

### 7. Tests
- **New file:** `tests/test_ipfs_lighthouse.py` — 6 tests covering upload (nested hash extraction, malformed response, missing key, HTTP error) and retrieve (gateway URL, HTTP error).
- **Extended:** `tests/test_ipfs_config.py` — 6 new tests for D6/D7 (provider via config, provider via env var, precedence rule, Filebase legacy flat key regression, cross-provider isolation, env-provider regression).

---

## Key design decisions (referenced in plan)

- **D5**: Lighthouse is a first-class provider (`"lighthouse"` in `SUPPORTED_IPFS_PROVIDERS`), not the generic `custom` path.
- **D6**: `IPFS_PROVIDER` env var is a fallback (config wins); precedence rule mirrors Part 1's D-decisions.
- **D7**: Provider-scoped keys fix the silent-misconfiguration bug where switching providers could silently reuse another provider's key.

## Files changed
| File | Status |
|------|--------|
| `dincli/services/ipfs_lighthouse.py` | **New** |
| `dincli/services/ipfs.py` | Modified (dispatch + label) |
| `dincli/cli/utils.py` | Modified (SUPPORTED_IPFS_PROVIDERS, resolve_ipfs_config) |
| `dincli/cli/system.py` | Modified (configure_ipfs, todo diagnostics) |
| `Documentation/guides/ipfs.md` | Modified |
| `CLAUDE.md` | Modified |
| `Documentation/ReadMe.md` | Modified |
| `Documentation/setup.md` | Modified |
| `tests/test_ipfs_lighthouse.py` | **New** |
| `tests/test_ipfs_config.py` | Modified (new test cases) |

## Not touched
- No contract changes
- No CID normalization changes
- No `custom`/`env`/`filebase` provider implementation changes (their behavior preserved through resolver compatibility)

## Commits
```
0333e34 test(ipfs): add Lighthouse provider tests + regression coverage for provider selection and API-key scoping
332a209 docs(ipfs): document the lighthouse provider; fix stale three-provider references
c9cb1d5 feat(ipfs): IPFS_PROVIDER env var + provider-scoped API keys (D6/D7)
0ed11bd feat(ipfs): add Lighthouse (Filecoin) provider adapter
```
