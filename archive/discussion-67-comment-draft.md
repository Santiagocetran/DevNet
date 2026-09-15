# DRAFT — Discussion #67 comment (for Santiago to review and post)

---

`task_300726_8` is implemented — PR [#31](https://github.com/InfiniteZeroFoundation/DevNet/pull/31)
updated (`036828e`), [#32](https://github.com/InfiniteZeroFoundation/DevNet/pull/32) synced
(`f69ab8d`). Both still drafts. Full detail in the PR body; summary and open questions here.

## Delivered

`sdk/session.py` (`DinSession` + `SignerProvider`), `sdk/wallet.py`, `sdk/tx.py`
(`send()` / `decode_events()` / `NonceManager`), and `cli/signer.py` — the CLI adapter from §2's
two-adapter design. **BL-1 fixed**, and all four §5b open questions have documented decisions —
with the replacement flow intentionally remaining caller-driven rather than gaining a dedicated
implementation.

247 tests on `feat/din-sdk`, 316 on `feat/din-daemon`.

## Three things worth your attention

**1. I found four defects in my own first pass and fixed them before asking you to look.** The
implementation matched the design but could not complete a transaction on a real chain: it
broadcast fine, then failed while waiting for confirmation. The polling loop tested
`get_transaction_receipt(...) is not None`, but web3 *raises* `TransactionNotFound` for an unmined
tx and never returns `None`. Separately, the session resolved the wallet from the
`--wallet` flag only, so a wallet configured via `DIN_WALLET_NAME` or config `wallet_name` was
displayed while the default key signed.

Root cause of the second one is worth recording: **§1c/§4a's CLI signer adapter was never built**
in the first pass, which left `DinContext` and `DinSession` resolving accounts through two
independent paths that disagreed. Building it fixed the wrong-signer bug and the double keystore decrypt together.

The lesson matches your PR #32 review instinct about tests that assert their own assumptions — the
original mocks encoded `get_transaction_receipt` returning `None`, a web3 contract that does not
exist, so the suite validated the bug. I've corrected those mocks and added regression tests written
to fail at the pre-fix commit first.

**2. One decision I'd like you to sanity-check.** On an *unclassified* broadcast failure (socket
timeout, dropped connection), I now report `broadcast=True` rather than `False`. The reasoning: the tx
may have reached the node, and §10 uses that flag to choose between "safe to rebuild" and "must
confirm, don't resend". On an unknown outcome, `False` risks a double-send while `True` costs a
confirmation lookup. Conservative by design, but it's a behaviour choice on a money-moving path, so
say if you'd rather it stayed optimistic.

**3. Half the golden parity check did not run.** The deploy call site passed — same command against
`4ab0114` and HEAD on a real anvil chain, output and exit code identical after normalizing hashes and
addresses. The **registry-write** case (`process_receipt`) I could not reach without standing up the
full registration flow, so the failure-path `error_msg` formatting is unit-tested but not
live-verified. Not claiming that one as done.

## Questions / spec notes

1. **Daemon adapter location.** The task file says the adapter "lives in `dincli/dind/`", but the
   base-branch note says `feat/din-daemon` gets no changes. I went with a documented contract plus
   reference implementations under `tests/`, and no daemon code. Confirm that was the intent.
2. **`send-eth` is a second signing path the task file doesn't mention.** `send()` structurally cannot
   wrap it — the signature takes a `contract_function` and a value transfer has none. It allocates via
   `get_tx_params()` and now reports to the `NonceManager`. A `tx.send_value()` would unify them, but
   that touches a live money-moving path, so I left it out.
3. **Deliverable line 144** says to post the closing discussion on #50 — that's the previous task's
   closed thread. Posting here and cross-linking; assuming a copy-paste from the prior task file.

## Next slice

`sdk/operations/` + plan/apply (§6) — [`BL-9`](../BACK_LOG.md) — flagged rather than started, same
convention as this task was flagged out of `task_220726_7`. Per your §6 review the priority there is
aggregator/auditor flows first, then `gi.start`, with `register_request`/client/model-owner tooling
lower (BL-4/BL-5).
