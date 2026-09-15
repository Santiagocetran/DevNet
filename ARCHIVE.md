# `Plans/` archive index

`Plans/` is **not tracked by Git** — it is excluded locally via `.git/info/exclude`, and
`git log --all -- Plans` is empty. Nothing in this folder has ever been committed, on any ref.

That has a consequence worth stating plainly: **moves, deletions and the reasoning behind them leave
no trace anywhere else.** There is no `git log` to reconstruct why a file went to `archive/`. This
file is the substitute. Anything moved into `archive/` gets a row here, with the date and the reason,
at the time of the move — otherwise the archive decays into a folder nobody trusts.

**Archive status means one of three things:** completed, superseded, or tracked elsewhere. A document
holding live, untracked findings does **not** qualify — see §3.

---

## 1. Active plans

| File | Covers | Status |
|---|---|---|
| `ci-next-01-dependabot-plan.md` | Dependabot on `main`, targeting `develop` | rev 2 — ready |
| `ci-next-02-lint-promotion-plan.md` | `ruff` config + cleanup + promotion (Phase 1 PR 3) | rev 2 — ready |
| `ci-next-03-timestamp-escalation-plan.md` | BL-25 + issue for the OP-Stack timestamp question | rev 2 — ready |
| `ci-next-04-forge-fmt-plan.md` | `forge fmt` + `--check` step (Phase 1 PR 4) | rev 1 — ready |

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
grep -rn 'Plans/[A-Za-z0-9_.-]*\.\(md\|sol\)' Plans/archive/ | grep -v 'Plans/archive/'
```

Expected output: empty.

---

## 3. Archived files that still contain live findings

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

## 4. Rules for the next move

1. Add the row here, with the date and the reason, in the same change as the `mv`.
2. Run the reference sweep in §2 and repair anything it finds.
3. Confirm the file is genuinely completed, superseded, or tracked elsewhere. If it holds a live
   finding, file the backlog row or issue **first** and link it — then archive.
4. If a document's scope is only partly done, carry the remainder into a named successor plan (as PRs
   3 and 4 were) or record explicitly that it is cancelled and why. Do not archive unclaimed scope.
