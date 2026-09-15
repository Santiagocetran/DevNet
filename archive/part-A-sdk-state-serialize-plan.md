# Part A Implementation Plan — `sdk/state.py` + `sdk/serialize.py`

**Task:** `task_220726_7` Part A (Issue #20, P4-1.2) · **Branch:** `feat/din-sdk` (local `0a6e207`, synced to `develop`)
**Depends on:** nothing (Part A code paths — `dincli/sdk/`, the `utils.py` converters — untouched by the 2026-07-23 develop merge; that merge only added docs/tasks/design files + unrelated CLI work)
**Companion docs:** `Plans/archive/current-state-and-next-task.md` (state + scope), proposal §3/§4/§8
**Scope reminder:** additive only — **no change to existing CLI behavior/output** (boundary #5). No wallet/session/tx.

---

## 0. Anchors (verified post-merge, 2026-07-23)

| Thing | Location |
|---|---|
| Converters to extract | `dincli/cli/utils.py` — `GIstateToDes` (385), `GIstateToStr` (393), `GIstatestrToIndex` (405) |
| Backing data | `dincli/cli/utils.py` — `stateDescription` (329), `states` (355), `GIstate_to_index` (382) |
| Converter call sites (all import from `dincli.cli.utils`) | `cli/task.py:8,181` · `cli/modelownerd/gi.py:6` · `cli/context.py:18,463,564,570,571` |
| Data call sites outside utils.py | **none** (grep-confirmed) |
| GI-state guards to rewire | `cli/context.py:563` `validate_GIstate_ET_given_GIstate`, `569` `validate_GIstate_LTE_given_GIstate` |
| Shim pattern to mirror | `dincli/services/ipfs.py`, `dincli/services/runtime.py` (prior wave `85ceae7`) |
| Error base + allowlist | `dincli/sdk/errors.py` — `ValidationError(code="validation_failed")`, allowlist keys `{field, expected, actual}` (all `str`) |
| Envelope/serialize spec | proposal §3 (lines 98-142); layout §8 |
| SDK version | `dincli/sdk/__init__.py:15` `__version__ = "0.1.0"` |

`states` entries are all valid Python identifiers (no spaces/hyphens) → usable as `IntEnum` member names.
`stateDescription` entries are human strings (kept only in the description converter).

---

## 1. `dincli/sdk/state.py` (new)

Pure module (stdlib only — keeps the import-boundary green). Three parts:

### 1a. Data + converters — moved **verbatim** from `utils.py`
Move `stateDescription`, `states`, `GIstate_to_index`, and the three functions unchanged (same
bodies, same `UnknownState({n})` fallback, same `KeyError` on unknown string). Behavior must be
byte-identical — existing callers reach them through the shim.

### 1b. `GIState` enum — the "enums" half of §8's "enums/converters"
Add a real enum so `serialize.py` has something to exercise the enum→name rule against (the §3
serialization test hook — task Part A §2 — explicitly says "wrap `state`'s GI-state enum … serializes
to its name string"):

```python
from enum import IntEnum
# member name == states[i], value == i (0-based, matching Solidity enum ordinals)
GIState = IntEnum("GIState", {name: idx for idx, name in enumerate(states)})
```

This is additive representation, **not** a new rule — converters stay the source of truth for callers.

### 1c. `validate_*` predicates — lifted from `context.py`, raising `ValidationError`
Only the two checks that exist today (task: "don't invent new validation rules"). Pure, no
console/typer. Populate `details` with exactly the `validation_failed` allowlist keys:

```python
from dincli.sdk.errors import ValidationError

def validate_gi_state_equals(current: int, expected: str) -> None:
    """Raise ValidationError unless the current GI state's name == expected. (was
    DinContext.validate_GIstate_ET_given_GIstate)"""
    actual = GIstateToStr(current)
    if actual != expected:
        raise ValidationError(
            f"expected GI state {expected!r}, current is {actual!r}",
            details={"field": "gi_state", "expected": expected, "actual": actual},
        )

def validate_gi_state_at_least(current: int, minimum: str) -> None:
    """Raise ValidationError if the current GI state is earlier than `minimum`.
    (state half of DinContext.validate_GIstate_LTE_given_GIstate)"""
    if current < GIstatestrToIndex(minimum):
        raise ValidationError(
            f"GI state must be at least {minimum!r}, current is {GIstateToStr(current)!r}",
            details={"field": "gi_state", "expected": minimum, "actual": GIstateToStr(current)},
        )
```

> Note the `LTE` method also gates on `target_gi == curr_gi` (a GI-*number* comparison, not state).
> That stays in the CLI method — the SDK predicate covers only the state-ordering half it's named for.

### 1d. `utils.py` shim (mirror `services/ipfs.py`)
Delete the moved definitions from `utils.py`; add near the existing `from dincli.sdk.*` block
(~line 30-39):

```python
# GI-state enums/converters moved to dincli.sdk.state (issue #20). Re-exported so existing
# `from dincli.cli.utils import GIstateToDes, ...` call sites keep working. New code: import
# from dincli.sdk.state.
from dincli.sdk.state import (  # noqa: F401
    GIState, GIstateToDes, GIstateToStr, GIstatestrToIndex,
    stateDescription, states, GIstate_to_index,
)
```

No import changes needed in `task.py`/`gi.py`/`context.py` — the shim keeps their imports valid.

---

## 2. `dincli/sdk/serialize.py` (new)

Genuinely new code; correctness bar = proposal §3's rules table. May import `web3` (allowed by the
boundary test — only `typer`/`rich`/`dincli.cli.*` are forbidden) for checksum/hex helpers.

### 2a. Module constants
```python
SCHEMA_VERSION = "din-sdk-envelope/v1"
from dincli.sdk import __version__ as SDK_VERSION
```

### 2b. `to_envelope()` — signature from the task
```python
def to_envelope(data, *, error=None, network=None, chain_id=None, correlation_id=None) -> dict:
    if error is not None:
        status, payload, err = "error", None, error.to_error()   # DinError.to_error() (§3 error shape)
    else:
        status, payload, err = "ok", (None if data is None else _encode_dataclass(data)), None
    meta = {"schema_version": SCHEMA_VERSION, "sdk_version": SDK_VERSION}
    if network is not None:        meta["network"] = network
    if chain_id is not None:       meta["chain_id"] = chain_id
    if correlation_id is not None: meta["correlation_id"] = correlation_id
    return {"status": status, "data": payload, "error": err, "meta": meta}
```

### 2c. Encoder — the rules table
`_encode_dataclass(obj)` iterates `dataclasses.fields(obj)`, reads `f.metadata.get("json")` for the
metadata-driven kinds, and dispatches the rest by Python type via `_encode_value(v)` (used for nested
values inside lists/dicts where no field metadata exists).

| Rule (proposal §3) | Trigger | Output |
|---|---|---|
| uint256 → decimal string | `metadata={"json":"uint256_string"}` | `str(int(v))` |
| omit | `metadata={"json":"omit"}` | field dropped entirely |
| address → checksummed | `metadata={"json":"address"}` | `Web3.to_checksum_address(v)` |
| small int passthrough | plain `int`/`bool`, no metadata | JSON number as-is |
| bytes/HexBytes → hex | `isinstance(v,(bytes,bytearray))` — `HexBytes` **is** a `bytes` subclass so this catches it; `Web3.to_hex` accepts both | `Web3.to_hex(v)` (0x-prefixed) |
| enum → name | `isinstance(v, enum.Enum)` | `v.name` |
| Decimal → string | `isinstance(v, Decimal)` | `str(v)` |
| nested dataclass / list / dict | recursion | recurse element-wise |
| `None` | value is None | `null` (kept, unless field tagged `omit`) |

Design decisions worth noting in the PR:
- **Address is metadata-driven** (`"address"` tag), not auto-detected from string shape — auto-detecting
  "looks like 40 hex chars" would mis-checksum non-address hex. Explicit tag = no false positives.
- **`Web3.to_hex`** (not `HexBytes.hex()`) for bytes — `.hex()`'s `0x` prefix is version-dependent;
  `to_hex` is always `0x`-prefixed, matching the rule.
- Order inside `_encode_dataclass`: check `omit` → check explicit `json` kind → else `_encode_value`.

---

## 3. Tests

### 3a. `tests/test_sdk_state.py` (new)
- **Converter snapshot (behavior unchanged):** for every `i in range(len(states))`:
  `GIstateToStr(i) == states[i]`, `GIstateToDes(i) == stateDescription[i]`,
  `GIstatestrToIndex(states[i]) == i`. Out-of-range → `"UnknownState(-1)"` / `f"UnknownState({len})"`.
- **Shim parity:** `from dincli.cli.utils import GIstateToStr` is the same object as the sdk one
  (`is` identity) — proves the shim, not a copy.
- **`GIState` enum:** `GIState(i).name == states[i]` and `GIState[states[i]].value == i` for all i.
- **`validate_gi_state_equals`:** passes silently on match; on mismatch raises `ValidationError` with
  `.code == "validation_failed"` and `.details == {"field":"gi_state","expected":…,"actual":…}`.
- **`validate_gi_state_at_least`:** passes when `current >= index(min)` (incl. equal); raises
  `ValidationError` when below.

### 3b. `tests/test_sdk_serialize.py` (new)
Test-only dataclass fixture exercising every rule (one assertion per rule row above), e.g.:
```python
@dataclass
class _Fix:
    gi: int                                                     # small-int passthrough
    fee_wei: int = field(metadata={"json": "uint256_string"})   # → "…"
    owner: str = field(metadata={"json": "address"})            # → checksummed
    blob: bytes = b"\x00\xab"                                   # → "0x00ab"
    price: Decimal = Decimal("1.5")                             # → "1.5"
    raw: object = field(default=None, metadata={"json": "omit"})# dropped
```
- One test per encoder rule (uint256 stringification, omit, small-int passthrough, bytes→hex,
  checksummed address, enum→name, Decimal→string).
- **Real enum rule:** wrap `GIState.LMSstarted` in a trivial dataclass → serializes to `"LMSstarted"`.
- **Envelope success round-trip:** `to_envelope(fixture, network="…", chain_id=…)` → `status=="ok"`,
  `data` populated, `error is None`, `meta` has `schema_version`/`sdk_version` (+ network/chain_id).
- **Envelope error round-trip:** `to_envelope(None, error=ValidationError("x", details={...}))` →
  `status=="error"`, `data is None`, `error["code"]=="validation_failed"`, details carried through.
  *Do not* re-test `sanitize_details` internals (already covered in `test_sdk_boundary.py`).

### 3c. `tests/test_sdk_boundary.py` (extend)
`walk_packages` already auto-imports new modules, so the clean-import guarantee covers them for free.
Add an explicit belt-and-suspenders assertion that both landed:
`assert {"dincli.sdk.state", "dincli.sdk.serialize"} <= loaded` inside the subprocess script.

---

## 4. CLI rewiring — `context.py` (output-preserving)

Rewire the two guards to delegate the *decision* to the SDK predicates while keeping **identical**
console output + `typer.Exit(1)` (boundary #5). Shape:

```python
def validate_GIstate_ET_given_GIstate(self, curr_GIstate, given_GIstate, msg) -> bool:
    from dincli.sdk.state import validate_gi_state_equals
    from dincli.sdk.errors import ValidationError
    try:
        validate_gi_state_equals(curr_GIstate, given_GIstate)
    except ValidationError:
        self.console.print(f"[bold red]✗ {msg}. Current state: {GIstateToStr(curr_GIstate)} [/bold red]")
        raise typer.Exit(1)
    return True
```

`validate_GIstate_LTE_given_GIstate` keeps its `if target_gi == curr_gi:` gate and calls
`validate_gi_state_at_least(curr_GIstate, given_GIstate)` inside it, same except/print/exit tail.

> This is the one place touching CLI code. Mitigation: the branch's existing CLI tests plus a manual
> check that a wrong-state invocation still prints the same red line and exits 1. If delegation proves
> to risk any output drift, fall back to leaving the methods inline and shipping the predicates as
> the SDK surface only — the predicates existing + tested is the load-bearing deliverable.

---

## 5. Sequence (small, independently-verifiable commits)

1. **Create `sdk/state.py`** (data + converters verbatim + `GIState`), no shim yet; add `test_sdk_state.py`
   converter/enum tests → run them green.
2. **Shim `utils.py`** (delete moved defs, add re-export); run full unit suite → converters still work
   via shim across `task.py`/`gi.py`/`context.py`.
3. **Add predicates** to `state.py` + their tests.
4. **Rewire `context.py`** two methods; verify wrong-state path output unchanged.
5. **Create `sdk/serialize.py`** + `test_sdk_serialize.py` (all rules + both envelope paths).
6. **Extend `test_sdk_boundary.py`**; run the boundary subprocess check.
7. **Full unit suite green**; update PR #31 body noting the slice; push (push = PR update — do with a
   green suite, per convention).

Run each step with `pytest` however this repo is normally invoked (`pytest …` per CLAUDE.md, or
`python -m pytest …`). In this local environment the interpreter lives in a `.venv` and `pytest`
isn't on `PATH`, so activate it first — adjust if your setup differs:
```bash
source .venv/bin/activate          # local-env specific; skip if pytest is already on PATH
python -m pytest -q tests/test_sdk_state.py tests/test_sdk_serialize.py tests/test_sdk_boundary.py \
  tests/test_connect_wallet.py tests/test_dintoken.py tests/test_ipfs_config.py \
  tests/test_sdk_config.py tests/test_sdk_manifest.py tests/test_sdk_web3.py
```
(The `tests/dincli/*` integration suite needs the hardhat/npm compile harness, and
`test_cache_client_dp.py` needs `torch` — both unavailable in this env, both pre-existing, neither
touched by Part A.)

---

## 6. Risks / watch-items

- **Output drift in `context.py`** — the only CLI-touching change. Covered by §4 mitigation + fallback.
- **`GIState` member names** — must equal `states[i]` exactly and values must be 0-based (use the dict
  form, *not* the auto-numbering functional API which starts at 1). Asserted in tests.
- **Encoder scope creep** — implement exactly the 8 rules; don't force envelopes onto
  `manifest.py`/`contracts.py` outputs (that's `operations/`, out of scope, boundary #3).
- **web3 import in `serialize.py`** — allowed by the boundary test; confirmed `web3` is already an SDK
  dependency (`sdk/web3.py`, `sdk/config.py`). The boundary subprocess check will catch any regression.

---

## 7. Definition of done (Part A slice of the task Deliverables)
- [ ] `sdk/state.py`: data + 3 converters (verbatim) + `GIState` + 2 `validate_*` predicates
- [ ] `utils.py` reduced to a re-export shim; `task.py`/`gi.py`/`context.py` unchanged in behavior
- [ ] `sdk/serialize.py`: `to_envelope()` + encoder implementing every §3 rule
- [ ] `context.py` guards delegate to SDK predicates, output/exit identical
- [ ] `test_sdk_state.py`, `test_sdk_serialize.py` added; `test_sdk_boundary.py` covers both modules
- [ ] Unit suite green; no CLI behavior/output change
- [ ] PR #31 body updated with the slice; wallet/session/tx flagged as the deferred next task
