# Plans/CLAUDE.md — personal, fork-only

Santiago's working rules for this clone of DevNet. They supplement the team's root `CLAUDE.md`, which
comes from upstream and **must not be edited** (it was written by Umer). This file lives on the `plans`
branch and reaches Claude through the root `CLAUDE.local.md`, which contains a single `@Plans/CLAUDE.md`
import line and is excluded locally (see "Fresh clone" below).

## What `Plans/` is

- A `git worktree` on **`plans`**, an orphan branch with no history in common with `develop` or any
  feature branch. It is pushed to `origin` (`Santiagocetran/DevNet`) only.
- **Never** push `plans` to `upstream`, merge it, rebase onto it, cherry-pick from it, or cut a branch
  from it. Plan content must never appear in an upstream PR diff.
- The main checkout ignores the folder through `.git/info/exclude` (`Plans/`), **not** `.gitignore`,
  because `.gitignore` is a team-owned tracked file. The same goes for `CLAUDE.local.md`.
- **Fork-only is not the same as private.** Anything that shouldn't be public stays out of `Plans/`
  unless the fork is private.

## Working in it

- Run Git commands for plan files from **inside `Plans/`**. From the DevNet root, Git operates on the
  code branch, and `Plans/` is invisible to it.
- Commit and push after every meaningful plan revision:
  `cd Plans && git add -A && git commit -m "..." && git push`. The other machine syncs with
  `cd Plans && git pull`. An unpushed revision exists on one machine only.
- Commit messages follow the repo style (`docs(plans): ...`, `chore(plans): ...`).

## Plan documents

- **Name:** `<series>-<NN>-<topic>-plan.md` (for example `ci-next-02-lint-promotion-plan.md`). Put
  post-implementation write-ups in a sibling `-summary.md`.
- **Header block:** `**Base:**` (branch and SHA the plan was measured against), `**Branch:**`,
  `**Origin:**` (what spawned it, cited by path and section), `**Status:**` (`rev N` plus a one-line
  verdict).
- **Revisions:** every revision after rev 1 opens with a `Rev N changelog` quote block. List what was
  wrong, how it was confirmed against the tree, and what changed. Label blocking defects **BLOCKER**.
- Numbers and claims about the code must be measured against the stated Base. If a tool wasn't
  available, say so explicitly ("unmeasured, re-measure before opening").

## Archiving

`ARCHIVE.md` is the index and holds the rules (its §5). In short:
- Archive only files that are completed, superseded, or tracked elsewhere.
- Carry unfinished scope into a named successor plan before archiving.
- `git mv` the file and add the dated reason row to `ARCHIVE.md` in the same commit.
- Run the reference sweep from `ARCHIVE.md` §2 afterwards.
- Keep the "Active plans" table in `ARCHIVE.md` in sync when a plan is added, revised, or shipped.

## Fresh clone / new machine

Worktree metadata and `.git/info/exclude` are local and don't travel with a clone:

```bash
git fetch origin plans
git worktree add Plans plans
printf 'Plans/\nCLAUDE.local.md\n' >> .git/info/exclude
printf '@Plans/CLAUDE.md\n' > CLAUDE.local.md
```
