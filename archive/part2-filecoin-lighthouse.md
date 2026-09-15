# Implementation Plan — Part 2: Filecoin Provider Adapter (Lighthouse)

**Parent task:** `task_300626_3` (P3-T0.2b + Filecoin adapter), Part 2 of `Developer/tasks/task_300626_3.md`
**Branch:** `feat/validator-readiness` (continue on same branch as Part 1)
**Roadmap ref:** `Developer/discussion/add-filecoin-support.md` — "Now (P3 — can start independently)"
**Deadline in task doc:** end of Jul 3 (today) — this is independent of Part 1's keystore work and doesn't block on it.

---

## 0. Guiding principles

1. **Mirror the existing `filebase` provider exactly.** `dincli/services/ipfs.py` already has a working pattern for a third-party pinning service (`_upload_via_filebase`/`_retrieve_via_filebase`, `FILEBASE_IPFS_*` URL constants, config-based API key). Lighthouse should slot in the same way — same dispatch structure, same error handling, same `configure-ipfs` UX — not a bespoke mechanism.
2. **No contract or CID changes.** Confirmed by both the task and the discussion doc: this is a pure `dincli/services/ipfs.py` adapter. Nothing else in the protocol changes.
3. **No invented API details.** Given the OWS incident in Part 1, every Lighthouse endpoint/header/response-shape claim below was checked against a primary source before being written down (see §1b) — not assumed from the task doc's or discussion doc's prose.

### Decisions locked before coding

**D5 — Implement as a genuine first-class provider (`"lighthouse"` in `SUPPORTED_IPFS_PROVIDERS`), not the generic dynamic-module `custom` path.**
The discussion doc says "using the existing `custom` provider path," which is accurate at the *architectural* level (no contract changes needed either way) but imprecise about the *mechanism*: `custom` in this codebase is a specific feature — `_load_custom_fn()` dynamically imports a user-supplied `.py` file at a configured `service_path` (see `dincli/services/ipfs.py:22-37`). That's for operators who bring their own storage backend; it is not how `env` or `filebase` (the two other shipped providers) work, and it's not what the task's concrete deliverables ask for. The task explicitly names a dedicated module (`dincli/services/ipfs_lighthouse.py`), a dedicated env var, and a dedicated test file — that's the shape of a first-class provider like `filebase`, not a `custom`-path example. Building it as first-class means it's shipped, tested, and documented for every operator without requiring them to hand-write an adapter module themselves.

**D6 — Implement `IPFS_PROVIDER` for real; API key resolution is config-first with an env fallback.**
v1 of this plan rejected `IPFS_PROVIDER` as provider *selection* and kept selection config-only, treating the task's env-var wording as an authoring assumption mismatch (by analogy with the Part 1 `configure-network`/`wallet_name` issue). An audit correctly pushed back: the task doesn't just mention `IPFS_PROVIDER` in passing, it lists **"provider selection from env vars" as an explicit required test case** (`Developer/tasks/task_300626_3.md:158`), twice-stated. That's a stated deliverable, not incidental phrasing — dropping it needs to be a pre-implementation call, not a PR footnote. Verified the task wording again and decided to build it rather than block on it, since a clean precedence rule is straightforward to define:
- **Provider selection precedence:** persisted config `ipfs_provider` (set via `configure-ipfs --provider ...`) wins if present; `IPFS_PROVIDER` env var is used only when no provider is configured yet. This mirrors the precedence direction already established for D-decisions in Part 1 and for the API-key fallback below (persistent explicit configuration beats ambient environment state) — an operator who explicitly ran `configure-ipfs` shouldn't have that silently overridden by a leftover shell variable.
- This is implemented generically in `resolve_ipfs_config()` (the env var name `IPFS_PROVIDER` isn't Lighthouse-specific), so it also becomes available for `env`/`filebase`/`custom` — a small scope increase over "just Lighthouse," but the alternative (a Lighthouse-only env override mechanism with a generically-named env var) would be more confusing, not less.
- Invalid values from either source behave identically to today's behavior for invalid *config* values: no new validation is added in `resolve_ipfs_config()` (there isn't any today), so an unrecognized provider still surfaces as `NotImplementedError` at upload/retrieve time. This is a deliberate consistency choice, not an oversight — noted here so it isn't mistaken for one during review.
- **API key resolution stays config-first with an env fallback**, per the original reasoning: `filebase`'s real pattern (`dincli/cli/utils.py:209-224`, `dincli/cli/system.py:1046-1090`) is `configure-ipfs --api-key`, persisted to config — not an env var. `LIGHTHOUSE_API_KEY` is honored as a fallback when no key is configured, satisfying the task's literal ask without inventing a new mechanism other providers don't have.
Flag the provider-selection-precedence direction in the PR for the task-giver to confirm, but implement it now rather than stalling on it — same operating mode as Part 1's D1–D4.

**D7 — API keys become provider-scoped in config; fixes a silent-misconfiguration bug the first draft missed entirely.**
An audit caught a real bug in v1's design: `configure_ipfs` stores *all* provider API keys under one shared `config["ipfs_api_key"]` field (`dincli/cli/system.py:1073,1086`, `dincli/cli/utils.py:221`). v1's validation change (`if selected_provider in ("filebase", "lighthouse") and not (api_key or existing_api_key): ...`) would let an operator run `configure-ipfs --provider lighthouse` with **no** `--api-key`, see it succeed because a *Filebase* key already exists in `existing_api_key`, and silently end up trying to authenticate to Lighthouse with a Filebase token — a confusing auth failure at upload time instead of a clear error at config time.
Fix: store keys per-provider — `config["ipfs_api_key_<provider>"]` — instead of one flat field. `resolve_ipfs_config()` resolves, in order: (1) the scoped key for the active provider, (2) **only for `filebase`**, the legacy flat `ipfs_api_key` (back-compat for operators who configured Filebase before this change — confirmed via `tests/test_ipfs_config.py` that no test currently pins the flat-key behavior, so this fallback is purely additive), (3) **only for `lighthouse`**, the `LIGHTHOUSE_API_KEY` env var (D6), (4) `None`. This is the same shape as the Part 1 "named wallet wins, legacy file is fallback" migration pattern — appropriate here since it's the same class of problem (a new, more specific mechanism superseding an old flat one without breaking existing users).

---

## 1. Grounding facts

### 1a. Existing architecture (verified by reading the code directly)

| Piece | Location | Notes |
|---|---|---|
| Provider dispatch | `dincli/services/ipfs.py::upload_to_ipfs` / `retrieve_from_ipfs` | `if provider == "env": ... elif provider == "filebase": ... elif provider == "custom": ...` — needs a 4th branch. |
| Provider allowlist | `dincli/cli/utils.py:116` | `SUPPORTED_IPFS_PROVIDERS = ("env", "filebase", "custom")` |
| Config resolution | `dincli/cli/utils.py:209-224` (`resolve_ipfs_config`) | Builds `IPFSConfig(provider, api_url_add, api_url_retrieve, api_key, api_secret, service_path)` — `api_key`/`api_secret` come from `config.json`, not env. |
| Filebase constants | `dincli/cli/utils.py:127-129` | `FILEBASE_IPFS_ADD_URL`, `FILEBASE_IPFS_CAT_URL`, `FILEBASE_IPFS_PIN_URL` — flat strings, no separate module. |
| Filebase upload/retrieve | `dincli/services/ipfs.py:119-157`, `203-224` | `Authorization: Bearer <api_key>`, multipart field `"file"`, response `.json()["Hash"]` — flat, not nested. |
| Provider config command | `dincli/cli/system.py:1046-1090` (`configure_ipfs`) | Validates provider is in `SUPPORTED_IPFS_PROVIDERS`, requires `--api-key` for `filebase`, persists to `config.json`. |
| Diagnostics | `dincli/cli/system.py:815-829` (inside `todo()`) | `elif ipfs_config.provider == "filebase": ...` branch checks `ipfs_config.api_key is None`. |
| Docs structure | `Documentation/guides/ipfs.md` | One `##` section per provider (`env`, `filebase`, `custom`), each with a `configure-ipfs` example and notes. |
| Test pattern | `tests/test_ipfs_config.py` | Monkeypatches `CONFIG_DIR`/`CONFIG_FILE`, writes real `config.json`/`.env` fixtures, patches `requests.post` with a `DummyResponse` class, asserts on `resolve_ipfs_config()` and `ipfs.upload_to_ipfs()`. |

### 1b. Lighthouse API — verified against primary sources (not the task doc's prose)

WebFetch against `docs.lighthouse.storage` pages directly 404'd/didn't expose raw endpoint details (rendered JS docs site). Fetched the **raw GitHub markdown source** of the official docs repo instead (`raw.githubusercontent.com/lighthouse-web3/gitbook/main/...`), which is a primary source:

| Fact | Value | Source |
|---|---|---|
| Upload endpoint | `POST https://upload.lighthouse.storage/api/v0/add` | `lighthouse-web3/gitbook/how-to/upload-data/file.md` |
| Auth header | `Authorization: Bearer <API_KEY>` | same |
| Multipart field | `file` | same |
| Upload response shape | `{"data": {"Name": "...", "Hash": "...", "Size": "..."}}` — **nested under `"data"`, unlike Filebase's flat `{"Hash": ...}`** | same |
| Retrieval | Public gateway: `GET https://gateway.lighthouse.storage/ipfs/{Hash}` | corroborated by `lighthouse-web3/gitbook` and lighthouse.storage marketing site |
| API key creation (CLI) | `lighthouse-web3 wallet` / `create-wallet` / `import-wallet --key <key>`, then `lighthouse-web3 api-key --new` (npm package `@lighthouse-web3/sdk`) — requires an Ethereum wallet since key creation is signature-authenticated | `lighthouse-web3/gitbook/how-to/create-an-api-key.md` |
| API key creation (web) | Files Dapp at `files.lighthouse.storage` → API key section | same |

**Not yet verified — flag for a live smoke test during implementation, not to be assumed:** whether gateway retrieval truly requires zero auth in all cases (public-gateway convention strongly suggests yes, but no primary source explicitly states "no Authorization header required"). Before merging, run one real `curl -X POST .../api/v0/add` + one real `curl .../ipfs/<hash>` with a live API key and confirm both match this table exactly — the same discipline that would have caught the OWS `export` fabrication earlier.

---

## 2. Work breakdown

### 2.1 New module: `dincli/services/ipfs_lighthouse.py`

Self-contained (no import back into `ipfs.py`, avoids circularity), mirroring `_upload_via_filebase`/`_retrieve_via_filebase`'s shape and error-message format:

```python
import requests
from pathlib import Path
from urllib.parse import quote

LIGHTHOUSE_UPLOAD_URL = "https://upload.lighthouse.storage/api/v0/add"
LIGHTHOUSE_GATEWAY_URL = "https://gateway.lighthouse.storage/ipfs"


def _raise_for_http_error(response: requests.Response, action: str, provider: str):
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        details = (response.text or "").strip()
        details = details[:300] if details else "No error details returned."
        raise RuntimeError(f"{provider} {action} failed [{response.status_code}]: {details}") from exc


def upload_via_lighthouse(config, file_path: Path) -> str:
    if not config.api_key:
        raise ValueError("Lighthouse IPFS provider requires an API key (config 'ipfs_api_key_lighthouse' or LIGHTHOUSE_API_KEY env var).")

    headers = {"Authorization": f"Bearer {config.api_key}"}
    with file_path.open("rb") as handle:
        response = requests.post(
            LIGHTHOUSE_UPLOAD_URL,
            files={"file": (file_path.name, handle, "application/octet-stream")},
            headers=headers,
            timeout=120,
        )
    _raise_for_http_error(response, "upload", "Lighthouse")
    try:
        return response.json()["data"]["Hash"]          # nested — different from Filebase's flat shape
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(f"Lighthouse upload returned an unexpected response shape: {exc}") from exc


def retrieve_via_lighthouse(config, cid: str) -> requests.Response:
    response = requests.get(f"{LIGHTHOUSE_GATEWAY_URL}/{quote(cid)}", stream=True, timeout=30)
    _raise_for_http_error(response, "download", "Lighthouse")
    return response
```
`_raise_for_http_error` is duplicated locally verbatim (matches `ipfs.py`'s version exactly) rather than imported from `ipfs.py`, which would create a circular import (`ipfs.py` needs to import this module for dispatch). The `.json()["data"]["Hash"]` access is wrapped so a malformed/changed Lighthouse response surfaces as a clear `RuntimeError` instead of a raw `KeyError`/`JSONDecodeError` leaking out of the adapter — this is exactly the kind of provider-side response change the discussion doc's "document any API surprises" ask is meant to catch, so it needs a clean, attributable error rather than a stack trace.

### 2.2 Wire into `dincli/services/ipfs.py`

- Import `upload_via_lighthouse`, `retrieve_via_lighthouse` from the new module.
- `upload_to_ipfs`: add `elif provider == "lighthouse": cid = upload_via_lighthouse(config, normalized_path)`.
- `retrieve_from_ipfs`: add `elif provider == "lighthouse": response = retrieve_via_lighthouse(config, hash_value); _write_response_to_file(response, safe_path); status_code = response.status_code`.
- `_provider_label`: add `"lighthouse": "Lighthouse (Filecoin)"`.

### 2.3 Config plumbing (`dincli/cli/utils.py`)

- `SUPPORTED_IPFS_PROVIDERS = ("env", "filebase", "lighthouse", "custom")`.
- `resolve_ipfs_config()`, provider selection (D6):
  ```python
  configured_provider = config.get("ipfs_provider")
  provider = normalize_ipfs_provider(configured_provider) if configured_provider else normalize_ipfs_provider(get_env_key("IPFS_PROVIDER", verbose=False))
  ```
  (config wins if set; `IPFS_PROVIDER` env var used only when no provider is configured yet — `normalize_ipfs_provider(None)` already returns `"env"`, so this preserves today's default when neither is set.)
- `resolve_ipfs_config()`, API key resolution (D7 — provider-scoped, replaces the single flat `ipfs_api_key` read):
  ```python
  api_key = _clean_optional_string(config.get(f"ipfs_api_key_{provider}"))
  if not api_key and provider == "filebase":
      api_key = _clean_optional_string(config.get("ipfs_api_key"))          # legacy back-compat, filebase only
  if not api_key and provider == "lighthouse":
      api_key = _clean_optional_string(get_env_key("LIGHTHOUSE_API_KEY", verbose=False))
  ```

### 2.4 CLI plumbing (`dincli/cli/system.py`)

- `configure_ipfs`:
  - Update `--provider` help text to include `lighthouse`.
  - Store to the provider-scoped field: `config[f"ipfs_api_key_{selected_provider}"] = api_key.strip()` instead of the flat `config["ipfs_api_key"]` (D7). Keep writing the flat field too *only* when `selected_provider == "filebase"`, so existing tooling/back-compat readers of the flat key for Filebase keep working — new providers (Lighthouse) never touch the flat field.
  - Validation: `existing_api_key` must be looked up as the *scoped* key (`config.get(f"ipfs_api_key_{selected_provider}")`, with the legacy-flat/env fallbacks from D7 folded in) — this is what actually closes the audit's "switching provider silently reuses the wrong key" bug. Add `lighthouse` to the same validation branch as `filebase` (`if selected_provider in ("filebase", "lighthouse") and not (api_key or resolved_existing_key): ...`).
  - Add `elif active.provider == "lighthouse":` in the no-args display branch ("Source: Lighthouse token stored in dincli config (`ipfs_api_key_lighthouse`) or LIGHTHOUSE_API_KEY env var").
- `todo()`'s IPFS diagnostics block (`~system.py:815-829`): add `elif ipfs_config.provider == "lighthouse":` mirroring the `filebase` branch, checking `ipfs_config.api_key is None` (this already reflects the D7-resolved value since it reads off `IPFSConfig`, not raw config).

### 2.5 Docs

**`Documentation/guides/ipfs.md`** (primary deliverable, per the task):
- Update the "three modes" intro to four; add a `## lighthouse provider` section mirroring the `filebase` section exactly:
  ```bash
  dincli system configure-ipfs --provider lighthouse --api-key <lighthouse_api_key>
  # or: export LIGHTHOUSE_API_KEY=<key>   (fallback if no key is configured)
  ```
  Note: uploads go to Filecoin via Lighthouse's pinning service; retrieval uses Lighthouse's IPFS gateway; API keys are created via `files.lighthouse.storage` or the `lighthouse-web3` CLI (requires a wallet signature — link the Lighthouse docs, don't restate their wallet-linking flow in detail); the provider-scoped-key mechanism (D7) so switching from Filebase doesn't silently reuse its key.
- Update "Migration notes" section: mention the `ipfs_api_key` → `ipfs_api_key_<provider>` scoping change and that existing Filebase configs keep working unchanged.

**Small consistency updates elsewhere** (not full rewrites — these three files currently describe an outdated "three providers" picture that shipping Lighthouse as first-class would make wrong, not just incomplete):
- `CLAUDE.md:67` — "three interchangeable upload/retrieve backends" → four, add Lighthouse to the one-line list. This file is read as authoritative project context on every session, so leaving it wrong is worse than leaving it silent.
- `Documentation/ReadMe.md:11` — "three supported IPFS modes" → four.
- `Documentation/setup.md` — add a brief "Option B — Lighthouse (Filecoin-backed)" alongside the existing "Option A — Filebase" section (mirrors that section's length/depth, doesn't need to be exhaustive since `ipfs.md` is the detailed reference).

### 2.6 Tests

**`tests/test_ipfs_lighthouse.py`** (per task's explicit deliverable) — imports `dincli.services.ipfs_lighthouse` directly, mirrors `tests/test_ipfs_config.py`'s fixture style:
- Upload: mock `requests.post` returning the *nested* `{"data": {"Hash": ...}}` shape, assert `upload_via_lighthouse` extracts `Hash` correctly — this is the one place a copy-paste from Filebase's flat-shape code would silently break.
- Upload malformed-response case: mock `requests.post` returning a shape missing `data`/`Hash` (or non-JSON body), assert `RuntimeError` is raised, not `KeyError`/`JSONDecodeError`.
- Retrieve: mock `requests.get`, assert it is called with the exact expected URL (`https://gateway.lighthouse.storage/ipfs/<cid>`) and method (`GET`, no auth header) — locks down the not-yet-live-verified assumption from §1b as an explicit, checkable contract, and assert the file is written.
- Error case: missing API key → `ValueError` before any HTTP call is attempted (assert `requests.post`/`get` were never called).
- HTTP error case: non-200 response → wrapped `RuntimeError` via `_raise_for_http_error`, matching Filebase's error-message format.

**`tests/test_ipfs_config.py`** (existing file — add regression + new-behavior coverage, don't just rely on the new file):
- Provider selection: `resolve_ipfs_config()` returns `provider == "lighthouse"` when set via `configure-ipfs` (config-sourced).
- Provider selection via env (D6, the task's explicit ask): `IPFS_PROVIDER=lighthouse` with no config `ipfs_provider` set → resolves to `lighthouse`.
- Precedence: config `ipfs_provider` set to `"filebase"` + `IPFS_PROVIDER=lighthouse` env both present → config wins (`filebase`) — locks down the D6 precedence rule as a test, not just prose.
- Invalid provider via env var (e.g. `IPFS_PROVIDER=nonsense`) → behaves the same as an invalid config value already does today (surfaces at use-time via `NotImplementedError`, not at resolution time) — regression-pins the "no new validation" call from D6.
- **Filebase regression:** existing flat `ipfs_api_key` config (pre-this-change format) still resolves correctly when provider is `filebase` (D7 back-compat).
- **Cross-provider isolation (the audit's core bug, now a locked-down test):** config has `ipfs_api_key_filebase` set, provider switches to `lighthouse` with no `ipfs_api_key_lighthouse` and no `LIGHTHOUSE_API_KEY` env — resolves to `api_key is None` (correctly fails closed) rather than reusing the Filebase key.
- Run the full existing `env`-provider test suite in this file unmodified and confirm it still passes — the D6/D7 changes touch shared resolver code every provider depends on.

---

## 3. Sequencing & commits

1. `feat(ipfs): add Lighthouse (Filecoin) provider adapter` — new `ipfs_lighthouse.py`, dispatch wiring in `ipfs.py`.
2. `feat(ipfs): IPFS_PROVIDER env var + provider-scoped API keys` — the D6/D7 changes to `resolve_ipfs_config()`/`configure_ipfs` in `utils.py`/`system.py`. Called out as its own commit since, unlike commit 1, it touches shared resolver code every existing provider depends on — makes it easy for a reviewer to scrutinize the one commit that can regress `env`/`filebase`.
3. `docs(ipfs): document the lighthouse provider; fix stale three-provider references` — `ipfs.md`, `CLAUDE.md`, `ReadMe.md`, `setup.md`.
4. `test(ipfs): add Lighthouse provider tests + regression coverage for provider selection and API-key scoping` — `tests/test_ipfs_lighthouse.py` (new) and `tests/test_ipfs_config.py` (extended), run for real (`pytest tests/test_ipfs_lighthouse.py tests/test_ipfs_config.py -v` + full suite), capture actual output in the PR.
5. PR description: note the D5/D6/D7 deviations from the task's literal wording (custom-path framing, env-var-as-primary-mechanism framing, key-scoping change) with rationale, plus the live-smoke-test result from §1b's not-yet-verified retrieval-auth assumption.

## 4. Definition of done

- `dincli system configure-ipfs --provider lighthouse --api-key <key>` works end-to-end against the real Lighthouse API — **one live smoke test with an actual account**, not just mocks, run manually during implementation and its result (request/response) pasted into the PR description. This is a one-time manual verification step, not part of the automated test suite or CI — local/CI test runs must not depend on a live Lighthouse account or network access.
- `IPFS_PROVIDER=lighthouse` + `LIGHTHOUSE_API_KEY=<key>` (no `configure-ipfs` call at all) is sufficient to upload/retrieve — the task's literal env-var-only deliverable, verified by a mocked test, not just documented.
- Switching provider via `configure-ipfs` without supplying a new `--api-key` never silently reuses another provider's key — verified by the cross-provider-isolation test (§2.6).
- All new tests pass; the full existing `tests/test_ipfs_config.py` suite still passes unmodified — **no behavior regressions** in the `env`/`filebase`/`custom` paths (the correct framing here, since D6/D7 do touch their shared resolver code — "not touched" was the wrong claim in the first draft).
- `pytest` run for real, output captured in the PR (same discipline as Part 1).
- `ipfs.md` documents the provider with accurate, source-checked API key creation steps; `CLAUDE.md`/`ReadMe.md`/`setup.md` no longer describe a stale three-provider picture.
- No changes to any contract or CID normalization code.
- PR notes the D5/D6/D7 deviations for the task-giver to confirm, same as D1-D4 were flagged in Part 1.

## 5. Files touched (summary)

**New:** `dincli/services/ipfs_lighthouse.py`, `tests/test_ipfs_lighthouse.py`
**Modified:** `dincli/services/ipfs.py` (dispatch + label), `dincli/cli/utils.py` (`SUPPORTED_IPFS_PROVIDERS`, `resolve_ipfs_config` provider/key resolution per D6/D7), `dincli/cli/system.py` (`configure_ipfs` scoped-key storage/validation, `todo()` diagnostics), `Documentation/guides/ipfs.md`, `CLAUDE.md`, `Documentation/ReadMe.md`, `Documentation/setup.md`, `tests/test_ipfs_config.py` (regression + new-behavior coverage).
**Not touched:** any contract, `dincli/services/cid_utils.py`, the `env`/`filebase`/`custom` provider *implementations* (their behavior is preserved, though the shared resolver code around them changes — see DoD above), `Developer/discussion/add-filecoin-support.md` (strategy doc, not to be edited — any pushback on its provider recommendation goes in the PR description per the task's own instructions).
