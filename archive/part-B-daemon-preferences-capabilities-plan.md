# Part B Implementation Plan — `dind preferences` + `dind capabilities`

**Task:** `task_220726_7` Part B (Issue #21, P4-2.1 / P4-2.2 local-only) · **Branch:** `feat/din-daemon` (PR #32, stacked on `feat/din-sdk`)
**Prereq:** the branch **sync** in §1 (feat/din-daemon is 21 behind **remote `develop`** (`origin`/`upstream`), 25 behind `origin/feat/din-sdk`; a stale local `develop` may misreport — verify against remotes)
**Companion docs:** `Plans/archive/current-state-and-next-task.md` (state + scope), `Plans/archive/part-A-sdk-state-serialize-plan.md`
**Scope reminder:** local-only. **No** live RPC/session, **no** wallet/signing (boundaries #1–#4). Mirror existing `dind` conventions — don't invent new config/logging styles.

---

## 0. Anchors (read from `feat/din-daemon`, verified 2026-07-23)

| Thing | Location |
|---|---|
| State-dir + path helpers | `dincli/dind/paths.py` — `StateDirs(state_dir)` with `.db_path`, `.pid_path` (add `.preferences_path`) |
| Config precedence pattern | `dincli/dind/config.py` — `resolve_state_dir/health_host/health_port` (`--flag > env > config.json > default`); `DEFAULT_STATE_DIR = CACHE_DIR/"dind"` |
| Load/save shape to mirror | `dincli/dind/state.py` — `StateStore` (SQLite; preferences will be simpler JSON, see §3) |
| Typer app + commands | `dincli/dind/main.py` — `app`, `start`/`stop`/`status`; commands print via `typer.echo`, take `--state-dir` |
| `/health` resources block | `dincli/dind/health.py` — `_build_payload()`; `resources` dict = `{cpu_count, disk_free_bytes, disk_total_bytes}`; disk via `shutil.disk_usage` try/except |
| JSON logging | `dincli/dind/logging.py` — `configure_logging`, `JsonFormatter` (daemon **runtime logs**, not command output) |
| Endpoint resolution (for probe) | `dincli/sdk/config.py` — `resolve_network()`, `resolve_network_value(network, key, ...)`, `resolve_ipfs_config()` (→ `api_url_add`/`api_url_retrieve`) |
| Import-boundary test | `tests/test_dind_boundary.py` — `pkgutil.walk_packages(dincli.dind)` → **auto-covers** new modules; forbids `dincli.cli.*` only (typer is allowed in `dind`) |
| Health test to extend | `tests/test_dind_health.py` — `test_health_payload_shape` asserts `resources` keys |

**Confirmed:** the boundary test walks *all* of `dincli.dind`, so `preferences.py`/`capabilities.py` are covered the moment they exist — no edit needed (belt-and-suspenders assertion optional). `dind` commands legitimately import `typer`; only `dincli.cli.*` is forbidden. Keep the new **logic** (dataclasses, detect/load/save) `typer`-free in the modules; the **commands** live in `main.py` and add typer there.

---

## 1. Branch sync (do FIRST — nothing else compiles against current develop otherwise)

`feat/din-daemon` is stacked on `feat/din-sdk`, which already contains `develop` + Part A. So **one merge** syncs everything:

```bash
git fetch origin && git fetch upstream
git checkout feat/din-daemon
git config branch.feat/din-daemon.pushRemote origin   # same push-routing footgun as feat/din-sdk
git merge origin/feat/din-sdk   # merge the REMOTE-tracking ref (bare `feat/din-sdk` may be stale unless just pulled); brings develop + SDK Part A in one go
# resolve conflicts (anticipate the same spots as the feat/din-sdk merge: test_connect_wallet.py, CLAUDE.md)
pytest   # or python -m pytest via .venv — confirm green post-merge
```

- **Merge, not rebase** — PR #32 is a public draft with pushed history; rebasing forces a force-push. The branch's history already integrates via merges (consistent with `feat/din-sdk`).
- Part B doesn't *functionally* depend on Part A output this round, but syncing stops the two PRs drifting and gets `develop`'s fixes. If the merge is large/noisy, that's expected (same as PR #31) — the develop commits collapse if/when PR #32's base advances.
- After merge, re-confirm the §0 anchors (line numbers may shift, as they did in Part A).

---

## 2. `dind` command surface (in `main.py`)

Add a `preferences` sub-group and a `capabilities` command, mirroring the existing `--state-dir` + `typer.echo` style:

```python
from dincli.dind.preferences import Preferences, load_preferences, save_preferences
from dincli.dind.capabilities import detect_capabilities

preferences_app = typer.Typer(help="Local daemon preferences.")
app.add_typer(preferences_app, name="preferences")

@preferences_app.command("show")
def preferences_show(state_dir: str | None = STATE_DIR): ...      # typer.echo(json.dumps(asdict(prefs), indent=2))

@preferences_app.command("set")
def preferences_set(state_dir: str | None = STATE_DIR,
                    domain: str | None = typer.Option(None, "--domain"),
                    risk_tolerance: str | None = typer.Option(None, "--risk-tolerance"),
                    min_reward: int | None = typer.Option(None, "--min-reward"),
                    privacy: list[str] | None = typer.Option(None, "--privacy")): ...

@app.command()
def capabilities(state_dir: str | None = STATE_DIR): ...          # typer.echo(json.dumps(asdict(summary), indent=2))
```

**State-dir resolution:** each command resolves first — `resolve_state_dir(state_dir)` → `StateDirs(resolved)` — before touching prefs/capabilities, exactly like `start`/`stop`/`status`. Pass the resolved dir into `load_preferences(paths.preferences_path)` / `detect_capabilities(resolved)`; never pass the raw `--state-dir` flag through (keeps the `--flag > env > config.json > default` precedence intact).

**Output convention:** print JSON via `typer.echo(json.dumps(asdict(...), indent=2))`. The task's "reuse the JSON-logging conventions" means *emit JSON* (consistent with the daemon being JSON-oriented) — **not** route command output through `logging.py`'s handler (that's for the daemon's runtime log stream, and `status` already uses `typer.echo` for command output). No `rich` in `dind`.

---

## 3. `dincli/dind/preferences.py` (new) — P4-2.1

Simpler than `StateStore` (SQLite is for the job queue; preferences is static config) — a dataclass + two JSON functions, as the task permits:

```python
from dataclasses import dataclass, field, asdict
import json
from pathlib import Path

@dataclass
class Preferences:
    domain: str | None = None                 # free-form, no fixed taxonomy yet
    risk_tolerance: str = "moderate"           # conservative | moderate | aggressive
    min_expected_reward: int | None = None     # wei; None = no floor
    privacy_constraints: list[str] = field(default_factory=list)

def load_preferences(path: Path) -> Preferences:
    """Return stored prefs, or defaults if the file is absent OR empty (never raise on missing/empty)."""
    if not path.exists():
        return Preferences()
    text = path.read_text()
    if not text.strip():          # empty/whitespace file → defaults, not a JSONDecodeError
        return Preferences()
    data = json.loads(text)
    return Preferences(**{k: data[k] for k in data if k in Preferences.__dataclass_fields__})

def save_preferences(path: Path, prefs: Preferences) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(prefs), indent=2))
```

- Storage path: add `preferences_path` to `StateDirs` → `state_dir / "preferences.json"` (reuse `paths.py`, don't hardcode).
- **Partial `set`**: load current, overwrite only the fields whose flags were passed (non-`None`; `--privacy` replaces the list when provided), save. Unset flags leave stored values untouched.
- Optional: validate `risk_tolerance` ∈ {conservative, moderate, aggressive} — raise `typer.BadParameter` in the command (keep the module pure).

---

## 4. `dincli/dind/capabilities.py` (new) — P4-2.2 (hardware/local slice)

```python
@dataclass
class CapabilitySummary:
    cpu_count: int
    cpu_speed_mhz: int | None
    ram_total_bytes: int | None
    ram_free_bytes: int | None
    disk_free_bytes: int | None
    disk_total_bytes: int | None
    gpu_available: bool
    rpc_reachable: bool | None      # None = not configured / check skipped
    ipfs_reachable: bool | None

def resource_snapshot(state_dir) -> dict: ...     # cpu + disk + RAM (all fast/local; shared with /health)
def detect_capabilities(state_dir=None) -> CapabilitySummary: ...
def score_capabilities(summary) -> int: ...       # pure
def compatible_with(summary, requirements: dict) -> bool: ...  # pure, placeholder
```

Detection, **stdlib-first** (flag any new dependency in the PR):
- **CPU count** — `os.cpu_count()` (already used in `health.py`). CPU speed: best-effort; `/proc/cpuinfo` "cpu MHz" on Linux, else `None` (don't add a dep for it).
- **RAM** — no stdlib cross-platform API. **Recommendation: stdlib-first, no new dep** — total via `os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")` (POSIX: Linux+macOS); free via `/proc/meminfo` `MemAvailable` on Linux, `None` elsewhere. Fields are `Optional`, so `None` is graceful. *If the team prefers cross-platform robustness, add `psutil` (the standard choice) and flag it in the PR* — but default to no-dep unless asked.
- **Disk** — `shutil.disk_usage(state_dir)` in a try/except. **Factor `health.py:_build_payload`'s inline disk block into `resource_snapshot()`** and have `health.py` call it, killing the duplication (task's explicit ask).
- **GPU** — best-effort bool: `shutil.which("nvidia-smi") is not None` or `glob("/dev/nvidia*")`. **Absence is a normal result, not an error.**
- **RPC/IPFS reachability** — **bare probe only** (boundary #4): resolve endpoints via `sdk.config`
  (`resolve_network_value(resolve_network(), "rpc_url")` for RPC — confirmed key, same one `sdk/web3.py`
  uses; `resolve_ipfs_config().api_url_add` for IPFS), parse with `urllib.parse.urlsplit`, then
  `socket.create_connection((host, port), timeout=~2s)` → bool. **No `get_w3`, no live RPC call.**
  - **Default ports** — `urlsplit(url).port` is `None` for `https://host/path` (no explicit `:443`). Fill
    defaults: `https → 443`, `http → 80`; only treat as `None` (skip) when the endpoint is unconfigured
    or truly unparseable (no host). Don't misclassify a normal port-less HTTPS URL as unreachable.
  - **`None`** = endpoint not configured / key missing: wrap the `resolve_network_value(..., "rpc_url")`
    lookup and catch `KeyError` (and unparseable URLs) → `rpc_reachable=None`, rather than inventing a
    second config path.

### `/health` wiring
Extend `health.py:_build_payload`'s `resources` block to the fuller summary. **Performance decision (documented tradeoff):** `/health` is polled frequently, so it must stay cheap — call the **fast** `resource_snapshot()` (cpu + disk + RAM: all local, no subprocess/socket) and **do NOT** run GPU (`nvidia-smi` subprocess) or the network probes on every poll. The full `detect_capabilities()` (with GPU + reachability) backs the on-demand `dind capabilities` command only. This avoids per-poll subprocess/socket cost while removing the duplicated disk logic.

---

## 5. Tests

- `tests/test_dind_preferences.py` (new): round-trip save→load; `load_preferences` returns defaults (without erroring) on both a **missing** file and an **empty/whitespace** file; partial `set` (via `CliRunner` on the `dind` app) updates only the passed field and leaves others; `show` on fresh dir emits defaults JSON.
- `tests/test_dind_capabilities.py` (new): `detect_capabilities()` returns a well-formed `CapabilitySummary` on the test host — **mock/skip GPU + network** (monkeypatch `shutil.which`, the socket probe, and `sdk.config` resolvers; don't assert a specific GPU/network outcome). `score_capabilities()` and `compatible_with()` are pure — unit-test directly against hand-built summaries (e.g. `compatible_with(s, {"min_ram_bytes":..., "requires_gpu":True})`).
- `tests/test_dind_health.py` (extend): `test_health_payload_shape` asserts the new `resources` keys (`ram_total_bytes`, `ram_free_bytes`, …) are present, and that a health poll does **not** invoke the network probe (assert the mocked socket wasn't called — guards the perf decision).
- `tests/test_dind_boundary.py`: auto-covers the new modules (walk_packages). Optional explicit assertion that both imported.
- Run: `pytest` per repo convention (local env: `source .venv/bin/activate && python -m pytest …`). The contract-integration suite (`tests/dincli/*`) and the torch DP test remain env-gated/pre-existing.

---

## 6. Sequence (small, verifiable commits)

1. **Sync** the branch (§1); resolve conflicts; suite green.
2. `paths.py`: add `preferences_path`. `preferences.py` + `test_dind_preferences.py` (module round-trip) → green.
3. `main.py`: `preferences` sub-app (`show`/`set`); extend `test_dind_preferences.py` with `CliRunner` partial-update cases.
4. `capabilities.py` (detect/score/compatible + `resource_snapshot`) + `test_dind_capabilities.py` (mock GPU/network) → green.
5. `main.py`: `capabilities` command.
6. Wire `resource_snapshot()` into `health.py`; extend `test_dind_health.py`.
7. Full runnable suite green → update PR #32 body (note the slice; reiterate wallet/session/tx deferral) → push (`origin`).
8. Follow-up on the #50 progress comment noting Part B landed.

**Commit shape** (matches repo convention):
- `feat(dind): local preferences schema + show/set commands (P4-2.1) (#21)`
- `feat(dind): hardware capability detection + capabilities command; fold into /health (P4-2.2) (#21)`

---

## 7. Risks / watch-items

- **RPC endpoint key** — confirmed `"rpc_url"` (via `resolve_network_value`, as `sdk/web3.py` uses); catch `KeyError` → `rpc_reachable=None`. Watch the **default-port** trap for port-less HTTPS URLs (§4).
- **New dependency** — default to **no `psutil`** (stdlib RAM detection with `None` fallbacks); only add it if the team wants cross-platform free-RAM, and flag it in the PR.
- **/health cost** — keep network/GPU out of the poll path (§4 perf decision); the health test guards it.
- **Merge noise** — the sync will pull develop into PR #32 (same as PR #31); expected, not a defect.
- **Release valve** (task): if the week runs tight, cut GPU detection and `compatible_with()` first — least load-bearing. Never cut preferences or the core CPU/RAM/disk detection.

---

## 8. Definition of done (Part B slice of task Deliverables)
- [ ] `feat/din-daemon` synced onto `feat/din-sdk` (develop + Part A), suite green post-merge
- [ ] `dincli/dind/preferences.py` + `dind preferences show`/`set` (partial updates), backed by `preferences.json` via `StateDirs`
- [ ] `dincli/dind/capabilities.py` + `dind capabilities` (JSON); `score_/compatible_` pure
- [ ] `/health` `resources` block extended via the shared `resource_snapshot()` (no duplicated disk logic; no per-poll GPU/network)
- [ ] `test_dind_preferences.py`, `test_dind_capabilities.py` added; `test_dind_health.py` extended; `dind` suite green
- [ ] `pytest` clean on **both** branches
- [ ] PR #32 body updated with the slice; wallet/session/tx reiterated as deferred next task
- [ ] #50 progress comment updated for Part B
