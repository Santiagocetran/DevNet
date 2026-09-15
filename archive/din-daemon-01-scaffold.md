# Implementation Plan — `dind` daemon scaffold (P4-1.1, issue #21)

**Issue:** #21 (start DIN daemon) · **Branch:** `feat/din-daemon` (off `feat/din-sdk`, now at `fc4232a`)
**Roadmap:** P4-1.1 (dind Daemon Framework) — carries forward P3-T0.2a/c/d
**Status:** DRAFT v3 — implementation-ready (two final audit corrections folded in).
**Depends on:** `feat/din-sdk` (uses `sdk.config`, `sdk.log`, `sdk.errors`).
**Sign-off:** Umer green-lit scaffold-only work in parallel on #21; the *role-automation* layer
waits on the SDK contract. This plan is that scaffold — SDK-independent.

> **Reality check (recon):** SIGTERM (T0.2a), `/health` (T0.2c), JSON logging (T0.2d) do **not**
> exist in code — this plan *establishes* them. P3-DOC7 (Umer's `dind` architecture doc) isn't
> written, so these choices effectively **seed** it; keep them documented for ratification.
>
> **v2 (audit-incorporated):** (1) unified **state-dir resolution** across start/stop/status
> (shared `--state-dir` + `DIN_DIND_STATE_DIR`) so lifecycle commands can't target the wrong
> daemon; (2) named **health bind** keys/defaults (`DIN_DIND_HEALTH_HOST=127.0.0.1`,
> `DIN_DIND_HEALTH_PORT`) with one resolver, and the daemon records its bound address so `status`
> finds the real port; (3) Phase 1 `status` is **PID-only** (health enrichment lands in Phase 3);
> (4) `package-data` for bundled unit examples is now in the checklist; (5) one shutdown status
> model — `running → pending` + interruption metadata (no `interrupted` status); (6) heartbeat is
> a **direct meta update**, not a per-tick queue row, plus jobs-table retention from day one;
> (7) `configure_logging()` is idempotent (replaces existing `dincli` handlers, preserves level).
>
> **v3 (final audit):** (a) `start` **refuses to launch if a live PID already exists** (non-zero
> exit; future `--force`); (b) corrected the logging mechanism — `sdk/log.py` installs its handler
> on the **root** logger via `basicConfig` (`sdk/log.py:25-29`) and `"dincli"` propagates to it, so
> the daemon attaches its JSON handler **to `dincli`** and sets `propagate=False` (rather than
> clearing a non-existent `dincli` handler).

---

## Goal & scope

Build the always-on `dind` process **framework** (P4-1.1), with **no role automation**:

- `dind` package + console script; `dind start | stop | status`.
- Event loop + job queue + persistent state store (SQLite — decision below).
- Graceful SIGTERM/SIGINT shutdown from day one (T0.2a).
- Structured JSON logging in daemon mode (T0.2d).
- HTTP `/health` endpoint + resource summary (T0.2c, extended per P4-1.1).
- `systemd`/`launchd` unit examples; container entrypoint/healthcheck handoff.

A loop **heartbeat** (meta update) proves liveness; a unit-tested **demo job** proves the queue
path. Real role handlers are **out of scope** (P4-2.x–7.x).

---

## Design decisions (resolved before implementation)

- **No `dincli/sdk/` or `dincli/cli/` files are modified.** Purely additive under `dincli/dind/`;
  imports `sdk.config`/`sdk.log`/`sdk.errors` but changes none. Keeps `feat/din-daemon` a clean
  superset of `feat/din-sdk` (trivial future rebase). SDK-worthy bits (log toggle, a shared
  `STATE_DIR`) are flagged for later promotion, not done here.

- **Unified lifecycle/config contract (audit #1, #2).** One resolver module,
  `dind/config.py`, resolves everything for **all** commands, with precedence
  `--flag > env > config.json > default`:
  - **State dir:** `--state-dir` on `start`, `stop`, **and** `status`; env `DIN_DIND_STATE_DIR`;
    default `CACHE_DIR / "dind"`. All of `dind.db`, `dind.pid` derive from it. This prevents
    `stop`/`status` from reading a default path when the daemon was started elsewhere.
  - **Health bind:** `DIN_DIND_HEALTH_HOST` (default **`127.0.0.1`** — local-only; safe under the
    container's `network_mode: host`, `docker-compose.yml:33`) and `DIN_DIND_HEALTH_PORT`
    (default `8787`), validated (host non-empty, port 1–65535). `status` uses the **same resolver**
    to find the endpoint; additionally the daemon **records its actually-bound host/port** in
    `daemon_meta` at startup, and `status` prefers that (handles ephemeral ports / drift).

- **State store = SQLite** (roadmap left the call to Santiago; tradeoff documented):
  ACID + crash recovery for the queue, atomic per-job status transitions, queryable
  (`last_success`, pending count for `/health`), WAL-safe concurrency, **stdlib (`sqlite3`), no
  dep.** JSON files rejected for the queue: whole-file rewrites are race-prone and corruption-prone
  under checkpoint-on-shutdown. (Static config stays JSON in `sdk.config`.)

- **Concurrency = threads, not asyncio** (dep-free, matches the sync codebase): main thread runs
  the scheduler loop; a daemon thread runs the `/health` server; SIGTERM sets a shared
  `threading.Event`. Job work is synchronous; `http.server` is blocking. Revisit asyncio at
  event-listening (P4-7.1).

- **`/health` = stdlib `http.server`** (`ThreadingHTTPServer`) — no FastAPI/uvicorn dep for one
  JSON endpoint.

- **JSON logging in `dincli/dind/logging.py`** — a `JsonFormatter` + an **idempotent**
  `configure_logging(mode)` the daemon calls at startup (audit #7, corrected in v3). Note
  `sdk/log.py` installs its text handler on the **root** logger via `basicConfig`
  (`sdk/log.py:25-29`); `"dincli"` has no handler of its own and propagates to root. So the daemon:
  captures `logging.getLogger("dincli").getEffectiveLevel()`, attaches the JSON `StreamHandler`
  **directly to the `dincli` logger**, sets `dincli.propagate = False` (so records don't *also*
  fire root's text handler → no double output), applies the captured level, and — for idempotency
  — removes any daemon handler it previously added to `dincli` before adding a new one (repeat
  calls don't stack). Toggle `DIN_LOG_FORMAT=json|text` (daemon → json, CLI → text/unchanged); runs
  only in the daemon process, so CLI output is never mutated. Error fields reuse `sdk.errors`
  `DinError.code`/`to_error()`/`sanitize_details` (secrets stay out of long-lived logs).

- **Lifecycle = foreground + PID file** (systemd/launchd/Docker background it): `start` runs
  foreground, writes the PID file; `stop` sends SIGTERM via the PID file; `status` reads it and (in
  Phase 3+) probes `/health`. `--detach` is a later nicety.

---

## Ground rules discovered from the code (recon, with refs)

- **Greenfield patterns.** No `signal` handler, `/health`, `http.server`, JSON formatter, or
  `healthcheck:` in code. Requirements: `ROADMAP.md:107-110` (T0.2a/c/d),
  `validator-operations.md` (shutdown `:107-119`, health `:125-137`, logging fields `:139-147`).
- **Entry point.** `pyproject.toml:27-28`: `dincli = "dincli.main:app"` (Typer app object). Add
  `dind = "dincli.dind.main:app"`. `packages.find` auto-includes `dincli*`, so `dincli/dind/`
  needs no manifest edit **for code** — but bundled non-`.py` files need `package-data` (audit #4).
- **Deps.** Only `typer, python-dotenv, web3, platformdirs, py-cid`. Scaffold adds **none**
  (sqlite3/http.server/signal/threading/json are stdlib).
- **Container handoff pre-marked.** `Dockerfile:79` `CMD ["sleep","infinity"]`,
  `docker-compose.yml:78` `command`, both with "replace when `dind` is entrypoint" comments; compose
  has **no** `healthcheck:` (add for T0.2c); `network_mode: host` at `:33`.
- **State-ownership boundary fixed** (`containerization.md:299-309`): `dind` (trusted host peer to
  `dincli`) owns wallet/signing/submission/task-selection; workers only compute. Scaffold wires
  **no** signing yet (role automation deferred), so the boundary holds by omission.
- **SDK reuse:** `sdk.config` (`CACHE_DIR` `sdk/config.py:13`, `load_config`, `get_env_key`),
  `sdk.log.logger`, `sdk.errors`.

---

## Package layout

```
dincli/dind/
  __init__.py          # __version__, docstring (daemon → sdk only, never cli)
  main.py              # Typer app: dind start | stop | status  (all take --state-dir)
  config.py            # resolver: state-dir, health host/port (flag > env > config > default)
  paths.py             # StateDirs(state_dir) -> db_path, pid_path
  process.py           # PID file read/write, is-running, stale detection, send-signal
  daemon.py            # scheduler loop (injectable stop_event/max_ticks), shutdown orchestration
  state.py             # SQLite: jobs + daemon_meta; enqueue/claim/complete/fail/checkpoint; retention
  jobs.py              # Job dataclass + status enum (pending|running|done|failed) + handler registry
  health.py            # ThreadingHTTPServer GET /health (JSON) + resource summary
  logging.py           # JsonFormatter + idempotent configure_logging(mode)
  signals.py           # install_shutdown_handlers(stop_event) for SIGTERM/SIGINT
  examples/
    dind.service       # systemd template
    com.din.dind.plist # launchd template
```

---

## Phase 1 — package skeleton + CLI lifecycle

- `dind/config.py`: the shared resolver (state-dir + health host/port) used by every command.
- `dind/main.py`: Typer app; `start` / `stop` / `status` **all accept `--state-dir`**.
  - `start`: resolve state dir; **if the PID file exists and that process is live, abort with a
    non-zero exit** ("already running"; a `--force` override is a future nicety) — only a *stale*
    PID is cleared; then foreground, write PID, run an (initially empty) loop until signal.
  - `stop`: resolve state dir → read PID → SIGTERM → wait `--timeout`.
  - **`status`: PID-only in this phase** (running/stopped/stale from the PID file). `/health`
    enrichment is added in Phase 3 (audit #3).
- `dind/process.py`: atomic PID write, stale detection (`os.kill(pid, 0)`).
- `dind/paths.py`: `StateDirs` deriving `db_path`/`pid_path`; `mkdir(parents=True, exist_ok=True)`.
- `pyproject.toml`: add the `dind` console script.
- **Exit:** start→idle loop, stop, PID-only status all work with a custom `--state-dir`; verified
  by hand + a subprocess test.

## Phase 2 — event loop + job queue + SQLite + graceful shutdown

- `dind/state.py`: SQLite (WAL). Tables:
  - `jobs`(id, type, status ∈ **pending|running|done|failed**, payload json, attempts, created_at,
    updated_at, last_error).
  - `daemon_meta`(started_at, last_tick, last_success, health_host, health_port, shutdown_count).
  - **Retention from day one (audit #6):** cap `done`/`failed` history (keep last N or age-out) on
    completion so the table can't grow unbounded.
- `dind/jobs.py`: `Job` dataclass + handler registry. A **demo job** (enqueued once, exercised in
  tests) proves enqueue → claim → run → complete.
- `dind/daemon.py`: loop with injectable `stop_event` + optional `max_ticks` (testable without real
  timing/signals). Each tick: update `daemon_meta.last_tick` (**heartbeat = direct meta update, not
  a queue row** — audit #6), then claim/dispatch any pending job.
- `dind/signals.py`: SIGTERM/SIGINT → set `stop_event`. **Shutdown contract**
  (`validator-operations.md:107-119`): stop claiming, set any `running` job **back to `pending`**
  and record interruption metadata (bump `attempts`/`last_error="interrupted@shutdown"`,
  `daemon_meta.shutdown_count`) — **no separate `interrupted` status** (audit #5); close health
  server; remove PID; exit 0.
- **Exit:** heartbeat advances each tick; SIGTERM → clean checkpointed shutdown; state survives
  restart; retention holds.

## Phase 3 — `/health` + resource summary + JSON logging

- `dind/health.py`: `ThreadingHTTPServer` bound via the resolver (`DIN_DIND_HEALTH_HOST`/`_PORT`,
  default `127.0.0.1:8787`); on bind, write the actual host/port into `daemon_meta`. `GET /health`
  → JSON `{status, uptime_s, pid, last_tick, last_success, queue:{pending,running,failed},
  resources:{cpu_count, disk_free_bytes, disk_total_bytes}}`. `status`=`degraded` if `last_tick`
  is stale. Handler guarded so a health error never crashes the loop.
  - Resource summary dep-free: `os.cpu_count()`, `shutil.disk_usage(state_dir)`. RAM-free and
    RPC/wallet checks are **TODO** (full detection is P4-2.2; RPC/signer need role-automation wiring).
- `dind/main.py` `status`: now resolves the endpoint (prefer `daemon_meta`'s recorded host/port,
  else the resolver) and enriches the PID view with the `/health` payload.
- `dind/logging.py`: `JsonFormatter` (T0.2d fields: ts, level, logger, msg + contextual
  role/network/model/gi/job_id/error_code via `LoggerAdapter`/`extra`); idempotent
  `configure_logging()` per the design decision. `dind start` calls it first.
- **Exit:** external `curl 127.0.0.1:8787/health` returns JSON; daemon stdout is line-delimited
  JSON; CLI output unchanged; `status` shows health.

## Phase 4 — service units + container handoff (capstone; separate commit)

- `dind/examples/dind.service` (systemd: `ExecStart=dind start`, `Restart=on-failure`,
  `KillSignal=SIGTERM`, `TimeoutStopSec`) + `com.din.dind.plist` (launchd).
- **`pyproject.toml` `[tool.setuptools.package-data]`: add `dincli.dind` → `examples/*` (audit #4)**
  (or, if we prefer not to ship them installed, place under `Documentation/` and reference — decide
  at implementation; default: package them so a future `dind install-service` can emit them).
- Container handoff (own commit, touches committed docker files): `Dockerfile:79` `CMD` →
  `["dind","start"]`; `docker-compose.yml:78` `command` updated; **add `healthcheck:`**
  (`curl -f http://127.0.0.1:8787/health`). Document in `docker/node/README.md`.
- **Exit:** `docker compose up` runs `dind` as entrypoint; healthcheck flips healthy.

---

## Testing

- **Keep the existing 95 green** (scaffold touches no `sdk`/`cli` code); run the full suite.
- **New `tests/test_dind_*.py`:**
  - `config`: resolver precedence (flag > env > config > default) for state-dir and health host/port.
  - `state`: enqueue/claim/complete/fail/checkpoint round-trip on a `tmp_path` DB; restart recovery
    (`running`→`pending`); retention caps history.
  - `logging`: `JsonFormatter` emits valid JSON with required fields; `configure_logging()` is
    idempotent (no duplicate handlers on repeat calls); secrets scrubbed.
  - `health`: payload shape; `degraded` on stale `last_tick`.
  - `daemon loop`: injected `stop_event`+`max_ticks`; heartbeat advanced; demo job ran; clean shutdown.
  - `process`: PID write/read/stale detection; `stop`/`status` honor `--state-dir`.
- **`dind` import-boundary test:** `import dincli.dind` pulls in **no `dincli.cli.*`** (daemon →
  sdk, never cli). Fresh subprocess. `typer` allowed here (the `dind` CLI uses it).
- **Runtime smoke:** `dind --help`; `dind start --state-dir <tmp>` (bg) → `curl /health` →
  `dind status --state-dir <tmp>` → `dind stop --state-dir <tmp>`.

---

## Risks & mitigations

- **Wrong-daemon lifecycle ops** — solved by the shared resolver + `--state-dir` on all commands.
- **Health bind ambiguity/security** — named keys, `127.0.0.1` default, validation, recorded bound
  address in `daemon_meta`.
- **Testing a long loop** — injectable `stop_event`/`max_ticks`; no wall-clock/real signals.
- **`http.server` thread** — `ThreadingHTTPServer`, short poll `timeout`, `daemon=True`; guarded handler.
- **SQLite threads** — single writer (loop) + WAL; health thread reads only; per-thread connections.
- **Log reconfiguration** — idempotent handler replacement; daemon-process-only; level preserved.
- **Unbounded queue** — heartbeat is a meta update; retention/compaction on the jobs table.
- **P3-DOC7 not written** — proceed per Umer's go-ahead; document choices; flag as proposed in the PR.
- **Cross-branch drift** — no `sdk`/`cli` edits, so `feat/din-daemon` stays a clean superset.

---

## Out of scope (explicit)

- Client/aggregator/auditor automation, task discovery/recommendation, preferences, full capability
  detection, on-chain event listening, peer coordination (P4-2.x → P4-7.x).
- Any signing / on-chain submission / IPFS wiring (needs the frozen SDK contract).
- Folding the JSON-log toggle or a shared `STATE_DIR` into `sdk/` (candidate follow-up).

---

## Step checklist

- [x] Refresh `feat/din-daemon` off current `feat/din-sdk` (`fc4232a`) — done
- [ ] Phase 1: `dind/` skeleton; `config.py` resolver; `main.py` (start/stop/status, all `--state-dir`,
      **status PID-only**, **start refuses a live PID**); `process.py`; `paths.py`; pyproject `dind` script
- [ ] Phase 2: `state.py` (SQLite jobs+daemon_meta, **retention**); `jobs.py` (demo job); `daemon.py`
      loop (**heartbeat=meta update**); `signals.py` (**running→pending** + interruption metadata)
- [ ] Phase 3: `health.py` (bind via resolver, record bound addr, resource summary); `status` health
      enrichment; `logging.py` (JSON + **idempotent** configure)
- [ ] Phase 4: `examples/*` units; **`package-data` entry for `dincli.dind/examples/*`**; container
      CMD + compose `healthcheck` (separate commit)
- [ ] Tests: `test_dind_*` (incl. resolver + idempotent-logging + retention) + `dind` import-boundary;
      full suite green; `--help`/curl smoke
- [ ] Push `feat/din-daemon`; open **draft PR** (base `feat/din-sdk`, not develop) tracking #21

---

## Commit / PR plan

Commits on `feat/din-daemon`:
1. `feat(dind): daemon package + CLI lifecycle (start/stop/status, shared --state-dir) (#21)`
2. `feat(dind): event loop + SQLite job queue + graceful SIGTERM (#21)`
3. `feat(dind): /health endpoint + resource summary + JSON logging (#21)`
4. `feat(dind): systemd/launchd examples + container entrypoint/healthcheck (#21)`

Then a **draft PR** `Santiagocetran:feat/din-daemon → InfiniteZeroFoundation:feat/din-sdk`
(base = the SDK branch it stacks on; clean daemon-only diff; honors "not develop directly").
Keep it draft — the visible-progress window for #21.
