# PR #31 / #32 review follow-ups + `develop` sync — implementation plan

**Branches:** `feat/din-sdk` (PR #31, head `036828e`) · `feat/din-daemon` (PR #32, head `f69ab8d`)
**Base of both PRs:** `upstream/feat/din-sdk` @ `805ce9d` (neither targets `develop`)
**Status:** rev 4 — execution-ready. A review of rev 3 raised 3 blocking findings and 6 corrections;
**all 9 hold** and are fixed below. Two are worse than the review stated (§4.4a, §4.6). Every claim
here was checked on 2026-08-27, not taken from the PR bodies or from Umer's review text.

> **Rev 4 changelog.**
>
> - **The merge commit could not have passed its own pre-commit gate** (§4.3). Rev 3 scheduled D1,
>   the password/signer repair and test retargeting *after* the merge while demanding a green suite
>   *before* committing it — incompatible, since the incoming tests patch dead shims and expect
>   builtin `ConnectionError` until those very changes land. **All of it now happens inside the merge
>   resolution;** only A1 stays post-merge.
> - **`_sanitize_host()` does not sanitize the common case** (§4.4a). Rev 2–3 claimed the `details`
>   half was already safe. It is not: the normalizer **preserves the URL path**, so
>   `https://mainnet.infura.io/v3/<KEY>` and `https://eth.alchemy.com/v2/<KEY>` pass through
>   **unredacted**, and unparseable input is returned verbatim. Demonstrated, not inferred. This is
>   now a required `errors.py` fix with its own tests.
> - **The IPFS conversion table was incomplete and miscounted** (§4.6). `develop`'s `services/ipfs.py`
>   has **20** raise statements, not 14. Four missing-configuration raises were omitted
>   (`:101`, `:270`, `:287`, `:391` — all `ConfigError`), and the invalid-CID row cited `:391`, which
>   is actually Filebase's missing-API-key check; `validate_cid()` is called at **`:450`**. Table
>   completed, and `sdk.cid.validate_cid()` now owns raising `ValidationError` itself.
> - **Two more message-level leaks found** (§4.6). `_raise_for_http_error:261-265` embeds 300 chars of
>   `response.text` **and** chains `from exc`, whose `requests.HTTPError` string carries the full
>   request URL; `retrieve_from_ipfs:475` logs the raw `RequestException` at ERROR. Both fixed.
> - **The CID-mismatch requirements contradicted each other** — resolved in favor of keeping
>   develop's message (§4.6). A CID is a public content address, not a credential; rev 3's blanket
>   "no full CID in messages" test requirement was over-broad and is narrowed.
> - **The `ConnectionError` rationale was not evidence** (§6). `services/bridge.py:125` never lets it
>   escape. Kept for compatibility, on correctly stated grounds.
> - **`DIN_DEBUG` needed defined semantics** (§6): exact `== "1"`, plus a note that `from None` still
>   suppresses the provider cause in debug mode.
> - **Broken cross-reference** (§6): golden parity is §7 of
>   `Developer/design/sdk-interface-proposal.md`, not §7 of this plan. Concrete command named.
> - **D4 was still open while §3 assumed an answer** (§6, §3.3) — recorded as decided.
> - **A4 had no verification** (§2.4): the branch configures no type checker (no mypy/ruff/pyright
>   config anywhere). Replaced with a runtime assertion in an existing test.

> **Rev 3 changelog.**
>
> - **D1 resolved** (§6, §0): `DinError` shape, and the CLI boundary becomes
>   `except (DinError, ConnectionError)` **with a `DIN_DEBUG` escape hatch** that re-raises the full
>   traceback. Workstream C is unblocked.
> - **`ConnectionError` must stay in the tuple** — verified, not defensive: after the merge
>   `services/bridge.py:125` raises builtin `ConnectionError`.
> - **A second dead handler found** (§6): `cli/system.py:1625` (`bridge-eth`) catches bare
>   `ConnectionError` with the comment *"#83 handles this globally once merged"*. After the port that
>   path raises `NetworkError`, so the local handler goes dead and the global one takes over with a
>   different message. Neither review caught this.

> **Rev 2 changelog.**
>
> - **D1 was underspecified at the CLI boundary** (§6, §4.4). Rev 1 said `cli/core.py`'s
>   `except (ChainIdMismatchError, ConnectionError)` would "keep working". True only for stage-3
>   mismatches: our SDK represents connection failure as `NetworkError`, which is **not** a
>   `ConnectionError` subclass, so stages 1 and 2 would escape as tracebacks. D1 now specifies the
>   full three-stage contract, the allowlist entry, and the handler change.
> - **The proposed merge history dropped the IPFS security work for several commits** (§4.3). Rev 1
>   put the merge commit first and the forward-ports after it, so the merge commit's tree resolved
>   the shims "ours" and temporarily lost develop's CID-integrity work. The forward-ports now happen
>   **inside the merge resolution**; no committed tree ever regresses.
> - **The test-patch retargeting missed `dincli.sdk.config`** (§4.5). "Retarget at `dincli.sdk.*`"
>   was not specific enough: `test_ipfs_retrieval.py` also patches `utils.CONFIG_DIR`/`CONFIG_FILE`,
>   which `resolve_ipfs_config()` reads from `dincli.sdk.config` — patching the re-export is a no-op.
>   Now an explicit mapping table.
> - **A1's post-sync scope was dangerously vague** (§4.6). "Extend the swap to whatever develop's new
>   IPFS functions raise" is now an enumerated conversion table over the raise sites (rev 2 said 14
>   and covered 17 — **corrected to 20 in rev 4**), with the
>   incoming tests that each one changes. **Sharpened:** rev 1 called the swap "no behavior change" —
>   that holds for the CLI handlers, but develop's incoming tests assert `RuntimeError` and
>   `ValueError` **explicitly** at four call sites, so the conversion is observable and ships with
>   test updates.
> - **C now depends on D1** (§0). Rev 1's table said C depended on nothing while §6 said D1 must be
>   decided before touching the sync. The table was wrong.
> - **CID verification is best-effort, not unconditional** (§4.2, §5). Verified: it returns early for
>   `provider == "custom"` and degrades to a one-time warning when no `ipfs` binary is usable. Recast
>   as CID-integrity hardening with named degraded paths, and the acceptance criterion is now four
>   specific behaviors rather than "47 tests pass".
> - **Test bookkeeping** (§5): 316 → **317** after A2–A4, so the daemon contributes **70**, not 69.
>   `≈420±` is a planning estimate, not an acceptance criterion — record the exact collected count
>   once the merged tree exists.
> - **The systemd rename needed verification steps** (§2.2). **Sharpened:** rev 1 said "update any
>   doc reference" — verified there are **none** in-tree (`git grep 'dind\.service\|dind@'` over
>   `feat/din-daemon` returns nothing), so that instruction had no target. Packaging needs no change
>   either: `pyproject.toml:38` ships `"dincli.dind" = ["examples/*"]`, a glob. Replaced with three
>   real checks. Health-server fix also upgraded to `try/finally`.

**Scope:** the three items agreed — **(A)** review quick fixes, **(B)** the untracked backlog rows,
**(C)** the `develop` sync. Everything else from the two reviews stays out (§7).

---

## 0. Sequencing

| # | Workstream | Branch | Lands as | Depends on |
|---|---|---|---|---|
| 1 | **A2–A4** — `dind` quick fixes | `feat/din-daemon` | 3 commits on the existing PR #32 | nothing |
| 2 | **B** — backlog rows BL-19/20/21 | `docs/pr31-32-review-followups` off `develop` | new PR to `develop` | nothing |
| 3 | **C** — `develop` sync | `feat/din-sdk`, then `feat/din-daemon` | merge + fixups on both PRs | D1 — **decided** (§6) |
| 4 | **A1** — IPFS error taxonomy | `feat/din-sdk` | final commits of the sync branch | **C** |

**One ordering constraint remains, and it is load-bearing.**

**A1 runs after C, not before.** `dincli/services/ipfs.py` is one of the three merge-conflict files,
and `develop` has added **7 new functions and 3 module-level globals** to it since our merge-base
(§4.2) — all of which land in `dincli/sdk/ipfs.py` during conflict resolution, each with its own
error paths. Doing the swap first means doing it twice, and the second pass is the one that matters.

C was blocked on D1, because D1 fixes the exception contract the `get_w3` forward-port must
implement. **D1 is now decided (§6), so all four workstreams are executable.** A2–A4 touch
`dincli/dind/*`, which `develop` never touches, and B touches only `Developer/BACK_LOG.md`, so those
two remain independent of everything else and can run in parallel with C.

---

## 1. Verified starting state

| Fact | Value | How verified |
|---|---|---|
| PR #31 head / PR #32 head | `036828e` / `f69ab8d` | `gh pr view --json headRefOid` |
| Reviews | umeradl, 2026-07-30, at `6eac109` / `99f060b`, both `COMMENTED` | `gh api .../reviews` |
| Replies posted on either PR | **none** | `gh api .../issues/N/comments` → 0 |
| Inline review comments | none (both are single top-level bodies) | `gh api .../pulls/N/comments` → 0 |
| CI on either branch | none configured | `gh pr checks` |
| Merge-base of `feat/din-sdk` and `upstream/develop` | `98d4837` | `git merge-base` |
| `develop` ahead of merge-base | **49 commits** | `git rev-list --count` |
| `feat/din-sdk` ahead of merge-base | 21 commits | `git rev-list --count` |
| `dind` commits since the review | **zero** (only SDK sync merges) | `git log --since=2026-07-30` |
| Test baselines | `feat/din-sdk` **247** · `feat/din-daemon` **316** · `develop` **255** | `pytest --collect-only`, exclusions per §5 |
| Venv | `DevNet/.venv` (py3.12.3, pytest + web3 + **torch**) | import probe |

`/home/santi/.venvs/devnet` also works but has no torch, so it cannot run
`tests/test_cache_client_dp.py`. Use `DevNet/.venv`. Running pytest from inside a separate git
worktree resolves `import dincli` to that worktree's copy (verified), so worktrees are safe despite
the editable install pointing at the main tree.

---

## 2. Workstream A — the quick fixes

### 2.1 A1 — IPFS error taxonomy

Deferred into the sync. Full conversion table in **§4.6**.

### 2.2 A2 — `dincli/dind/examples/dind.service` is broken as shipped

`User=%i` and `EnvironmentFile=-%E/dind/%i.env` resolve only in *instantiated* units
(`name@.service`); this file has no `@`, so anyone following
`systemctl enable --now dind.service` hits it immediately.

**Fix:** rename to `dind@.service`, document `systemctl enable --now dind@<user>.service`. Rename
keeps multi-user installs working, which is what the `%i`/`%E` pair was written for.

**Verification — three checks, replacing rev 1's "update any doc reference":**

1. `systemd-analyze verify dincli/dind/examples/dind@.service` where available. Note it will report
   `ExecStart=dind` as not found unless the venv's `bin` is on `PATH`; that is expected — read it for
   *specifier and syntax* errors, not resolvability.
2. `git grep -n 'dind\.service\|dind@'` — **currently returns nothing on `feat/din-daemon`**, so
   there is no in-tree reference to update and the check exists to prove none appears later. The only
   place the old filename and old enable command appear is PR #32's own body; fix it there when
   replying to the review.
3. Packaging needs **no change** — `pyproject.toml:38` declares
   `"dincli.dind" = ["examples/*"]`, a glob that picks the renamed file up automatically. Confirm
   with a `pip install -e .` + `importlib.resources` listing rather than assuming.

### 2.3 A3 — `HealthServer.shutdown()` never closes the socket

`dincli/dind/health.py:106-108` calls `self.server.shutdown()` (stops `serve_forever`) but never
`server_close()`, so the listening socket stays open.

**Fix, upgraded from rev 1:** add `self.server.server_close()` in `shutdown()`, **and** wrap the
`serve_forever(poll_interval=0.5)` call (`health.py:104`) in `try/finally` with `server_close()` in
the `finally`. `shutdown()` alone only covers the orderly path; the `finally` also covers the loop
terminating abnormally, which is the case that would actually strand the port.

### 2.4 A4 — `resource_snapshot` type hint

`dincli/dind/capabilities.py:32` declares `resource_snapshot(state_dir: Path)`;
`dincli/dind/health.py:66-67` passes `str(self.state.db_path.parent)`. Runtime-safe
(`shutil.disk_usage` re-stringifies). Drop the `str()` at the call site — that is the fix that makes
the annotation true, rather than widening the annotation to match a sloppy call.

### 2.5 Commits for A2–A4

Three commits on `feat/din-daemon`, one per fix:

```
fix(dind): make the systemd example a template unit (dind@.service)   [review #32 No. 3]
fix(dind): close the health server socket on shutdown                 [review #32 No. 4]
fix(dind): pass a Path to resource_snapshot                           [review #32 No. 5]
```

**Verification:** 316 → **317** — one new test in `tests/test_dind_health.py` asserting a stopped
`HealthServer` releases its port (bind the same port again). A2 is covered by §2.2's three checks.

**A4 has no type checker to verify it.** Rev 3 said "verified by the type checker"; the branch
configures none — no `mypy`/`ruff`/`pyright` section in `pyproject.toml` (only `setuptools` and
`pytest`), and no `mypy.ini`/`.ruff.toml`/`pyrightconfig.json`/`setup.cfg`/`tox.ini` in the tree.
Verify at runtime instead: in the existing `/health` test, spy on `resource_snapshot` and assert
`isinstance(state_dir, Path)`. Folding it into an existing test keeps the count at **317**.

---

## 3. Workstream B — the three untracked `dind` follow-ups

Umer's PR #32 review asked that findings No. 1, No. 2 and No. 6 "be opened as tracked follow-ups
now". Only BL-9 landed, and that came from PR #31's finding No. 6, not from #32.

### 3.1 Numbering — the archived draft is stale

`Plans/archive/followups-tracking-note.md` drafts these as **BL-10/11/12**. Those numbers are
**taken**: `Developer/BACK_LOG.md:19` on `develop` carries

```
<!-- BL-10 through BL-15 reserved: added by PR #68 (docs/review-followups-backlog),
     not yet merged as of 2026-08-05. Don't reuse those numbers. -->
```

PR #68 (Abidoyesimze, open, last updated 2026-08-21) claims BL-10–BL-15, and `develop` already
carries BL-16/17/18. **Use BL-19, BL-20, BL-21.** No other open PR adds BL rows above 18 (checked
all 15 open PRs).

### 3.2 Ownership — also stale

The archived note says BACK_LOG.md "isn't ours to edit unilaterally" because every commit to it is
Umer's. True of the history (six commits, all `umeradl`), but **PR #68 is the precedent**: a
contributor opening a docs PR against `develop` that adds backlog rows from a review is the accepted
shape. Follow it, including its one-commit-per-row structure.

### 3.3 The PR

Branch `docs/pr31-32-review-followups` off `develop` @ `5fc1485`, **four commits** (three
review-sourced rows plus BL-22 per D4), `Developer/BACK_LOG.md` only. Row text: reuse the drafts in
`Plans/archive/followups-tracking-note.md` §2 verbatim except —

- renumber BL-10/11/12 → **BL-19/20/21**;
- BL-19's file reference is **correct as drafted** — verified: `read_pid` at `main.py:69`,
  `is_process_running` at `:70`, `remove_pid` at `:78`, `write_pid` at `:95`, with no `flock`/`O_EXCL`
  anywhere in `dincli/dind/process.py`;
- BL-20 and BL-21's references verified unchanged (`health.py:40` always `send_response(200)`,
  `status` computed at `:57-62`; `logging.py:64` plain `StreamHandler`, no `FileHandler` in the
  package).

Phase `P4-1.1`, source `PR #32 code review finding No. N, Jul 30, 2026`, per the drafts.

**BL-22 — included per D4.** `followups-tracking-note.md` §4 records `NonceManager._instances` never
being evicted (process-wide mutable state keyed by `(chain_id, address)`, already a source of real
test pollution). Not from either review, but the one §4 item that becomes load-bearing the moment
`dind` runs long-lived. Source it honestly as `task_300726_8` implementation note, Jul 31, 2026 —
not as a review finding.

---

## 4. Workstream C — the `develop` sync

### 4.1 Shape

`develop` is **49 commits** ahead of merge-base `98d4837`; `feat/din-sdk` is 21 ahead. Merging
`upstream/develop` into `feat/din-sdk` produces **3 conflicts**:

| File | Conflict hunks | `develop` side | our side |
|---|---|---|---|
| `dincli/cli/utils.py` | 4 | +95 / −0 | −758 (reduced to shims) |
| `dincli/services/ipfs.py` | 1 | +287 / −41 | −273 (reduced to a shim) |
| `dincli/services/cid_utils.py` | 1 | +18 | −83 (reduced to a shim) |

`dincli/cli/system.py`, `tests/test_connect_wallet.py` and the rest auto-merge.

### 4.2 Why this is not a conflict-resolution job

All three conflict files are files **we emptied into `dincli/sdk/`**, and `develop` has since put
real work back into them. Taking "ours" silently drops that work. Every `develop`-side change has to
be **forward-ported into the SDK module** that now owns the code, with `services/`/`cli/` left as the
re-export shim.

| `develop` change | Commit(s) | Now owned by | Notes |
|---|---|---|---|
| `get_w3` chain-id validation (4 stages) + `ChainIdMismatchError` | `386f9ef`, `31af2ca` (PR #98) | `dincli/sdk/web3.py` | Our `get_w3` is 25 lines with **no** chain-id check. Contract per D1 (§6). |
| `validate_cid()` (py-cid validation, rejects path traversal) | PR #96 | `dincli/sdk/cid.py` | +18 lines, self-contained. |
| IPFS retrieval rework — `_compute_ipfs_cid_local`, `_verify_downloaded_cid`, `_is_kubo_path`, `_build_retrieve_url`, `_should_use_fallback`, `_retrieve_via_url`, `_write_response_to_file`, `DEFAULT_PUBLIC_GATEWAY`, 3 warn-once globals | `3136d39`, `b506f75` (PR #96) | `dincli/sdk/ipfs.py` | **The big one.** `sdk/ipfs.py` has *none* of it (grep `verify`/`gateway`: zero hits). |
| `_get_password` quiet lookups, `load_account` changes | `466c770`, `f8688a9` (PR #100) | `dincli/sdk/wallet.py` + `dincli/cli/signer.py` | The only place the two refactors overlap — resolve carefully. |
| `ReadResult` + `read_after_write()` | `466c770` | `dincli/cli/utils.py` (stays) | Purely additive, CLI-level. |

**What the CID work actually guarantees.** `_verify_downloaded_cid` recomputes the CID of downloaded
content with a local kubo binary and **refuses to save on mismatch** — genuine integrity hardening.
But it is **best-effort by design**, with two named degraded paths, both verified in develop's source:

- `if provider == "custom": return` — skipped entirely for user-supplied provider modules, because
  their chunking/CID settings may legitimately differ.
- `_compute_ipfs_cid_local` returns `None` when no usable `ipfs` binary exists (missing, never
  `init`-ed, timeout); the caller emits a **one-time warning and saves the file anyway**.

Describe it as CID-integrity hardening with explicit degraded behavior — not as an unconditional
guarantee. §5 names the four behaviors that must survive the port.

### 4.3 Merge construction — no committed tree may regress

**Rev 1 got this wrong.** It put the merge commit first and the forward-ports after, which means the
merge commit's own tree resolves the shims "ours" and **loses develop's CID-integrity work for
several commits**. That is a knowingly regressive commit and it poisons `git bisect`.

**Rev 3 then made the opposite error:** it moved the forward-ports into the merge but left D1, the
password/signer repair and the test retargeting *after* it — while still demanding a green suite
*before* the merge commit. Those cannot both hold. Until the retargeting lands the incoming tests
patch dead shims; until D1 lands they assert builtin `ConnectionError`; until the password overlap is
resolved that path may be behaviorally broken. The gate would fail by construction.

**Everything required for green goes inside the merge resolution.** One commit, whose tree is the
first tree that both preserves develop's behavior and passes:

```
merge: sync upstream/develop into feat/din-sdk
   ├─ resolve all three conflicts; relocate every conflicting develop function
   │  into dincli/sdk/{web3,cid,ipfs}.py
   ├─ D1: ChainIdMismatchError, the 3-stage contract, allowlist entry,
   │      cli/core.py handler + DIN_DEBUG, delete cli/system.py:1625
   ├─ _sanitize_host() hardening (§4.4a)
   ├─ resolve the quiet-password / signer-split overlap
   └─ retarget the incoming tests per §4.5, and rewrite the chain-id tests
      onto SDK types and stable codes
```

Working method: do all of it in the working tree with the merge **uncommitted**
(`git merge --no-commit`), run §5's suite until green, and only then commit. The commit message must
enumerate the above — a merge commit doing this much work is only acceptable if it says so.

**A1 stays a separate post-merge commit** and is self-consistent on its own, because it changes the
error types and the tests asserting them together:

```
fix(sdk): IPFS error taxonomy — IpfsError/ConfigError/ValidationError   [review #31 No. 5]
```

Reviewer readability is worth less than every committed tree retaining the security behavior and
passing its tests.

### 4.4 A regression to fix while we are in there

Our extracted `get_w3` **reintroduces a credential leak that `develop` deliberately removed.**
`dincli/sdk/web3.py` raises:

```python
raise NetworkError(f"Could not connect to Ethereum node at {rpc_url}", ...)
```

`develop`'s version carries an explicit comment that the URL is kept out of `str()` and out of any
formatted traceback (`from None`; the message names the *network*, not the endpoint) — because RPC
URLs routinely embed API keys.

Fix under D1: the message names the network, never the URL, and chaining is `from None`.

### 4.4a The `details` half is **not** safe either — `_sanitize_host()` must be hardened

Rev 2 and rev 3 both claimed `endpoint_host` was already safe because it is typed `"host"` in the
allowlist and `_sanitize_host()` strips userinfo and query. That is wrong in the most common case:
**the normalizer preserves `parts.path`**, and path-style API keys are how the two largest RPC
providers work. Run against the current implementation:

| input | current output |
|---|---|
| `https://mainnet.infura.io/v3/SECRET_KEY` | `https://mainnet.infura.io/v3/SECRET_KEY` ❌ |
| `https://eth.alchemy.com/v2/SECRET_KEY` | `https://eth.alchemy.com/v2/SECRET_KEY` ❌ |
| `https://user:pw@node.example/rpc?apikey=SECRET` | `https://node.example/rpc` ✅ |
| `not a url at all SECRET` | `not a url at all SECRET` ❌ |

So a credential reaches `DinError.to_error()["details"]` — the envelope the daemon is designed to log
— on the two most common endpoint formats, plus any input `urlsplit` cannot parse.

**Fix in `errors.py`:** `"host"` normalization keeps **only** `scheme://hostname[:port]` — drop path,
query, params and fragment — and the unparseable fallback returns a fixed placeholder
(`"<unparsable-endpoint>"`), never the input. Losing the path costs a little diagnostic precision;
host+port still identifies the endpoint, which is what the field is for.

**Tests** (none of these exist today): userinfo, query-string key, **path key** (both provider
shapes), fragment, and malformed/opaque input — each asserting the secret is absent from the
sanitized value.

This is a change to `errors.py` shared by every code using the `"host"` kind
(`network_unreachable`, `rpc_unreachable`), so it lands in the merge commit alongside D1, not in A1.

### 4.5 Tests that will break — 67 of them, and the patch mapping

`develop` brings **165 new tests** in five files not on our branch:

```
test_bridge_eth.py 46 · test_ipfs_retrieval.py 47 · test_scoring.py 36
test_chain_id_validation.py 20 · test_develop_small_backports.py 16
```

Two of those files patch **by module attribute**, which the shim layout defeats — patching a
re-exported name on the shim does not touch the binding the SDK function actually reads:

| Old patch target | New target | Why |
|---|---|---|
| `dincli.cli.utils.Web3` | `dincli.sdk.web3.Web3` | `get_w3` body lives in `sdk/web3.py` |
| `dincli.cli.utils.resolve_network_value` | `dincli.sdk.web3.resolve_network_value` | resolved via `sdk.web3`'s own import |
| `dincli.cli.utils.load_din_info` | `dincli.sdk.web3.load_din_info` | same |
| `dincli.services.ipfs.*` (17 `setattr`) | `dincli.sdk.ipfs.*` | includes the globals `_warned_fallback`, `_warned_no_provider`, `_warned_no_verify` |
| `dincli.cli.utils.CONFIG_DIR` / `CONFIG_FILE` (4 `setattr`) | `dincli.sdk.config.CONFIG_DIR` / `CONFIG_FILE` | **missed in rev 1.** Defined at `sdk/config.py:12,20`; `cli/utils.py:23` merely re-imports them, and `resolve_ipfs_config()` (`sdk/config.py:115`) reads the `sdk.config` bindings via `load_config()` |

The alternative — leaving the moved code in `services/`/`cli/` so the patches keep working — undoes
the extraction this PR exists to do. Expect this to be the fiddliest hour of the sync.

### 4.6 A1 — the IPFS error conversion table

Rev 1 said "extend the swap to whatever develop's new IPFS functions raise". Taken literally that
flattens distinct failure classes into one code. `develop`'s `services/ipfs.py` has **20 raise
statements** (rev 3 said 14 and covered 17, one of them mislabeled). All 20 below, plus the
`validate_cid()` call, with the incoming test each conversion changes.

| Raise site (develop line) | Today | → | Rationale | Incoming test |
|---|---|---|---|---|
| `_raise_for_http_error` `:263` | `RuntimeError` | **`IpfsError`** | provider/HTTP failure; allowlist entry already exists. **Also fix the leak** — see below | — |
| `upload_to_ipfs` RequestException `:351` | `RuntimeError` | **`IpfsError`** | same | — |
| `retrieve_from_ipfs` RequestException `:476` | `RuntimeError` | **`IpfsError`** | same | `:303`, `:320` assert `RuntimeError` → **update** |
| `_verify_downloaded_cid` mismatch `:167` | `ValueError` | **`IpfsError(code="ipfs_cid_mismatch")`** | integrity failure the daemon must branch on distinctly from transport failure; new allowlist entry `{"requested_cid": "str", "computed_cid": "str"}` | `:389` asserts `ValueError, match="CID mismatch"` → **update type, keep message** |
| no retrieval endpoint configured `:380` | `ValueError` | **`ConfigError`** | user configuration, not a provider fault | `:192` asserts `ValueError` → **update** |
| `_should_use_fallback` gateway URL validation `:244,248,250,252` | `ValueError` | **`ConfigError`** | validates `IPFS_PUBLIC_GATEWAY`; 4 parametrized cases | `:286` asserts `ValueError` → **update** |
| `_require_custom_service_path` missing `ipfs_service_path` `:101` | `ValueError` | **`ConfigError(details={"key": "ipfs_service_path"})`** | **omitted in rev 3.** Missing config | — → **add** |
| `_upload_via_env` missing `IPFS_API_URL_ADD` `:270` | `ValueError` | **`ConfigError(details={"key": "IPFS_API_URL_ADD"})`** | **omitted in rev 3.** Missing config | — → **add** |
| `_upload_via_filebase` missing `ipfs_api_key` `:287` | `ValueError` | **`ConfigError(details={"key": "ipfs_api_key"})`** | **omitted in rev 3.** Missing config | — → **add** |
| `_retrieve_via_filebase` missing `ipfs_api_key` `:391` | `ValueError` | **`ConfigError(details={"key": "ipfs_api_key"})`** | **omitted in rev 3** — and this is the line rev 3 mislabeled as the invalid-CID row | — → **add** |
| `validate_cid()` **call** at `:450` (raises from `cid_utils.py:84` + py-cid) | `ValueError` | **`ValidationError`, raised by `sdk.cid.validate_cid()` itself** | See the decision below | `:363` asserts bare `Exception` → **passes either way** |
| unsupported provider `:343`, `:469` | `NotImplementedError` | **`ConfigError`** | a bad `provider` value is a config problem. *The one judgment call in this table* — flag it in the PR body rather than burying it | — |
| custom-plugin contract violations `:66,72,76,320` | `ImportError` / `AttributeError` / `TypeError` / `TypeError` | **preserve** | plugin-author bugs, not SDK domain errors; wrapping hides the real cause | — |
| `FileNotFoundError` `:58` | builtin | **preserve** | a stdlib condition with a stdlib meaning | — |

**Where `validate_cid` converts — decided: inside `sdk/cid.py`.** `validate_cid()` becomes an SDK
function, and the SDK's contract is that domain errors cross its boundary as `DinError`; translating
per call site duplicates the work and misses future callers. It has only two callers today
(`cid_utils.py:78` internal, `ipfs.py:450`), so the blast radius is known. Wrap py-cid's own
exceptions from `make_cid()` too, not just the explicit `ValueError` at `cid_utils.py:84`. Note
`ipfs.py:450` calls it only when `provider != "custom"` — preserve that guard.

**Two message-level leaks to fix in the same pass** (found in rev 4 review, both verified):

- `_raise_for_http_error:261-265` embeds up to 300 characters of `response.text` in the message
  **and** chains `from exc`, whose `requests.HTTPError` string contains the full request URL — which
  for Filebase/env providers carries the API key. Fix: `from None`, message names provider + status
  code only, and put the bounded body in `details` under the allowlist's existing `"stderr": "tail"`
  kind where sanitization applies.
- `retrieve_from_ipfs:475` logs the raw `RequestException` at ERROR (`f"...: {exc}"`), same URL
  exposure, into whatever the daemon captures. Fix: log `type(exc).__name__` — the pattern
  develop's own `get_w3` already uses — and raise `from None`.

**On the CID-mismatch message — rev 3 contradicted itself; resolved in favor of keeping it.** The
table says "keep message" while rev 3's test requirement forbade any full CID. **A CID is a public
content address, not a credential**, so that requirement was over-broad: keep develop's message
verbatim (full computed CID, `[:12]`-truncated requested CID) so both the diagnostic value and the
incoming `match="CID mismatch"` assertion survive, and carry both full values in sanitized `details`.

**Correcting rev 1's "no behavior change" claim.** That holds for the five CLI `except RuntimeError`
handlers — verified: all five guard `ensure_worker_image`/`ensure_worker_packages_installed`, none
guard an IPFS call, and the actual IPFS call sites catch `except Exception` (`aggregator.py:325`,
`:478`, `client.py:275`) or nothing (`context.py:549`, `ipfs.py:19`, `:28`,
`modelownerd/model.py:156`). But the exception **type and stable `.code` are the observable this
work exists to create**, and develop's incoming tests assert the concrete types at four sites. The
conversion is a deliberate, tested behavior change, not a silent one.

**Correcting rev 1's "no behavior change" claim.** That holds for the five CLI `except RuntimeError`
handlers — verified: all five guard `ensure_worker_image`/`ensure_worker_packages_installed`, none
guard an IPFS call, and the actual IPFS call sites catch `except Exception` (`aggregator.py:325`,
`:478`, `client.py:275`) or nothing (`context.py:549`, `ipfs.py:19`, `:28`,
`modelownerd/model.py:156`). But the exception **type and stable `.code` are the observable this
work exists to create**, and develop's incoming tests assert the concrete types at four sites. The
conversion is a deliberate, tested behavior change, not a silent one.

**New tests required alongside** — one per property, since none of this is covered today:
`.code` is the expected stable string; `details` survive `sanitize_details` with the right keys;
chaining is `from None` on every path whose cause may carry a credential (all `requests` paths);
and the message contains **no URL and no credential** — CIDs are exempt, per the resolution above.

### 4.7 Then the daemon branch

`git merge feat/din-sdk` into `feat/din-daemon`. No conflicts expected — `develop` never touches
`dincli/dind/*` (verified) — but re-run the `dind` boundary test, since the SDK's import surface
changes underneath it.

### 4.8 What the PRs look like afterwards

Both stay drafts targeting `upstream/feat/din-sdk` @ `805ce9d`. Nothing here changes the base.
**Nothing reaches `develop` until a separate `feat/din-sdk` → `develop` PR exists**, which is its own
decision and out of scope — but every week this sync is deferred, §4.2's table grows.

---

## 5. Verification

```bash
V=/home/santi/InfiniteZero/DevNet/.venv/bin/python
$V -m pytest -q --ignore=tests/test_cache_client_dp.py --ignore=tests/dincli
```

| Point | Expected |
|---|---|
| `feat/din-daemon` after A2–A4 | 316 → **317**, all pass |
| `feat/din-sdk` after the sync | 247 + 165 + the `test_dintoken.py`/`test_connect_wallet.py` additions. Planning estimate ≈420; **record the exact collected count once the merged tree exists and use that as the criterion** — collection is deterministic, an approximation is not an acceptance test |
| `feat/din-daemon` after merging the synced SDK | the SDK total + its **70** `dind` tests (69 + A3's), all pass |
| Boundary tests | `tests/test_sdk_boundary.py`, `tests/test_dind_boundary.py` green — non-negotiable, they are the architecture |

**CID-integrity acceptance — four named behaviors, not a test count.** `test_ipfs_retrieval.py`
passing at 47/47 is necessary but not sufficient; assert these survived the port explicitly:

1. mismatch → refuses to save, destination absent;
2. match → saves;
3. verifier unavailable (no `ipfs` binary) → one-time warning, **saves anyway**;
4. `provider == "custom"` → verification bypassed by design.

`tests/dincli/` (Hardhat/Foundry live-chain harness) stays excluded as in every prior slice.
`tests/test_cache_client_dp.py` **can** run in `DevNet/.venv` (torch present) — worth one run after
the sync since `develop` moved contract code.

---

## 6. Decisions needed

### D1 — the SDK error contract for `get_w3` — **DECIDED 2026-08-27**

**Decision: the `DinError` shape, with a broad CLI catch and a `DIN_DEBUG` escape hatch.** It is the
only option consistent with a daemon-facing SDK — `ConnectionError` carries no stable `code`, so
`dind` would have nothing to key retries off. The full contract, which rev 1 left implicit:

```python
class ChainIdMismatchError(DinError):
    code = "chain_id_mismatch"
```

| Stage | Failure | Raises |
|---|---|---|
| 1 | connect / `is_connected()` false | `NetworkError(code=RPC_UNREACHABLE, details={"endpoint_host": rpc_url})`, `from None` |
| 2 | `w3.eth.chain_id` read fails | `NetworkError(code=RPC_UNREACHABLE, ...)`, `from None` |
| 3 | `actual != expected` | `ChainIdMismatchError(details={"network", "expected_chain_id", "actual_chain_id"})` |

Also required:

- **Allowlist entry** in `errors.py`:
  `"chain_id_mismatch": {"network": "str", "expected_chain_id": "int", "actual_chain_id": "int"}`.
  Without it `sanitize_details` drops all three keys — codes with no schema yield `{}`.
- **Message secrecy** per §4.4: stages 1/2 name the network, never the URL; `from None` so the
  provider's exception text cannot resurface in a traceback.
- **Re-export `ChainIdMismatchError` from `dincli.cli.utils`** so the name resolves where develop's
  code and tests expect it.
- **Change the CLI boundary.** `cli/core.py:40` currently reads
  `except (ChainIdMismatchError, ConnectionError)`. Catching `ConnectionError` no longer covers
  stages 1 and 2, because `NetworkError` is a `DinError(Exception)`, **not** a `ConnectionError`.
  Decided shape:

  ```python
  except (DinError, ConnectionError) as e:
      if os.getenv("DIN_DEBUG") == "1":
          raise
      click.secho(str(e), err=True, fg="red")
      sys.exit(1)
  ```

  This is a top-level `TyperGroup.invoke` wrapper whose whole job is one-line red rendering + exit 1,
  so every SDK domain error shares that policy — and `DIN_DEBUG=1` still recovers the traceback,
  which matters because a `ValidationError` raised by a genuine bug would otherwise be
  indistinguishable from clean user error.

  **Exact `== "1"`, not truthiness.** `if os.getenv("DIN_DEBUG")` would enable debug for
  `DIN_DEBUG=0` and `DIN_DEBUG=false`, which is the opposite of what those say. Document the
  contract as `DIN_DEBUG=1` in the CLI docs and in PR #31's body.

  **What debug does and does not restore.** It re-raises the *sanitized* exception, so the stack is
  recovered but every `from None` still suppresses the provider cause — deliberately, since that
  cause is exactly what may carry a credential (§4.4, §4.6). Debug mode is not an exception to the
  disclosure policy. When the cause matters for support, it is the `logger.debug` of the exception
  *type* that carries it, per develop's own `get_w3` pattern.

  **`ConnectionError` stays for compatibility — rev 3's stated evidence was wrong.**
  `services/bridge.py:125` raises builtin `ConnectionError` inside a `try` whose `except Exception`
  immediately rewraps it as `PreflightRejected`, caught earlier as `BridgeError`; it never reaches the
  global handler. After `get_w3` moves to `NetworkError`, **no verified site raises a builtin
  `ConnectionError` that reaches this handler.** Keep it anyway, on the honest grounds: the stdlib's
  `ConnectionRefusedError`/`ConnectionResetError` are `ConnectionError` subclasses, so any raw-socket
  failure surfacing unwrapped from a dependency lands here rather than as a traceback. Cheap
  insurance, not evidence of a live path.

  **State this as a deliberate behavior change:** SDK errors that previously escaped as tracebacks —
  `IpfsError` after §4.6 among them — now render as one line. That is an improvement, but it
  invalidates the previous slice's golden-parity run. Re-run parity per **§7 of
  `Developer/design/sdk-interface-proposal.md`** ("Backward-compatibility guarantees + test
  strategy") — rev 3 pointed at §7 of *this* plan, which is the out-of-scope list. Concretely: run
  `dincli dindao deploy din-coordinator` against a local anvil on `4ab0114` and on HEAD in separate
  venvs, normalize tx hash and addresses, and diff stdout, stderr **and** exit code. Cover at least
  one *failing* path this time (point `--network local` at a dead RPC port): that is the case the
  handler change actually alters, and the previous run only covered the success path.
- **`cli/system.py:1625` goes dead — handle it deliberately.** `bridge-eth` catches bare
  `ConnectionError` with the comment *"#83 handles this globally once merged; local handling closes
  the gap on plain main and stays harmless afterwards."* After the port an RPC connect failure there
  arrives as `NetworkError`, so the local handler stops firing and the global one takes over. Net
  effect: still one red line, still exit 1, but the message changes from
  `"could not connect to a blockchain RPC endpoint"` to the SDK's. Either delete the dead handler
  (its own comment anticipates exactly this) or widen it to `(NetworkError, ConnectionError)` to keep
  the bespoke wording. Recommend deleting — the global policy is the point of D1. Note it in the PR
  body; neither review caught this site.
- **Rewrite the incoming tests** to assert SDK types and stable `.code` values, not builtin
  `ConnectionError`.

### D2–D4

| # | Decision | Recommendation |
|---|---|---|
| D2 | Retarget develop's tests at `dincli.sdk.*`, or keep the code in `services/` so its patches work? | Retarget, per §4.5's mapping. |
| D3 | `dind.service`: rename to `dind@.service`, or hardcode a placeholder user? | Rename (§2.2). |
| D4 — **DECIDED** | Include BL-22 (`NonceManager._instances`) in workstream B? | **Yes.** The one non-review item that bites once `dind` is long-lived, and it already caused real test pollution. §3.3 is updated to four rows / four commits. Trivially reversible: drop the fourth commit if Umer prefers the PR stay strictly review-sourced. |

All four decisions are recorded — **no open decision blocks any workstream.**

---

## 7. Explicitly not in scope

- **PR #31 findings No. 2, 3, 4** (double `getModel` on `--info`; `uint256_string`/`address`
  validation in `serialize.py`; the amount-tagging scan test and `correlation_id` origin). All still
  open, all non-blocking, none touched here.
- **PR #32 findings No. 1, 2, 6** — *tracked* by workstream B, **not fixed**. That is what the review
  asked for.
- **Replying to the two reviews.** Not one of the three items, but the cheapest thing on the board;
  both reviews have sat unanswered since Jul 30, and this plan writes most of the reply. PR #32's
  body also needs its `systemctl enable --now dind.service` line corrected (§2.2).
- Anything that changes either PR's draft status, base branch, or requests re-review.
