# `Plans/` archive index

`Plans/` is a `git worktree` on the orphan branch **`plans`**, pushed to `origin` (the
`Santiagocetran/DevNet` fork) only — never `upstream`, never merged into anything. Working rules
for the branch itself are in [`CLAUDE.md`](CLAUDE.md). Until 2026-09-15 this folder was untracked
and nothing in it had been committed; `plans` starts at `ee0fdc7` with the tree as it stood then, so
**history before that commit exists only in this file.**

Git now records *that* a file moved. It does not record *why*, or whether the move was honest — and
that is what decays. So this file stays the index: anything moved into `archive/` gets a row here,
with the date and the reason, **in the same commit as the `mv`** — otherwise the archive decays into
a folder nobody trusts.

**Archive status means one of three things:** completed, superseded, or tracked elsewhere. A document
holding live, untracked findings does **not** qualify — see §4.

---

## 1. Active plans

| File | Covers | Status |
|---|---|---|
| `ci-next-01-dependabot-plan.md` | Dependabot on `main`, targeting `develop` | rev 2 — ready |
| `ci-next-02-lint-promotion-plan.md` | `ruff` config + cleanup + promotion (Phase 1 PR 3) | rev 2 — ready |
| `ci-next-03-timestamp-escalation-plan.md` | BL-25 + issue for the OP-Stack timestamp question | rev 2 — ready |
| `ci-next-04-forge-fmt-plan.md` | `forge fmt` + `--check` step (Phase 1 PR 4) | rev 1 — ready |
| `testnet-readiness/` | Prep packet for the 2026-09-18 testnet-readiness meeting (discussion #132): overview, node software status, hardware measurement plan, key fixes, docs inventory, audit | rev 2 + review corrections — ready for the meeting |

Phase 1 of the CI series (`archive/ci-cd-phase1-plan.md`) defined four PRs. PRs 1 and 2 shipped as
#103 and #118. **PR 3 is `ci-next-02`, PR 4 is `ci-next-04`** — both were carried forward rather than
cancelled, so the archived Phase 1 plan has no remaining unclaimed scope.

---

## 2. Moves made 2026-09-15

| File | Reason |
|---|---|
| `ci-cd-phase1-plan.md` | PRs 1–2 shipped (#103, #118). Remaining scope carried forward in full: PR 3 → `ci-next-02`, PR 4 → `ci-next-04`. Still the authoritative record of the design reasoning; both successors cite it by section. |
| `discussion-74-revised-proposal.md` | The proposal that became discussion #74. Superseded by what actually shipped. |
| `slashing-invariants-fix-plan.md` | Merged as PR #117 (2026-09-10). |
| `slashing-invariants-verified-reference.t.sol` | Companion reference to the above. |
| `pr31-32-followups-and-develop-sync-plan.md` | The `develop`-sync half is done. Written against heads `036828e` / `f69ab8d`; those branches are now at `dc83f92` / `8c20047`. The still-open PR #31/#32 hardening is superseded by `Developer/tasks/task_110926_14.md` and `task_110926_15.md`, which were re-verified against current heads on 2026-09-11. **Judgement call** — reversible with one `mv` if the older context is still wanted. |

### Reference repair

Archiving broke 17 relative references of the form `Plans/<file>.md` across 12 archived documents —
they pointed at top-level paths that no longer existed. All 17 were rewritten to `Plans/archive/<file>`
on 2026-09-15 and verified to resolve. **Any future move must do the same sweep**, or the archive
turns into a pile of dead links:

```bash
# from the DevNet root: every Plans/<file> reference anywhere, resolved against disk
grep -rnoI --exclude-dir={.git,.venv,node_modules,lib} 'Plans/[A-Za-z0-9_./-]*\.\(md\|sol\)' . \
  | while IFS=: read -r src line ref; do [ -e "$ref" ] || echo "$src:$line  $ref"; done
```

Expected output: empty. The sweep covers the whole working tree, not just `archive/`. On 2026-09-15
it only scanned `Plans/archive/`, and that missed the six dead references in the root-level
`AUDIT_HANDOFF.md` (fixed on 2026-09-16, §3).

---

## 3. Moves made 2026-09-16

| File | Reason |
|---|---|
| `AUDIT_HANDOFF.md` | Was at the repo root, untracked (in `.git/info/exclude`), dated 2026-07-03. A handoff brief for a fresh audit of `task_300626_3` on `feat/validator-readiness`; it said of itself "delete … once the audit is done". Completed: Part 1 merged to `develop` via PR #16 (`dc6ff23`, `c12b9e1`). Its one substantive finding, Lighthouse retrieval returning HTTP 402, is tracked elsewhere, in `Developer/discussion/add-filecoin-support.md` (marked superseded, `70fef30`) and `Developer/tasks/task_060726_4.md`. Archived instead of deleted, because it had never been committed and deleting it would have lost it for good. Its six `Plans/<file>` references were rewritten to `Plans/archive/<file>`, and its `.git/info/exclude` entry was removed. |

---

## 4. Archived files that still contain live findings

**`archive/followups-tracking-note.md`** — archived before 2026-09-15 (dated 2026-08-01), not part of
that day's moves, but it does not meet the archive bar and should be resolved:

- **§1, `sdk/ipfs.py`'s mislabeled `TODO(sdk-keystones)`** — three `raise` swaps from bare
  `RuntimeError` to the already-existing `IpfsError`. Consequence is real: `dind` keys retries off the
  stable `.code`, and a failed IPFS upload currently raises without one. **Not tracked in
  `BACK_LOG.md` under any BL number.**
- **`save_din_info()` writes the packaged config**, so a local deploy dirties a tracked repo file and
  shows up in `git status`. `XDG_CONFIG_HOME` isolation does not cover it. **Also untracked.**
- The note's own `BL-10` / `BL-11` numbering is **stale** — those findings were filed in the real
  backlog as **BL-19** and **BL-20**. Anyone reading the note cold will cite the wrong IDs.

**Action before this file can honestly stay archived:** open backlog rows (or issues) for the two
untracked findings, correct the stale BL numbers, and add the links. Until then it is "archived" in
location only.

---

## 5. Rules for the next move

1. Use `git mv`, and add the row here with the date and the reason **in the same commit**. Push
   `plans` afterwards — an unpushed move exists on one machine only.
2. Run the reference sweep in §2 and repair anything it finds.
3. Confirm the file is genuinely completed, superseded, or tracked elsewhere. If it holds a live
   finding, file the backlog row or issue **first** and link it — then archive.
4. If a document's scope is only partly done, carry the remainder into a named successor plan (as PRs
   3 and 4 were) or record explicitly that it is cancelled and why. Do not archive unclaimed scope.
