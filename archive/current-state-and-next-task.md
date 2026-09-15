# Current State & Next Task — SDK (#20) + Daemon (#21)

**Author:** Santiago (@Santiagocetran) · **Written:** 2026-07-23 · **Updated:** 2026-07-23 (Parts A + B shipped)
**Active task:** `task_220726_7` — SDK state/serialize layer + daemon preferences & capability detection
**Deadline:** Tuesday **2026-07-28** (5 working days, started Jul 22)

This is my living handoff doc: where the two issues/draft-PRs stand, the feedback Umer gave,
what this week's task is, what I verified, and what's done vs. still to do. Older plans live
in `Plans/archive/`. Implementation detail: `Plans/archive/part-A-sdk-state-serialize-plan.md`,
`Plans/archive/part-B-daemon-preferences-capabilities-plan.md`.

## Status at a glance (2026-07-23) — `task_220726_7` implementation COMPLETE

- ✅ **Part A DONE & pushed** — `sdk/state.py` + `sdk/serialize.py` on `feat/din-sdk`, in PR #31
  (head `6eac109`). Commits `4fa4f03` (state extraction + predicates) and `6eac109` (serializer),
  on the `develop` merge `0a6e207`. PR #31 body updated; progress commented in Discussion #50.
- ✅ **Part B DONE & pushed** — `dind/preferences.py` + `dind/capabilities.py` (+ `/health` wiring)
  on `feat/din-daemon`, in PR #32 (head `99f060b`, one atomic commit on the `feat/din-sdk` sync
  merge `a9692e9`). **213 unit tests green** (dind + sdk). PR #32 title/body updated; Part B
  progress commented in Discussion #50.
- ⏭️ **Deferred → the next task, flagged for Umer** — wallet/session/tx keystone (`wallet.py`,
  `session.py`, `SignerProvider` §2, `tx.send()` §5b) + the `operations/` role layer. Not started
  (out of scope for this task). `dind` does no signing / on-chain submission until this lands.

> Both PRs remain **drafts pending review**; both branches synced to `develop`. Nothing else
> outstanding for `task_220726_7` beyond review feedback.

> **Link freshness (verified 2026-07-23):** all links below resolve on `github.com`.
> - `task_220726_7.md` is on `develop` (via `f281e26`) and on both feature branches.
> - The SDK proposal has **not merged to `develop` yet** (lives on `feat/din-sdk`), so its link is
>   pinned to commit `ba5a54d`, not `develop`.

---

## Links (start here)

| What | Link |
|---|---|
| Issue #20 — DIN-SDK | https://github.com/InfiniteZeroFoundation/DevNet/issues/20 |
| Issue #21 — `dind` daemon | https://github.com/InfiniteZeroFoundation/DevNet/issues/21 |
| PR #31 (draft) — `feat/din-sdk` | https://github.com/InfiniteZeroFoundation/DevNet/pull/31 |
| PR #32 (draft) — `feat/din-daemon` (stacked on #31) | https://github.com/InfiniteZeroFoundation/DevNet/pull/32 |
| Discussion #50 — Umer's assignment thread + feedback | https://github.com/InfiniteZeroFoundation/DevNet/discussions/50#discussioncomment-17741496 |
| Discussion #50 — our Part A progress comment | https://github.com/InfiniteZeroFoundation/DevNet/discussions/50#discussioncomment-17752710 |
| Discussion #50 — our Part B progress comment | https://github.com/InfiniteZeroFoundation/DevNet/discussions/50#discussioncomment-17753363 |
| **Task file** `task_220726_7.md` | https://github.com/InfiniteZeroFoundation/DevNet/blob/develop/Developer/tasks/task_220726_7.md |
| SDK interface proposal (design spec — not yet on `develop`, pinned to PR #31 head) | https://github.com/InfiniteZeroFoundation/DevNet/blob/ba5a54d/Developer/design/sdk-interface-proposal.md |

---

## 1. Current state of the two branches

Both draft PRs were opened early per the "keep feature-branch work visible" convention; both
are now synced to `develop` and carry their task slice, but remain drafts pending review.

| Branch | PR | PR head (= local, in sync) | Status |
|---|---|---|---|
| `feat/din-sdk` | #31 draft | `6eac109` (Part A + `develop` merge, pushed 2026-07-23) | ✅ Part A shipped; synced to `develop` |
| `feat/din-daemon` (stacked on `feat/din-sdk`) | #32 draft | `99f060b` (Part B + `feat/din-sdk` sync `a9692e9`, pushed 2026-07-23) | ✅ Part B shipped; synced |

### SDK — `dincli/sdk/` (PR #31)
Now **11 of the 16** modules in proposal §8's target layout:
`cid`, `errors`, `config`, `log`, `web3`, `ipfs`, `contracts`, `manifest`, `runtime`, **`state`, `serialize`** (last two added by Part A).

- `errors.py` ships the full `DinError` taxonomy and allowlist-based `sanitize_details` (proposal
  §4/§4a), including `ValidationError` (`code="validation_failed"`) that Part A's predicates use.
- Import-boundary is enforced by `tests/test_sdk_boundary.py` (fresh-subprocess
  `pkgutil.walk_packages` check that no SDK module pulls in `typer`/`rich`/`dincli.cli.*`);
  extended to assert `state`/`serialize` too.

**Still missing from proposal §8:** `session.py` (`DinSession`), `wallet.py`, `tx.py`, `worker.py`,
and the `operations/` role-command layer — the wallet/session/tx group is the deferred next task.

### Daemon — `dincli/dind/` (PR #32, present on `feat/din-daemon`)
P4-1.1 scaffold: lifecycle (`start`/`stop`/`status`), SQLite job queue, graceful SIGTERM,
`/health`, structured JSON logging, systemd/launchd examples, container handoff. Config uses a
`resolve_*` precedence pattern (`--flag > env > config.json > default`) in `dind/config.py`;
path helpers in `dind/paths.py`.

**Part B added (P4-2.1/2.2, local-only):** `dind/preferences.py` + `dind preferences show/set`
(`preferences.json` via `StateDirs.preferences_path`); `dind/capabilities.py` + `dind capabilities`
(CPU/RAM/disk/GPU + bare RPC/IPFS socket probes; no new dependency); `/health` `resources` now
uses a shared fast `resource_snapshot()` (GPU/network probes stay off the poll path).

> Note: `dincli/dind/` lives on `feat/din-daemon` (not `feat/din-sdk`). Both parts are now done —
> Part A on `feat/din-sdk`, Part B on `feat/din-daemon` (synced onto `feat/din-sdk`).

---

## 2. Umer's feedback (Discussion #50)

Umer reviewed the SDK interface proposal and **approved** §§2 (session/signer), 3
(envelope/serialization), 4/4a (errors), 5b (tx keystone), 6 (plan/apply), 8 (package
layout) — "with a handful of open questions noted per-section."

- **His heaviest concern:** nonce management under §5b — "a live gap in `get_tx_params()`'s
  nonce fetch today, not just a doc nit."
- **Crucially for us:** *"None of those open items touch `state.py`, `serialize.py`,
  preferences, or capability detection, so they don't block this task — they'll matter once
  you get to `wallet.py`/`session.py`/`tx.py`."*

**Takeaway:** the feedback validates the scope split rather than redirecting it. The nonce/
signing concerns land in the *next* task, not this one.

---

## 3. The task — `task_220726_7`

Deliberately carves off the two lowest-risk, most self-contained slices and **defers all
wallet/session/signing** to a dedicated future task.

### Part A — SDK (`feat/din-sdk`, PR #31) — Issue #20, P4-1.2 — ✅ DONE (pushed, 144 tests green)

> Shipped as committed: `4fa4f03` (state extraction + `GIState` + predicates + output-preserving
> `context.py` delegation) and `6eac109` (serializer). The A1–A3 spec below is retained for the record.

**A1. `dincli/sdk/state.py`** — extract GI-state converters from `cli/utils.py`
(`GIstateToDes`, `GIstateToStr`, `GIstatestrToIndex`), leaving a re-export shim
(`from dincli.sdk.state import ...  # noqa: F401`), same pattern as the `85ceae7` wave.
Add `validate_*` predicates that raise `dincli.sdk.errors.ValidationError` — **only lifting
checks that already exist in the CLI**, no new rules invented.

**A2. `dincli/sdk/serialize.py`** — new `to_envelope()` + shared encoder (proposal §3).
Envelope shape: `{status, data, error, meta}`. Encoder rules, each tested explicitly:
- `metadata={"json": "uint256_string"}` → decimal **string** (JS precision safety)
- `metadata={"json": "omit"}` → dropped entirely
- small ints (GI number, indices, enum-backed ints) → stay JSON numbers
- `bytes`/`HexBytes` → `0x`-prefixed hex
- addresses → checksummed (`Web3.to_checksum_address`, don't hand-roll)
- enums → **name** string in `data`
- `Decimal` → string

**A3. Tests** — `tests/test_sdk_state.py`, `tests/test_sdk_serialize.py`, and confirm/extend
`tests/test_sdk_boundary.py` covers the two new modules.

### Part B — Daemon (`feat/din-daemon`, PR #32) — Issue #21, P4-2.1 / P4-2.2 (local-only) — ✅ DONE (pushed, 213 tests green)

> Shipped as commit `99f060b` on the `feat/din-sdk` sync merge `a9692e9`. The B1–B3 spec below is retained for the record.

**B1. `dincli/dind/preferences.py`** — 4-field dataclass
(`domain`, `risk_tolerance="moderate"`, `min_expected_reward: int|None`,
`privacy_constraints: list[str]`), stored as `preferences.json` under the resolved state dir
(reuse `dind/paths.py`, mirror `dind/state.py`'s load/save shape). New commands:
`dind preferences show` (JSON out, reuse `dind/logging.py` conventions — no `rich` in `dind`)
and `dind preferences set --domain/--risk-tolerance/--min-reward/--privacy` (partial updates
only touch passed flags).

**B2. `dincli/dind/capabilities.py`** — `CapabilitySummary` dataclass +
`detect_capabilities()`, `score_capabilities()`, `compatible_with()`. Detect stdlib-first:
CPU count (`os.cpu_count()`, reuse `health.py:83`), RAM (needs `psutil` — flag the new dep in
PR, or document deferral), disk free (factor `health.py:66-73`'s `shutil.disk_usage` into a
shared helper), GPU (best-effort `nvidia-smi`/`/dev/nvidia*`, absence is normal), and
RPC/IPFS **bare reachability probe** (`socket.create_connection` w/ short timeout — *not* a
live RPC call; read endpoints via `dincli.sdk.config`). New command `dind capabilities` (JSON).
**Extend `/health`'s `resources` block** (`health.py:82-86`) to use the fuller summary.

**B3. Tests** — `tests/test_dind_preferences.py`, `tests/test_dind_capabilities.py` (mock/skip
GPU+network; assert well-formed summary, `score_/compatible_` are pure), extend
`tests/test_dind_health.py` for the new `resources` fields.

### Scope boundaries (do NOT cross)
1. **No** wallet/keystore/signing (`wallet.py`, `session.py`, `SignerProvider` §2) — deferred.
2. **No** `tx.py` `send()` §5b keystone (needs `DinSession`).
3. **No** `operations/` role-command refactor.
4. RPC/IPFS check stays a lightweight reachability probe, not a session RPC call.
5. **No** change to existing CLI command behavior/output — `state.py`/`serialize.py` are additive.

### Release valve (if the week runs tight)
Cut Part B's GPU detection and `compatible_with()` first (least load-bearing). **Never** cut
`state.py`/`serialize.py` — every later `operations/` module depends on the envelope shape.

---

## 4. What I verified against the branches (findings & gotchas)

> These were confirmed and handled during Part A — kept here as the record of *why* the
> implementation looks the way it does. All four held true in the shipped code.

1. **The three converters aren't fully self-contained.** `GIstateToDes/Str/strToIndex`
   (`cli/utils.py:385/393/405`) are pure of `console`/`typer` ✅ but depend on module-level
   data `stateDescription` (line 329), `states` (355), `GIstate_to_index` (382). **Those data
   structures must move into `state.py` too** and be re-exported alongside the functions.

2. **The "inline validation to lift" is NOT in `modelownerd/`** (grep there found only a
   comment). The real gates are two methods on `DinContext` in **`cli/context.py:563-571`**
   (`validate_GIstate_ET_given_GIstate` / `validate_GIstate_LTE_given_GIstate`; shifted from
   525 after the 2026-07-23 develop merge). They **mix
   the predicate with `console.print` + `typer.Exit`**.
   → **Design:** put pure predicates in `sdk/state.py` that raise `ValidationError`; keep the
   CLI methods' exact red-text output (boundary #5) but delegate the boolean decision to the
   SDK. This is the one spot that needs care.

3. **Boundary test already auto-covers new modules.** `test_sdk_boundary.py` uses
   `pkgutil.walk_packages`, so `state`/`serialize` are checked the moment they exist — the
   "extend the module list" ask is effectively satisfied (add an explicit assertion at most).

4. **Branch layout confirms Part A → Part B order.** `dincli/dind/` only exists on
   `feat/din-daemon`; the branches are stacked, so push Part A on `feat/din-sdk` first, then
   rebase `feat/din-daemon` onto it partway through the week to stop the PRs drifting.

---

## 5. How to continue — working order

**On `feat/din-sdk` (Part A) — ✅ ALL DONE:**
1. ✅ `state.py` — moved `states`/`stateDescription`/`GIstate_to_index` + 3 converters; shim in `cli/utils.py`.
2. ✅ `state.py` — pure `validate_*` predicates (raise `ValidationError`); `context.py`'s two methods delegate, output identical.
3. ✅ `serialize.py` — `to_envelope()` + encoder, all rules (incl. `None`→null edge case).
4. ✅ Tests: `test_sdk_state.py`, `test_sdk_serialize.py`, `test_sdk_boundary.py` extended.
5. ✅ `pytest` clean (144) → PR #31 title+body updated → pushed (`6eac109`) → progress commented in #50.

**On `feat/din-daemon` (Part B) — ✅ ALL DONE:**
6. ✅ **Synced:** merged `origin/feat/din-sdk` (= `develop` + Part A) into `feat/din-daemon` (`a9692e9`, clean); suite green.
7. ✅ `preferences.py` + `dind preferences show/set` (partial updates, risk validation).
8. ✅ `capabilities.py` + `dind capabilities`; `/health` wired via shared `resource_snapshot()` (GPU/network off the poll path).
9. ✅ Tests: `test_dind_preferences.py`, `test_dind_capabilities.py` (network-hermetic), `test_dind_health.py` extended.
10. ✅ `pytest` clean (213) → PR #32 title+body updated → pushed (`99f060b`) → progress commented in #50.

**Wrap-up — done:**
11. ✅ Both branches synced to `develop`; full runnable suite green on `feat/din-daemon`.
12. ✅ Part B follow-up comment posted in #50.

**What's left for `task_220726_7`:** review feedback only. The next *task* (separate) is the
wallet/session/tx keystone — see the ⏭️ item in the status block.

### Definition of done (from task Deliverables)
- [x] `sdk/state.py` extracted + shim; `sdk/serialize.py` implements every §3 rule
- [x] New SDK tests; boundary test covers both new modules; suite green, no CLI behavior change
- [x] PR #31 body updated with the slice covered; wallet/session/tx flagged as deferred next slice (comment in #50)
- [x] `dind preferences show/set` + `dind capabilities`; `/health` `resources` extended
- [x] New daemon tests; `dind` suite green
- [x] `pytest` clean on **both** branches (runnable unit suites; contract-integration + torch suites env-gated)
- [x] PR #32 body updated with the slice covered
