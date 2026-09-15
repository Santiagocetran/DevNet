# Follow-ups deliberately kept OFF the PR #31 / Discussion #67 review

Split out of the `task_300726_8` closing post so they don't dilute the SDK review or invite scope
expansion on PR #31. None of these are `task_300726_8` deliverables. Raise them **after** the SDK
review closes, or fold them into the next task's scoping.

---

## 1. `sdk/ipfs.py`'s mislabeled `TODO(sdk-keystones): IpfsError`

**Source:** PR #31 code review, finding No. 5 (Umer, 2026-07-30).

`_raise_for_http_error` and the `RequestException` catches in `upload_to_ipfs` / `retrieve_from_ipfs`
raise bare `RuntimeError`, tagged as blocked on the keystone work. They are not:
`IpfsError` already exists (`errors.py:70`) and its `_ALLOWLIST` entry
(`{"provider", "status_code", "path", "stderr"}`) is already present — so **`errors.py` needs no
change**, just three `raise` swaps.

**Why it matters:** per `errors.py`'s own docstring the daemon "keys retries off the stable `code`".
A failed IPFS upload currently raises with no `.code`, so `dind`'s retry policy has nothing
structured to branch on.

**Status:** not done in `task_300726_8`. It touches the IPFS path rather than the wallet/session/tx
slice, and folding it in would have widened a security-sensitive review. Cheap and self-contained
whenever it's scheduled.

---

## 2. Three `dind` gaps from the PR #32 review are untracked

Umer's PR #32 review asked that these be opened as tracked follow-ups "now". Only `BL-9` landed (and
that came from PR #31's finding No. 6, not from #32). Drafted rows in his table format, ready to paste
into `Developer/BACK_LOG.md` — **his file**, every commit to it is his, so it isn't ours to edit
unilaterally.

```markdown
| BL-10 | Daemon | `dind start` PID-file TOCTOU race | `start()` (`dincli/dind/main.py`) does `read_pid` → `is_process_running` → `write_pid` with no file lock (no `O_EXCL`, no `flock`) tying the check to the write, so two concurrent `dind start` invocations against the same `--state-dir` both start clean and both run event loops against the same SQLite DB. Last writer wins `dind.pid`, so `dind stop`/`status` can only ever see one — the other is an unstoppable orphan doubling job-claim traffic. Contradicts the "start refuses a live PID" claim under any real concurrency (systemd `Restart=on-failure` retry, double-invoking deploy script). Reproduced live during review. | P4-1.1 (harden before `dind` runs real jobs) | PR #32 code review finding No. 1, Jul 30, 2026 | 🆕 New |
| BL-11 | Daemon | Container healthcheck can't detect `degraded` status | `HealthHandler.do_GET()` (`dincli/dind/health.py`) always returns HTTP 200 unless `_build_payload()` itself raises — the computed `status: "degraded"` (stale last-tick) appears only in the JSON body, never in the status code. `docker-compose.yml`'s `curl -f http://127.0.0.1:8787/health` only fails on non-2xx, so a daemon whose event loop has hung while the health thread still answers passes the healthcheck forever. As wired, the check is crash-only, not hang-detecting — undercutting `ecf7aa3`'s "Docker auto-restart an unhealthy daemon" claim. Fix: map `degraded` to a non-2xx code, or document the healthcheck as crash-only. | P4-1.1 (harden before `dind` runs real jobs) | PR #32 code review finding No. 2, Jul 30, 2026 | 🆕 New |
| BL-12 | Daemon | `dind` persists no logs to disk | `configure_logging()` (`dincli/dind/logging.py`) attaches a plain `StreamHandler` (stderr) with the `JsonFormatter` — no `RotatingFileHandler`, nothing written into `StateDirs` despite it already holding `jobs.db`/`dind.pid`/`preferences.json`. Under systemd (journald) or a container log driver the supervisor persists logs; run directly in a terminal — the documented and tested path — stderr is gone when the session closes, leaving nothing to `grep` for "why did my node skip a job three hours ago". For an always-on daemon aimed at non-expert operators (issue #21), `dind` should own a rotating log file under its own state dir. | P4-1.1 (operability, before `dind` is load-bearing) | PR #32 code review finding No. 6, Jul 30, 2026 | 🆕 New |
```

---

## 3. Three PR #32 quick fixes — code, not backlog

Small and self-contained, but they'd deviate from `task_300726_8`'s "no code edits on
`feat/din-daemon`" boundary, so they were left alone.

- **`dincli/dind/examples/dind.service` is broken as shipped** — uses `%i` / `%E`, which only resolve
  in *instantiated* units (`name@.service`). The file has no `@`, so `User=%i` and the
  `EnvironmentFile=` path break for anyone following the documented
  `systemctl enable --now dind.service`. Fix: rename to `dind@.service` and document
  `dind@<user>.service`, or hardcode a placeholder username with an edit-me comment.
- **`HealthServer.shutdown()` never calls `server_close()`** — stops `serve_forever()` but leaves the
  listening socket open. Harmless today because the process exits immediately after, but it would hold
  the port in any future harness driving multiple start/stop cycles in one process.
- **`resource_snapshot(state_dir: Path)` is passed a `str`** from `health.py` — type-hint accuracy
  only, works fine at runtime.

---

## 4. Noted during `task_300726_8`, not from any review

- **`NonceManager._instances` is never evicted.** Keyed by `(chain_id, address)` and cached for the
  process lifetime. Correct and irrelevant for the CLI (one invocation), but it's process-wide mutable
  state with no eviction — worth a look when `dind` starts running long-lived. It also caused real
  test pollution: reservations leaked between test classes until each cleared it in `setup_method`.
- **Local deploys dirty a tracked repo file.** `save_din_info` writes to the *packaged*
  `dincli/config/din_info.json`, not the user config dir, so `dincli dindao deploy …` against a local
  chain shows up in `git status`. `XDG_CONFIG_HOME` isolation does **not** cover it.
- **The `local` network's explorer URL points at Optimism Sepolia.** Local deploys print a
  `sepolia-optimism.etherscan.io` link for a transaction that only exists on anvil. Pre-existing
  (identical before and after this task, so it didn't affect the parity diff), mildly confusing during
  local testing.
