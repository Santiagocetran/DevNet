# Node software: honest status and merge plan (PRs #31 and #32)

← [Back to the meeting overview](README.md)

**Facts checked against:** `develop` @ `5d258e0`, `feat/din-sdk` @ `ab1ba24`, `feat/din-daemon` @ `27885d7`.
PR states were read live from GitHub on 16 Sep 2026.

> **Revision 2 changes:**
> - The daemon is described as a framework that doesn't run the node roles yet.
> - Merging no longer closes checklist items. There's now a requirement-by-requirement evidence table.
> - Corrected: the PRs are **not** drafts anymore.
> - The option to skip CLI interruption safety "because of the daemon" was removed.

---

## The short version

- **Built:** a background service (the daemon) that starts, stops cleanly, reports whether it's
  alive and writes logs. There's also a shared foundation (the SDK) under it.
- **Not built yet:** the daemon **doesn't do any node work**. Today it runs only two kinds of job:
  a do-nothing test job and a read-only "check my stake" lookup
  ([`dincli/dind/jobs.py` @ 27885d7](https://github.com/Santiagocetran/DevNet/blob/27885d7/dincli/dind/jobs.py)).
  Training, auditing and aggregating in the daemon are separate roadmap items (P4-4.1, 4.2 and 4.3),
  all still marked **Planned**.
- **So today, operators run the node with the command-line tool** (`dincli client …`,
  `dincli auditor …`, `dincli aggregator …`). Any safety promise for testnet has to cover **that**
  path, or the meeting must explicitly decide otherwise.

---

## What we ask the meeting to decide

1. **What will testnet operators actually run?** Realistically, for the first cohort: the
   command-line tool, inside the provided container setup.
2. **What evidence closes each item?** Use the table below as a starting point.
3. **When should the SDK and daemon be merged?** This is Abraham's call; the question is open in
   [#139](https://github.com/InfiniteZeroFoundation/DevNet/discussions/139#discussioncomment-18402481)
   with no answer from him in the thread yet.
4. **Who reviews #31 and #32?**

---

## Requirement by requirement

The requirements below are quoted in plain words from `Developer/ROADMAP.md` @ `5d258e0`.

The four statuses mean:
- **Built**: the code exists.
- **Reviewed**: someone else checked it.
- **Merged**: it's in the main code.
- **Proven**: tested against the requirement.

### T0.2a: shutting down safely

| What the requirement asks | Where we are | How we'd prove it |
|---|---|---|
| The service stops taking new work and exits cleanly when told to stop | **Built** in the daemon (`dincli/dind/signals.py`). Not merged. | Existing daemon tests, re-run on the merged code |
| Work in progress is saved or clearly marked unfinished, and locks are released | **Not proven.** The daemon has no real jobs to interrupt yet. | Stop the node **during a real training, audit or aggregation job**, restart it, and check nothing is corrupted and the job is marked unfinished |
| Checked under `docker stop` and `docker compose down` | **No record** of this check | Same test as above, run in the container setup |
| Review the command-line tool's long-running steps (starting workers, downloading from IPFS, sending transactions) for "interrupted halfway" damage | **Not done** | A short findings note listing which commands are risky if stopped, and what happens |

The roadmap's notes column says this item is "no use for DIN cli now". **The meeting should
confirm or overturn that explicitly**, since the command-line tool is what operators will run.

### T0.2c: health check

| What the requirement asks | Where we are | How we'd prove it |
|---|---|---|
| Process alive, with the time of the last successful work | **Built.** Reports "degraded" (HTTP 503) when the heartbeat goes stale. | Tests, plus a manual stale-heartbeat check |
| Configuration loaded | **Not built** | Health reports failure when config is missing |
| Blockchain connection (RPC) reachable | **Not built** | Health reports failure when RPC is down |
| Wallet signer available (without exposing the key) | **Not built** | Health reports failure when the wallet can't be unlocked |
| Disk space above a threshold | **Partly built.** It reports free disk but doesn't enforce a threshold. | Health fails below an agreed threshold |
| Docker health check wired in | **Built** in the daemon's compose file. It doesn't auto-restart on "unhealthy", and the file says so. | Documented and tested |

### T0.2d: useful logs

| What the requirement asks | Where we are | How we'd prove it |
|---|---|---|
| JSON logs with time, level, role, network, model, round, job and error code | **Built** for the daemon, including all the fields. Files rotate on disk. | Check real logs with `docker compose logs` |
| Human-readable output kept in interactive command-line use | **Not verified** | Run CLI commands and check the output |
| Works with standard log collectors (no colour codes in JSON) | **Not verified** | Feed logs to a collector or JSON parser |

### T0.2e: starting with the computer, and network isolation

| What the requirement asks | Where we are | How we'd prove it |
|---|---|---|
| Linux (systemd) and Mac (launchd) service files | **Built** as examples: `dincli/dind/examples/dind@.service` and `com.din.dind.plist` | Install on a clean Linux and a clean Mac |
| Network isolation guide: what the node needs (RPC, IPFS), what work containers must not have, suggested firewall rules | **Partly built.** Work containers already run with **no network** (`dincli/cli/worker.py`), and the container README mentions it. There's **no firewall or connection guide.** | A written guide an outsider can follow |

**Takeaway:** the daemon merge moves several rows forward, but **no T0.2 item is fully done just
by merging**. Several rows depend on the command-line path or on work that doesn't exist yet.

---

## The merge itself

### Where each piece goes

| PR | From | Into | State (live, 16 Sep) |
|---|---|---|---|
| [#31](https://github.com/InfiniteZeroFoundation/DevNet/pull/31) SDK | `Santiagocetran:feat/din-sdk` | `feat/din-sdk` | Open, **ready for review** (not a draft) |
| [#32](https://github.com/InfiniteZeroFoundation/DevNet/pull/32) daemon | `Santiagocetran:feat/din-daemon` | `feat/din-sdk` | Open, **ready for review** (not a draft) |
| [#29](https://github.com/InfiniteZeroFoundation/DevNet/pull/29) indexer | `robertocarlous:feat/din-indexer` | `feat/din-indexer` | Open |
| [#72](https://github.com/InfiniteZeroFoundation/DevNet/pull/72) indexer events | `robertocarlous:feat/din-indexer-65` | `feat/din-indexer` | Open |

After that, `feat/din-sdk` and `feat/din-indexer` each need their own merge into `develop`.

**About the indexer:**
- Umer's proposed order is indexer first, then #31, then #32, then everything into `develop`.
- As far as we know, the SDK and daemon **don't need** the indexer to work.
- So the order is a **preference**, not a technical requirement. Ask Umer to confirm that, since it
  decides whether the indexer can hold up our merge.

### What's in the way

1. **The branches have fallen behind.** They last caught up with `develop` on 23 August, and
   `develop` has 121 commits they don't have. A trial merge shows **3 clashing files**:
   `Developer/BACK_LOG.md`, `dincli/cli/context.py` and `dincli/cli/utils.py`.
2. **It's a big review:** 82 files and about 12,850 added lines compared with `develop`.
3. **No up-to-date test results.** The last recorded run was 248 passing on the daemon branch
   ([10 Sep review in #139](https://github.com/InfiniteZeroFoundation/DevNet/discussions/139#discussioncomment-18391160)),
   before the 11 Sep fixes. I couldn't re-run them here because this machine's environment is
   missing the test dependencies. **Test results on each branch alone don't prove the combined code
   works.** The tests that count are the ones on the final merged code.
4. **Nobody has decided the timing** or named a reviewer.

### Steps

| Step | What | Who | Status label it reaches |
|---|---|---|---|
| 1 | Bring both branches up to date with `develop` and fix the 3 clashes | Santiago | — |
| 2 | Re-run all tests; record date, commit, command and counts in the PR bodies | Santiago | — |
| 3 | Decide timing (now, or after P3) | **Abraham**, Friday | — |
| 4 | Name a reviewer and review | Umer / Abraham | **Reviewed** |
| 5 | Merge #31, then #32, into `feat/din-sdk` | Reviewer | — |
| 6 | Merge `feat/din-sdk` into `develop` (after the indexer, if Umer's order holds) | Umer | **Merged** |
| 7 | Re-run the tests **on the merged `develop` commit** | Santiago | — |
| 8 | Run the proof checks from the table above; tick only the rows that pass | Santiago + checklist owner | **Proven** |
