# Implementation Plan — DIN-SDK loaders wave 2 (manifest · runtime)

**Issue:** #20 (DIN-SDK) · **Branch:** `feat/din-sdk` (`fc4232a`)
**Scope:** extract the manifest / `din_info` functions and `ServiceRuntimeContext` into
`dincli/sdk/`, completing the loader tier. Follow-up to `din-sdk-01-loaders`.
**Status:** DRAFT v3 — audit-incorporated; ready to implement.

> **v2 (audit):** (1) the `cache_manifest` CLI wrapper must **catch `ValidationError` → print the
> existing message → `typer.Exit(1)`** (there is no top-level `DinError` handler in `main.py`, and
> `pretty_exceptions_enable=False`, so an escaped `DinError` would dump a traceback); (2) expanded
> the importer inventory to include the `get_manifest_key` role commands; (3) `load_din_info`/
> `save_din_info`/`load_cid_services` read a **packaged resource** (`files("dincli")/config/...`),
> not a config-dir path — add patchable `DIN_INFO_PATH`/`CID_SERVICES_PATH` constants and test via
> those; (4) the freshness-warning `console → logger` move is **intentional output drift**
> (documented), consistent with `din-sdk-01`.
>
> **v3 (audit):** (5) dropped the `dind --help` smoke check — `dind` lives on the child branch
> `feat/din-daemon`, not on `feat/din-sdk` where this plan runs; (6) the negative-id wrapper test
> calls `cache_manifest(-1, "local")` **directly** (asserting `typer.Exit`), not via `task explore`,
> which would drag in wallet/web3 setup.
**Does NOT need Umer's sign-off:** mechanical relocation + presentation-stripping; commits to no
public-interface decision the keystones/DOC7 could overturn. (The *session-coupled* manifest logic
in `DinContext` — `ensure_file_exists`, `_resolve_task_contract_artifact_path`, the `local.json.cid`
cache — stays with the keystones; it needs the `DinSession` abstraction.)

---

## Why this is next / what's in scope

`din-sdk-01` extracted `config/log/web3/ipfs/contracts`. The remaining sign-off-independent loaders
are **manifest** and **runtime**, deferred there because they need IPFS retrieval + `din_info` +
chain reads — all of which now live in the SDK. Verified dependency closure of `cache_manifest`/
`get_manifest` (`utils.py:441-547`): `CACHE_DIR` (`sdk.config`), `load_din_info` (moving here),
`get_contract_instance` (`sdk.contracts`), `retrieve_from_ipfs` (`sdk.ipfs`), `get_cid_from_bytes32`
(`sdk.cid`), `files("dincli")` (stdlib). No `DinContext` dependency (`utils.py` never imports it).

**In scope (from `utils.py`):** `load_din_info` (`:326`), `load_cid_services` (`:331`),
`save_din_info` (`:336`), `cache_manifest` (`:441`), `get_manifest_path` (`:490`), `get_manifest`
(`:507`), `get_manifest_key` (`:548`), `is_ethereum_address` (`:572`); plus `services/runtime.py`.

**Out of scope:** `DinContext`'s manifest/artifact methods (session-coupled → keystones); wallet;
`build_and_send_tx`; anything touching the frozen-contract surface.

---

## The one real design decision — `cache_manifest`'s presentation

`cache_manifest`/`get_manifest` are the only manifest functions with presentation, and it can't move
into `sdk/` (rich `console` / `typer.Exit` would break the import-boundary test). Three couplings:
- `console.print("[red]Error")` + `raise typer.Exit(1)` on negative `model_id` (`utils.py:443-444`).
- a `console.print` freshness warning (`utils.py:534`).
- an entire `info=True` model-info dump, incl. optional genesis-model print (`utils.py:464-478`).

**Decision — split pure logic (SDK) from presentation (CLI shim), preserving backward compatibility
so no callers change:**

- `sdk/manifest.py` (pure, no console/typer):
  - `download_manifest(network, model_id, *, force=False) -> None` — the cache/fetch half of today's
    `cache_manifest`; raises `ValidationError` on negative `model_id` (was `typer.Exit`).
  - `get_model_info(network, model_id, *, include_genesis=False) -> dict` — returns the on-chain
    `getModel(...)` fields (+ genesis CID when asked) as data. This is the content the old `info=True`
    block printed.
  - `get_manifest`, `get_manifest_path`, `get_manifest_key`, `load_din_info`, `save_din_info`,
    `load_cid_services`, `is_ethereum_address`. `get_manifest` calls `download_manifest(...,
    force=True)` when stale (self-contained in the SDK).
  - **Patchable resource constants:** `DIN_INFO_PATH = files("dincli").joinpath("config",
    "din_info.json")` and `CID_SERVICES_PATH = files("dincli").joinpath("config",
    "cid_services.json")` at module top; `load_din_info`/`save_din_info`/`load_cid_services` read
    these (today they inline `files(...)`). This makes them monkeypatchable in tests (audit #3) —
    note `din_info.json` is a *packaged, mutable* resource, not user config.
  - `get_manifest`'s freshness warning → `logger.warning` (via `logging.getLogger("dincli")`, the
    no-cycle rule from `din-sdk-01`). **Intentional output drift (audit #4):** for direct
    `get_manifest` callers this warning moves from a rich-styled stdout line to a logger line (still
    visible via the CLI's text handler on stderr) — the same library-correct trade-off made for the
    config warnings in `din-sdk-01`, not a regression to fix.
- `cli/utils.py` keeps `cache_manifest(model_id, network, info=False, update=False,
  genesis_model_info=False)` as a **thin CLI wrapper** that calls `download_manifest` and, when
  `info`, calls `get_model_info` and does the `console.print` rendering. **It must `try/except
  ValidationError` around `download_manifest` and reproduce today's behavior — print
  `"[red]Error:[/red] Model ID must be non-negative"` and `raise typer.Exit(1)`** (audit #1: there
  is no top-level `DinError` handler in `dincli/main.py` and `pretty_exceptions_enable=False`, so an
  escaped `ValidationError` would show a traceback + regress the clean error). Presentation stays in
  the CLI layer; the caller that passes `info=True` (`cli/task.py:159`) is unchanged.

Net: SDK is presentation-free and boundary-clean; the CLI keeps identical command surface, exit
codes, and error/`info` output — the only change is the incidental freshness-warning styling noted
above.

---

## Ground rules discovered from the code

- **Low test-migration risk (unlike `din-sdk-01`'s config move).** No unit test patches
  `utils.get_manifest` / `load_din_info` / `cache_manifest` / `CACHE_DIR` (grep empty). So the
  re-export shim is transparent for these — the patched-globals trap doesn't apply here. (The
  `tests/dincli/` integration suite is separate / environment-bound and out of scope.)
- **Importers to preserve via shim** (`from dincli.cli.utils import ...`) — regenerate the exact
  list before editing with
  `rg -n "from dincli\.cli\.utils import" dincli tests | rg "get_manifest|load_din_info|save_din_info|load_cid_services|cache_manifest|is_ethereum_address"`:
  `cli/task.py` (`cache_manifest`), `cli/dindao.py` (`load_din_info`,`save_din_info`),
  `cli/system.py` (`load_din_info`,`load_cid_services`), `cli/modelownerd/{task,gi,model}.py`
  (`load_din_info`,`get_manifest`), `cli/context.py` (`get_manifest`,`get_manifest_key`,
  `load_din_info`), and the **`get_manifest_key` role commands** (audit #2): `cli/auditor.py:9`,
  `cli/aggregator.py:8`, `cli/modelownerd/aggregation.py:5`, `cli/modelownerd/auditor_batches.py:7`.
  The re-export covers them all; listed so verification doesn't skip high-traffic role flows.
  `services/runtime.py` is imported by `cli/context.py:24`.
- **`services/runtime.py`** imports `get_manifest,get_manifest_path` from `cli.utils` (`:7`); after the
  move it imports from `sdk.manifest`. It's otherwise pure (a frozen dataclass) → clean move + shim.
- **Boundary:** `sdk.manifest` may import only `sdk.{config,contracts,ipfs,cid}` + stdlib +
  `logging.getLogger`. No `typer`/`rich`/`cli`. The import-boundary test will now walk it.

---

## Phases

### Phase 1 — `sdk/manifest.py`
- Move the 8 functions; strip presentation per the design decision (`ValidationError`, `logger`,
  `get_model_info` returning data). `download_manifest` replaces the fetch half of `cache_manifest`.
- `cli/utils.py`: delete the moved defs; add re-exports
  `from dincli.sdk.manifest import (load_din_info, save_din_info, load_cid_services,
  get_manifest, get_manifest_path, get_manifest_key, is_ethereum_address, download_manifest,
  get_model_info)`; **keep** a `cache_manifest(...)` wrapper (compose `download_manifest` +
  `get_model_info` + `console.print`) for backward compatibility.

### Phase 2 — `sdk/runtime.py`
- Move `services/runtime.py` verbatim; change its import to `from dincli.sdk.manifest import
  get_manifest, get_manifest_path`. Leave `services/runtime.py` as a re-export shim
  (`from dincli.sdk.runtime import ServiceRuntimeContext, build_service_runtime_context`).

---

## Testing

- **Keep the suite green** (baseline 137 passed / 1 skipped): `pytest tests/ --ignore=tests/dincli`.
- **Boundary test auto-covers `sdk.manifest`/`sdk.runtime`** — verifies they pull in no
  `typer`/`rich`/`cli`.
- **New `tests/test_sdk_manifest.py`:**
  - `get_manifest_path` model-id vs task-coordinator branches + the "exactly one identifier"
    `ValueError`s.
  - `is_ethereum_address` valid/invalid.
  - `load_din_info`/`save_din_info`/`load_cid_services` round-trip against a `tmp_path` by
    monkeypatching `sdk.manifest.DIN_INFO_PATH` / `CID_SERVICES_PATH` (NOT `sdk.config` paths — these
    are packaged resources, audit #3).
  - `cache_manifest` CLI wrapper maps `ValidationError` (negative id) → clean message + `typer.Exit`.
    Call `cache_manifest(-1, "local")` **directly** and assert `typer.Exit` is raised — not through
    `task explore`, which first calls `ctx.obj.get_en_w3_account_console(...)` (wallet/web3 setup).
  - `download_manifest` raises `ValidationError` on negative `model_id` (was `typer.Exit`).
  - `get_manifest` freshness/`force` path with a mocked contract + mocked `retrieve_from_ipfs`
    (no live chain/IPFS).
- **Runtime smoke:** `dincli --help`; `python -c "import dincli.cli.context, dincli.services.runtime,
  dincli.cli.task, dincli.cli.dindao, dincli.cli.system"` (shims resolve). (No `dind` check — it
  lives on `feat/din-daemon`, not this branch.)

---

## Risks & mitigations

- **`cache_manifest` behavior drift.** The CLI wrapper must reproduce today's exact prints for
  `info`/`genesis_model_info`. Mitigation: keep the wrapper's `console.print` lines verbatim from
  `utils.py:464-478`; no test asserts them, but preserve for parity; manually eyeball
  `dincli ... explore`-style output if feasible.
- **Boundary regression.** Any stray `console`/`typer` left in `sdk.manifest` turns the boundary test
  red — that's the guardrail; run it each phase.
- **`get_manifest` recursion/logging cycle.** `sdk.manifest` uses `logging.getLogger("dincli")`
  directly (never imports `sdk.log`), per the `din-sdk-01` no-cycle rule.
- **Import order (`utils.py` re-export placement).** `cache_manifest` wrapper references the
  re-exported `download_manifest`/`get_model_info`; put the `from dincli.sdk.manifest import ...`
  above the wrapper definition.

---

## Out of scope (explicit)

- `DinContext` manifest/artifact/`ensure_file_exists`/`local.json.cid` logic → keystones (needs
  `DinSession`).
- Wallet/keystore, `tx.send`, `validate_*`, role operations, CLI-renders-JSON refactor.

---

## Step checklist

- [ ] `sdk/manifest.py`: move 8 fns; `download_manifest` + `get_model_info`; strip console/typer → `ValidationError`/`logger`
- [ ] `cli/utils.py`: re-exports (above the wrapper) + `cache_manifest` CLI wrapper preserving `info`/genesis prints
- [ ] `sdk/runtime.py`: move + repoint import to `sdk.manifest`; shim `services/runtime.py`
- [ ] `tests/test_sdk_manifest.py`; boundary test covers manifest/runtime; full suite green + smoke imports
- [ ] Commit; push `feat/din-sdk`; the existing draft PR #31 auto-updates

---

## Commit / PR plan

One commit on `feat/din-sdk`:
`refactor(sdk): extract manifest + runtime into dincli/sdk (#20)`

Completes the SDK loader tier (`cid, errors, config, log, web3, ipfs, contracts, manifest, runtime`).
Pushing updates draft PR #31 automatically; the keystones (session/tx/signer) remain the only
SDK work still waiting on Umer's contract feedback.
