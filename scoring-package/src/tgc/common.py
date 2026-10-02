from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator


def resolve_profile_path(base_dir: Path, value: str | Path) -> Path:
    """Resolve an operational profile path relative to the profile directory.

    ``~`` and environment variables are expanded. Absolute paths remain valid
    for local deployments; relative paths no longer depend on the process CWD.
    """
    expanded = os.path.expandvars(str(value))
    supplied = Path(expanded).expanduser()
    return supplied.resolve() if supplied.is_absolute() else (base_dir / supplied).resolve()


def resolve_within(
    root: Path,
    relative: str | Path,
    *,
    label: str = "path",
    must_exist: bool = False,
) -> Path:
    """Resolve an untrusted relative path while confining it to ``root``.

    Contract manifests and checker bindings are data.  Treating their path
    fields as trusted allowed absolute paths, ``..`` traversal, and symlink
    escapes to address files outside an artifact.  This helper rejects all
    three before any file is opened.
    """
    root_resolved = root.resolve()
    supplied = Path(relative)
    if supplied.is_absolute() or supplied.drive or supplied.root:
        raise ValueError(f"{label} must be relative to {root_resolved}: {relative!s}")
    if any(part in {"", ".", ".."} for part in supplied.parts):
        raise ValueError(f"{label} contains a forbidden path segment: {relative!s}")
    candidate = (root_resolved / supplied).resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as error:
        raise ValueError(
            f"{label} escapes its allowed root {root_resolved}: {relative!s}"
        ) from error
    if must_exist and not candidate.exists():
        raise FileNotFoundError(candidate)
    return candidate


def validate_archive_member(name: str) -> str:
    """Return a normalized safe POSIX archive member name or raise.

    ZIP readers must reject absolute names, drive-like prefixes, backslashes,
    empty components, and ``..`` before extraction or comparison.
    """
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ValueError(f"unsafe archive member name: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe archive member name: {name!r}")
    if path.parts and ":" in path.parts[0]:
        raise ValueError(f"unsafe archive member drive prefix: {name!r}")
    normalized = path.as_posix()
    if normalized != name:
        raise ValueError(f"non-canonical archive member name: {name!r}")
    return normalized


def _fsync_directory(path: Path) -> None:
    """Best-effort durability barrier for an atomic rename's parent directory."""
    flags = getattr(os, "O_RDONLY", 0)
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


V3_CHECKER_INPUT_VERSION = "tgc-checker-input/3.0.0"
V3_CONSENSUS_SEMANTICS_VERSION = "tgc-consensus-semantics/3.4.1"

# One forward-v3 vocabulary boundary, shared by source validation, rendered
# dispatch validation, and release preflight. Labels are stable audit values;
# patterns are deliberately narrow so current terms such as
# ``specificity=family_only`` remain legal while retired payload sentinels do
# not.
RETIRED_FORWARD_SCHEMA_PATTERNS: tuple[tuple[str, str], ...] = (
    ("constructions_json", r"\bconstructions_json\b"),
    ("primary_construction_idx", r"\bprimary_construction_idx\b"),
    ("primary_claim_index", r"\bprimary_claim_index\b"),
    ("primary_idx", r"\bprimary(?:_|\s+)idx\b"),
    ("n_asserted", r"\bn_asserted\b"),
    ("n_rejected", r"\bn_rejected\b"),
    ("n_mentioned", r"\bn_mentioned\b"),
    ("rejection_quote", r"\brejection_quote\b"),
    ("stance", r"\bstance\b"),
    (
        "payload_family_only_sentinel",
        r"\bpayload\s*(?::\s*)?\{\s*[\"']family_only[\"']",
    ),
    (
        "unparseable_payload_sentinel",
        r"\{\s*[\"']unparseable[\"']\s*:\s*true\s*\}",
    ),
)


def retired_forward_schema_hits(text: str) -> tuple[str, ...]:
    """Return retired extraction vocabulary present on a forward-v3 surface."""

    return tuple(
        label
        for label, pattern in RETIRED_FORWARD_SCHEMA_PATTERNS
        if re.search(pattern, text, flags=re.IGNORECASE)
    )


def project_v3_checker_input(
    value: Any,
    *,
    allow_legacy_extras: bool = False,
    legacy_specificity: str | None = None,
) -> dict[str, Any]:
    """Project a v3 claim to the closed mathematical checker-input surface.

    Current-v3 input is exactly ``{kind, payload}``.  Historical early-v3
    records sometimes retained retired CSV-era presentation fields; callers
    may strip those fields only after explicitly authorizing an audited replay.
    """
    if not isinstance(value, dict):
        raise ValueError("v3 checker input must be an object")
    expected_fields = {"kind", "payload"}
    observed_fields = set(value)
    if observed_fields != expected_fields and not allow_legacy_extras:
        raise ValueError(
            "current v3 checker input field surface must be exactly "
            f"{sorted(expected_fields)}; observed {sorted(observed_fields)}"
        )
    allowed_early_v3_fields = {
        "idx",
        "quote",
        "rejection_quote",
        "stance",
    }
    unknown_replay_fields = (
        observed_fields - expected_fields - allowed_early_v3_fields
    )
    if allow_legacy_extras and unknown_replay_fields:
        raise ValueError(
            "early-v3 checker input contains unknown replay fields "
            f"{sorted(unknown_replay_fields)}"
        )
    if legacy_specificity is not None and not allow_legacy_extras:
        raise ValueError(
            "legacy specificity migration requires explicit early-v3 replay"
        )
    kind = value.get("kind")
    payload = value.get("payload")
    if not isinstance(kind, str) or not kind:
        raise ValueError("v3 checker input kind must be a non-empty string")
    if not isinstance(payload, dict):
        raise ValueError("v3 checker input payload must be an object")
    # Compiler <=3.1.10 encoded non-witness specificity as a fabricated
    # checker payload ({"family_only": true} or {"unparseable": true}) while
    # the independently hashed checker_core correctly remained empty. Accept
    # only that exact sentinel, and only when the gate's specificity evidence
    # names the same state. This is a compatibility migration, not a general
    # payload rewrite.
    retired_sentinel = next(
        (
            specificity
            for specificity in ("family_only", "unparseable")
            if payload == {specificity: True}
        ),
        None,
    )
    if retired_sentinel is not None:
        if not (
            allow_legacy_extras
            and legacy_specificity == retired_sentinel
        ):
            raise ValueError(
                "retired early-v3 specificity sentinel requires explicit "
                "replay with matching specificity evidence"
            )
        payload = {}
    return {"kind": kind, "payload": deepcopy(payload)}


def content_id(prefix: str, value: Any, length: int = 24) -> str:
    return f"{prefix}_{canonical_sha256(value)[:length]}"


@lru_cache(maxsize=4)
def engine_implementation_sha256(package_dir: Path | None = None) -> str | None:
    """Hash this engine's own Python source, for the provenance chain.

    Three things decide a verdict and only two of them were covered. The checker bundle is
    pinned by the contract and verified at runtime (a mismatch raises), and the boundary /
    consensus / identity policies carry sha256s in every report's lineage. The ENGINE
    implementation was covered by nothing but a version string — yet `canonical.py` decides
    what counts as the same mathematical object and `consensus_v3.py` decides what counts as
    agreement, so the same compiled records could be re-scored to different lanes under
    different engine code with nothing in the artifacts to show it.

    Returns None rather than raising when the source is unreadable (zipped install, stripped
    deployment): a missing hash must be visibly absent in the report, never silently wrong,
    and must not block scoring.

    ``package_dir`` exists so the sensitivity property is testable against a scratch tree; a
    tripwire that cannot be shown to fire is not a tripwire. Production callers pass nothing.
    """
    package = Path(package_dir) if package_dir is not None else Path(__file__).resolve().parent
    try:
        sources = sorted(package.glob("*.py"))
        if not sources:
            # A missing or stripped directory globs empty rather than raising, so hashing
            # would return a perfectly valid digest OF NOTHING — the silently-wrong outcome
            # this function exists to prevent. Absent must read as absent.
            return None
        digest = hashlib.sha256()
        for path in sources:
            digest.update(path.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
    except OSError:
        return None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        _fsync_directory(path.parent)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def write_json_atomic(path: Path, value: Any) -> None:
    write_text_atomic(
        path,
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )


def iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: each JSONL record must be an object")
            yield line_number, value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [value for _, value in iter_jsonl(path)]


def write_jsonl_atomic(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    write_text_atomic(path, text)


def stable_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def next_generation(root: Path, prefix: str = "gen") -> Path:
    """Atomically reserve the next immutable generation directory.

    Multiple workers may scan the same maximum.  ``mkdir(exist_ok=False)`` is
    the reservation primitive; a collision simply advances to the next number.
    """
    root.mkdir(parents=True, exist_ok=True)
    numbers: list[int] = []
    for path in root.iterdir():
        if not path.is_dir() or not path.name.startswith(prefix + "_"):
            continue
        suffix = path.name[len(prefix) + 1 :]
        if suffix.isdigit():
            numbers.append(int(suffix))
    number = max(numbers, default=0) + 1
    while True:
        generation = root / f"{prefix}_{number:03d}"
        try:
            generation.mkdir(exist_ok=False)
        except FileExistsError:
            number += 1
            continue
        return generation
