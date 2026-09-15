# PR 6 — IPFS retrieval: correct endpoint handling, and an opt-in gateway fallback

**Branch:** `fix/ipfs-gateway-retrieval` (off `main` @ `e83c589`, already created)
**Base:** `main`. A behaviourally-equivalent `develop` PR follows (§6).
**Origin:** [discussion #79](https://github.com/InfiniteZeroFoundation/DevNet/discussions/79) finding B11; @umeradl confirmed it and asked for a fix on both branches
**Status:** rev 3 — twice audited. **Implement as opt-in** unless Umer explicitly approves
default-on (§2.1a). No open questions.

> **Rev 2 changelog.** An audit found three high-priority gaps; all were verified against the tree
> and **all hold**. The URL detector failed the config the CLI itself recommends (§2.2). The public
> gateway fallback widens a trust boundary that ends in `torch.load(weights_only=False)`, so it is
> now **opt-in** (§2.1). The `develop` counterpart needs behavioural parity, not a one-line
> POST→GET (§6). Also added: atomic writes (§2.4), strict CID encoding (§2.5), an actionable
> warning message (§2.6), warn-once (§2.6), and D3 scoped down honestly (§2.7).
>
> **Rev 3 changelog.** A second audit found two specification blockers — both were under-definition
> rather than error, and both are now pinned: `{cid}` templates had no defined HTTP method (§2.2),
> and `IPFS_PUBLIC_GATEWAY` had no stated contract for source, precedence, truthiness or malformed
> values (§2.1a). Also tightened: CID validation moves ahead of provider dispatch and uses `py-cid`
> rather than a delimiter blocklist, with **rejection** as the single defined outcome (§2.5); the
> atomic-write lifecycle is spelled out step by step and gains a mocked success test (§2.4); D3 gets
> a smoke test (§2.7); duplicate `arg` handling is defined (§2.2); and the status is now a decision
> rather than a question.

---

## 1. Three defects

The discussion diagnosed this as POST-vs-GET. Real, but **not** what a fresh user hits.

### D1 — `resolve_ipfs_config()` returns the literal string `"None"` — `main` only

`cli/utils.py:91-92` initialises both URLs to `"None"` and only overwrites them when the env var is
set. Every downstream guard is a truthiness check — `services/ipfs.py:167` (retrieve) and `:77`
(**upload**) — and a non-empty string is truthy, so **neither ever fires**. Reproduced:

```
resolve_ipfs_config() -> retrieve='None'
guard fires? False
MissingSchema: Invalid URL 'None/bafybeifvy3ctest': No scheme supplied
RuntimeError: Failed to retrieve CID bafybeifvy3c
```

That `RuntimeError` is verbatim the B11 symptom. The intended "IPFS API retrieve URL missing"
message is dead code. `develop` rewrote this function and is unaffected.

### D2 — POST, path-style — **both branches**

`services/ipfs.py:170` does `requests.post(f"{base}/{cid}")`. Wrong twice: public gateways reject
POST (measured: `GET ipfs.io/ipfs/<cid>` works, `POST` → **405**), and it is not kubo's `?arg=` form
either, so the local-daemon config also fails. The Filebase branch seven lines below already uses
the correct `cat?arg=` form — the two branches of one function disagree.

### D3 — `importlib` is never imported — `main` only

`_load_custom_fn` calls `importlib.util.spec_from_file_location` (`:23`) with no `import importlib`
in `:1-7`. Any `custom` provider raises `NameError`. See §2.7 — fixing this does **not** make
`custom` work.

## 2. Design decisions

### 2.1 The public gateway fallback is **opt-in** — needs Umer's sign-off to change

Rev 1 proposed silently defaulting to `https://ipfs.io/ipfs` when nothing is configured. Withdrawn.

**Why.** Retrieved artifacts are deserialised with `torch.load(..., weights_only=False)` —
`services/auditor.py:24,31`, `services/modelowner.py:47,49,54`, `services/aggregator.py:33`. That is
arbitrary pickle execution on the retrieved bytes. The client never verifies that what came back
actually matches the requested CID, so the gateway is fully trusted. Filebase is a paid,
authenticated service the operator chose; silently adding an unauthenticated public endpoint to that
path is a different risk, and not one to introduce as a side effect of a bug fix.

Rev 1 also proposed `trustless-gateway.link` as an alternative. **It is not a drop-in**: it serves
raw blocks / CAR streams, not a reconstructed UnixFS file, so a 200 there does not mean the bytes
are what `torch.load` expects. Rev 1's live check was measuring the wrong thing.

**Resolution for this PR:**

- Support the fallback, but **off by default**, enabled by setting `IPFS_PUBLIC_GATEWAY` (either to
  `1` for the built-in default, or to a gateway base URL).
- When it is off and nothing is configured, fail with an **actionable** message (§2.6) instead of
  today's `MissingSchema` confusion. That alone converts B11 from "inscrutable error" to "here is
  what to set", which is most of its practical cost.
- Document the trust assumption at the point of use: reads come from an unverified third party and
  land in a pickle deserialiser.

**Ask Umer** whether he wants it on by default. That is a maintainer policy call about the project's
trust boundary, not a bug-fix decision. Proper CID verification — fetching a CAR and validating the
DAG locally — would remove the objection, but it is far larger than this PR and belongs on its own.

### 2.1a `IPFS_PUBLIC_GATEWAY` — exact contract

Under-specified in rev 2. Two implementations could both "satisfy" it and disagree. Pin it down:

| Aspect | Contract |
|---|---|
| Source | `get_env_key("IPFS_PUBLIC_GATEWAY", None, verbose=False)` — process env then `.env`, matching every other setting |
| Precedence | `IPFS_API_URL_RETRIEVE` **always wins**. The fallback is consulted only when it is unset |
| Normalisation | Strip surrounding whitespace before interpreting |
| Disabled | Unset, `""`, `0`, `false`, `no` (case-insensitive) |
| Built-in default | `1`, `true`, `yes` (case-insensitive) → `https://ipfs.io/ipfs` — a module constant, `DEFAULT_PUBLIC_GATEWAY` |
| Explicit gateway | Any other value must be an absolute `http`/`https` path-gateway base URL |
| Rejected | Missing/other scheme, embedded credentials (`user:pass@`), a fragment, or an empty host — raise a clear config error rather than silently falling back |

Tests cover each row, including a malformed value producing a config error and not a silent
default.

### 2.2 The URL builder must parse, not substring-match

Rev 1 proposed `if "/api/v0/" in base`. That **fails the config the CLI itself recommends**:
`system.py:546` prints `IPFS_API_URL_RETRIEVE=http://localhost:5001/api/v0` — no trailing slash, so
the check misses and it would issue `GET http://localhost:5001/api/v0/<cid>`.

Parse the URL and support these forms explicitly:

| Configured value | Request |
|---|---|
| `…/api/v0` | `POST …/api/v0/cat?arg=<cid>` |
| `…/api/v0/cat` or `…/api/v0/cat/` | `POST …/api/v0/cat?arg=<cid>` |
| `…/api/v0/cat?arg=` | append the encoded CID to the existing query |
| `…/ipfs` or `…/ipfs/` | `GET …/ipfs/<cid>` |
| anything containing `{cid}` | substitute the encoded CID; **method per the rule below** |
| any other host/path | `GET {base}/<cid>` — last-resort gateway assumption, documented |

**Template method selection.** A `{cid}` template does not imply a verb — both of these are
plausible and they need different methods:

```
https://gateway.example/ipfs/{cid}          -> GET
http://localhost:5001/api/v0/cat?arg={cid}  -> POST
```

Rule: **substitute first, then select the method from the parsed path of the result** — kubo
(`/api/v0` or `/api/v0/cat`) → POST, everything else → GET. One test per template form, so two
independent implementations cannot diverge here.

**Rules:** decide on the parsed `path`, never a raw substring; never emit a double slash; never emit
a second `?`; preserve an existing query when appending.

**Duplicate `arg`:** if the configured URL already has `arg=` empty, fill it. If it already has a
**populated** `arg`, replace it rather than appending a second one — never emit repeated `arg`
parameters.

kubo requires POST with `arg`; gateways use `GET /ipfs/{cid}`. These are different protocols and the
builder is the only place that difference should live.

### 2.3 Fix the sentinel at source

`resolve_ipfs_config()` returns real `None` instead of `"None"`. Verified safe: two consumers, both
in `services/ipfs.py` (`:71`, `:153`), and nothing in the package compares these to the string
`"None"`. This makes the dead guards live on **both** the upload and retrieval paths.

### 2.4 Write downloads atomically

`services/ipfs.py:195` streams straight into the final destination, so a timeout mid-transfer leaves
a **partial file that looks like a complete one**. That matters because callers treat existence as a
cache hit — `cache_manifest` only re-fetches `if update or not manifest_path.exists()`
(`cli/utils.py:508`), the same behaviour that made `--update` necessary in #80's readiness checklist.

Required lifecycle, in this order:

1. `raise_for_status()` **before** creating any temp file.
2. Create the temp file securely in the **destination directory** (same filesystem, so the replace
   is atomic).
3. Stream chunks into it.
4. Close the response in a `finally`, including on stream failure.
5. Replace the destination only after iteration completes.
6. Remove the temp file on **every** failure path.
7. Preserve the function's existing return contract (the response status code).

This refactors the ordinary success path, so it needs a **mocked multi-chunk success test**, not
just a live check — plus assertions that the response was closed and no temp file survives a
failure.

### 2.5 Validate the CID once, before provider dispatch

Two problems with rev 2's wording. It implied validation lived in the URL builder — which would
leave the **Filebase** branch on its existing `quote(hash_value)` and hand **custom** unchecked
input. And a delimiter blocklist still admits junk like `not-a-cid`.

**Validate `hash_value` at the top of `retrieve_from_ipfs`, before any provider branch**, using the
`py-cid` dependency the project already has. Verified behaviour of `cid.make_cid`:

| Input | Result |
|---|---|
| `QmUNLLsPACCz1v…` (v0) | valid |
| `bafkreieq5jui4j…` (v1) | valid |
| `not-a-cid` | `ValueError` |
| `../etc/passwd` | `ValueError` |
| `""` | `ValueError` |

The helper belongs in `dincli/services/cid_utils.py`, which exists precisely so `cli.utils` and
`services.ipfs` can share CID code without a circular import.

Then use `quote(cid, safe="")` for **every** URL including Filebase — `quote`'s default `safe="/"`
leaves slashes intact, which is exactly the injection vector.

**Contract is rejection, not escaping.** Rev 2's "rejected or fully escaped" left two acceptable
behaviours; an invalid CID now raises. Tests assert rejection for `/`, `?`, `#`, `%`, whitespace,
empty, and non-string inputs.

### 2.6 Make the message actionable, and warn once

Rev 1's warning told users to run `dincli system configure-ipfs` — but that command only accepts
`filebase` and `custom` (`system.py:779`), so it is not a route to the node provider. Bad advice.

Message content, for both the fallback notice and the nothing-configured error:

> Set `IPFS_API_URL_ADD` / `IPFS_API_URL_RETRIEVE` for a local node, or configure Filebase with
> `dincli system configure-ipfs --provider filebase`.

And when the fallback *is* enabled: state that reads come from a public, best-effort, **unverified**
gateway and that uploads still require a real provider — an aggregator with no upload capability
fails at T1 submission, which is the expensive moment. **Warn once per process**, not per retrieval;
aggregation loops fetch many CIDs.

### 2.7 D3 is a `NameError` fix, not a working `custom` provider

Adding the import removes the `NameError`, but `custom` still will not work: after
`response = fn(...)` the code unconditionally calls `response.raise_for_status()` and
`response.iter_content(...)` (`:191-197`), so a custom function that writes the file itself and
returns `None` or a status code still breaks. `develop` handles this differently.

Include the one-line import — a `NameError` is strictly worse than a clear failure — but **do not
claim `custom` is fixed**. Defining its return contract is a separate change (§9).

Since it is an independent change, it needs its own verification: a narrow smoke test that
`_load_custom_fn` can load a callable from a temporary module file. Without that, the import fix
ships untested.

## 3. Changes — `main`

| File | Change |
|---|---|
| `dincli/cli/utils.py` | `resolve_ipfs_config()` returns `None`, not `"None"` (§2.3) |
| `dincli/services/ipfs.py` | `import importlib.util` (§2.7); URL builder (§2.2); GET/POST per endpoint kind; opt-in fallback (§2.1); atomic write (§2.4); strict CID encoding (§2.5); warn-once actionable messaging (§2.6) |
| `dincli/services/cid_utils.py` | `validate_cid()` helper (§2.5) — lives here to avoid a circular import |
| `tests/test_ipfs_retrieval.py` | New, force-added (`tests/` is gitignored on `main`; #31 already proposes dropping that) |

The `filebase` and `custom` branches keep their **protocol behaviour** unchanged — but they do sit
downstream of the shared CID validation (§2.5) and atomic write (§2.4), so those paths change too.

## 4. Tests

**URL builder** — one case per row of §2.2's table, plus: trailing slashes, an existing query
string, `http://localhost:5001/api/v0` specifically (the CLI-recommended value rev 1 broke), a
populated `arg=` being **replaced** rather than duplicated, and **both template forms** — a gateway
template resolving to GET and a kubo template resolving to POST (§2.2).

**`IPFS_PUBLIC_GATEWAY` contract** — one case per row of §2.1a: precedence under a set
`IPFS_API_URL_RETRIEVE`, whitespace, each disabled value, each truthy value, an explicit gateway
URL, and a malformed value raising a config error rather than silently defaulting.

**Behaviour** — gateway URL → GET; kubo URL → POST with `arg`; Filebase protocol unchanged; nothing
configured and fallback off → actionable error with **no request attempted**; fallback on → GET plus
exactly **one** warning across repeated calls.

**Sentinel** — `resolve_ipfs_config()` returns `None`; an unconfigured **upload** raises the
intended `IPFS_API_URL_ADD` error rather than a wrapped `MissingSchema`.

**CID validation** — `/`, `?`, `#`, `%`, whitespace, empty, non-string, and plain junk
(`not-a-cid`) are **rejected**; valid v0 and v1 CIDs pass; the rejection happens before any provider
branch, so Filebase and custom are covered too.

**Atomicity** — a **mocked multi-chunk success** writes the complete file and returns the status
code (this refactors the ordinary success path, so it needs direct coverage); a mid-stream exception
leaves no destination file and no leftover temp file; an existing valid file survives a failed
refetch; the response is closed on both paths.

**D3** — a smoke test that `_load_custom_fn` loads a callable from a temporary module file. It is an
independent change and would otherwise ship untested.

**Live** (recorded, not a CI gate) — a real CID through a configured gateway writes bytes that load
correctly; `task gi show-state 0` with the fallback enabled and no provider. Needs a throwaway
wallet, per #83 §4.2. Drop rev 1's recurring `POST → 405` check: it asserts a third party's current
behaviour by deliberately sending an invalid request.

## 5. Diff allowlist

`dincli/cli/utils.py`, `dincli/services/ipfs.py`, `dincli/services/cid_utils.py`,
`tests/test_ipfs_retrieval.py`.

No version state, no `.gitignore`, no `Plans/`, **no docs** — see §7.

## 6. `develop` — behavioural parity, opened right after

Rev 1 said `develop` needs "only D2". **Inconsistent**: `develop` raises when
`IPFS_API_URL_RETRIEVE` is absent, so fixing POST→GET alone still leaves fresh users unable to read.
If the requirement is to fix both branches, both need the same behaviour: gateway GET, kubo POST,
the same fallback policy, the same warning, equivalent tests.

It must be a separate PR — different base branches — but it is **not deferred**: open it once this
one's shape is settled, built on `develop`'s `IPFSConfig` structure rather than porting `main`'s.

## 7. Docs — deliberately not here

`setup.md` §6 on `main` is actively misleading: it tells users to set `IPFS_API_URL_*` and then run
`configure-ipfs --provider custom`, which selects the Python-module provider and demands
`ipfs_service_path`. It does not select the env-backed route at all.

**#80 already rewrites that entire section** (as §7, renumbered), marking the node provider
unselectable and `custom` non-functional. Editing it here would conflict with #80 for no benefit.

So: fix the runtime message (§2.6) so it is correct regardless of merge order, note the dependency
in the PR body, and revise the docs once both land — at which point `setup.md` should also gain the
`IPFS_PUBLIC_GATEWAY` opt-in if Umer wants it.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Gateway response feeds `torch.load(weights_only=False)` | §2.1 — opt-in, documented, and Umer decides the default. CID verification noted as the real fix |
| ipfs.io is explicitly best-effort, not production infrastructure | Runtime message now; documentation via #80 and the §9 follow-up. Opt-in and overridable |
| Fallback masks a missing upload provider until T1 | §2.6 warning states reads-only explicitly |
| Sentinel change alters upload-path behaviour | Intended — a dead guard becomes live. Test covers it |
| Atomic-write refactor touches the success path | Tests for both success and mid-stream failure |

## 9. Follow-ups

- Define the `custom` provider return contract so `custom` actually works (§2.7)
- Make `"ipfs node"` selectable via `configure-ipfs --provider` (`system.py:779` accepts only
  `filebase`/`custom`)
- Backport `--service-path` from `develop`
- Real CID verification (fetch CAR, validate the DAG locally) — would let the fallback be on by
  default without expanding the trust boundary
