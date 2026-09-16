# Private key fixes

← [Back to the meeting overview](README.md)

**Checklist item:** P3-T0.2b (keystore security) · **Facts checked against:** `develop` @ `5d258e0` (16 Sep 2026)
**Security reviewer named in the roadmap:** Umer

> **Revision 2 changes:**
> - These are "two confirmed defects", not "all that's left".
> - The data-distribution helper is now explicitly in scope.
> - Added acceptance checks and a proposed policy for every way to bring a key in.
> - Added a gap in the migration guide.
> - The reviewer is now Umer, as the roadmap says.
> - "Closed" is no longer claimed.

---

## Where key safety stands

**Built and merged (since July):** for real use (not demo mode), keys are stored **locked with a
password** (an encrypted keystore). The tool asks for the password when it needs it. The guides
warn in several places that keeping keys in a text file is for local development only.

**What this document covers:** two **confirmed defects** we found while checking. Fixing them is
worthwhile, but it **doesn't mean key safety is finished**. The last section lists what still needs
checking before anyone calls T0.2b's key half done.

---

## Defect 1: the tool still reads an unprotected key in real mode

### What happens

When you register a wallet, `--account 3` picks an account by number.

- **In demo mode**, it picks a built-in test account. That's fine.
- **In real mode**, it reads the key from a **plain text file** (`.env`, as `ETH_PRIVATE_KEY_3`).

The tool then saves the key locked, **but the unprotected copy stays in the text file**, and the
help text presents this route as normal.

**The same thing happens in a second place:** the command that hands out demo training data to
clients reads the same plain-text keys in real mode.

### Where

- [`dincli/cli/system.py:529`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/dincli/cli/system.py#L529): wallet registration
- [`dincli/cli/system.py:1261`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/dincli/cli/system.py#L1261): `dataset distribute-mnist`

### Why it matters

It keeps a real operator's key in a plain file, which is easy to copy, back up or share by
accident. A leaked key stays leaked, whichever network it was used on.

### Proposed fix

- In both places, **allow account-by-number only in demo mode**.
- In real mode, **stop before reading anything**, and show a friendly message pointing to the
  hidden prompt or keystore import, with a link to the wallet guide.
- Update the help text and `Documentation/public/cli-reference.md` to match.

---

## Defect 2: the setup file points to a guide that isn't there

`.env.example` tells operators to see `Documentation/guides/wallet-setup.md`. The guide is actually
at `Documentation/public/guides/wallet-setup.md`. It's the exact moment someone is about to do the
unsafe thing, and the link leads nowhere.

- **Where:** [`.env.example:13`](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/.env.example#L13)
- **Fix:** correct the path.

---

## How we'll know the fix works (acceptance checks)

| Check | Expected result |
|---|---|
| Demo mode: `register-wallet --account N` | Still works as before |
| Real mode: `register-wallet --account N` | Stops with the friendly message, **before** reading any key from the environment (a test proves the value is never read) |
| Real mode: `dataset distribute-mnist` with clients | Same rule, or a documented exception agreed with Umer |
| Real mode: hidden prompt | Still works |
| Real mode: `--keystore` import | Still works |
| Help text, CLI reference and `.env.example` | All point to the same, existing wallet guide |
| Existing test suite | Still passes |

---

## Proposed policy for every way to bring a key in

The tool accepts keys several ways. The fix only changes one, but the policy should be written
down so reviewers know what's intended:

| Route | Today | Proposal for real use |
|---|---|---|
| Hidden prompt | Allowed | **Recommended** |
| Import an encrypted keystore file | Allowed | **Recommended** |
| Key in a file (`--key-file`) | Allowed | Allowed as a **one-time migration** route. Tell people to delete the file afterwards. |
| Key typed in the command itself | Allowed, with a warning about shell history | Keep the warning, or demo-only. **Umer to decide.** |
| `--account N` from `.env` | Allowed | **Demo mode only** (this fix) |

---

## A gap this fix doesn't cover

Blocking a route **doesn't remove copies people already have.** The
[migration guide](https://github.com/InfiniteZeroFoundation/DevNet/blob/5d258e0/Documentation/public/guides/keystore-migration.md)
explains how to move a key into an encrypted keystore, and it tells you to delete the temporary
keystore file. **I found no step telling people to remove the old `ETH_PRIVATE_KEY_…` lines from
their `.env`.**

**Proposal:** add that step to the same PR.

**The same guide also contradicts itself about the passphrase.** It says the passphrase is "never
stored on disk", but a few lines earlier it tells people to put `DIN_WALLET_PASSWORD` in `.env`.
Details are in the [docs inventory](04-operator-docs-inventory.md#contradictions-found-in-existing-guides).
**Proposal:** fix that wording in the same PR.

---

## Before calling the key half of T0.2b done

The roadmap asks for three things. The fixes above help, but these still need a check by the
security reviewer:

1. **"Audit all `.env.example` and docs for plaintext key patterns."** The defects above came from
   spot checks, not a full audit. Do one full pass and record what was checked.
2. **"Never write the decrypted key to disk or environment."** This should be confirmed by review,
   including in the daemon once it merges (the daemon has its own password handling).
3. **"Document migration."** Mostly done; add the `.env` clean-up step above.

---

## Plan

| Step | What | Who | When |
|---|---|---|---|
| 1 | One PR to `develop`: both defects, the migration-guide `.env` clean-up step, the passphrase wording fix, and tests for the checks above | Santiago | Target Thu 17 Sep. If not ready, open an issue instead and link it here. |
| 2 | Security review | Umer (per roadmap) | After PR opens |
| 3 | Full pass over docs and `.env.example` for plaintext key patterns | Santiago, reviewed by Umer | Proposed: by 25 Sep |
| 4 | Merge the PR into `develop` | Reviewer | After step 2 approves |
| 5 | Run the acceptance checks above **on the merged `develop` commit**, and record the commit and results | Santiago | After step 4 |
| 6 | Review of decrypted-key handling: confirm the decrypted key never lands on disk or in the environment, in the CLI and in the daemon once merged | Umer (security reviewer) | Proposed: before the checklist review |
| 7 | Mark the key half of T0.2b **proven** | Checklist owner | Only when steps 3, 5 and 6 are all complete |

These fixes go straight into `develop` and don't depend on the daemon PRs.

**PR / issue:** *proposed; not opened yet*. Replace this line with the link once it exists.

---

## What to say on Friday

> "The encrypted keystore has been live since July. While checking, I confirmed two defects: real
> mode still reads plain-text keys from `.env` in two commands, and a setup file points to the wrong
> guide. There's a small fix with clear checks, for Umer to review. That doesn't finish key safety.
> We still need a full pass over docs for plain-text key patterns, and a check that decrypted keys
> never land on disk."
