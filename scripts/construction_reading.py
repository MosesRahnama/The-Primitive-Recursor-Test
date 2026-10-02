"""Construction reading round r7: seed, check, flatten, brief and document per-session reading records.

The record contract is scoring/construction_reading/R7_SCHEMA.json. The paragraph-block
construction, the file digest and the text reader come from scripts/tier1_source_reading.py
(the Tier 1 reading tool); the validation and export logic here follows the r7 contract.

Commands never write a grade. Readers copy quotations and pick menu values; this tool
checks identity, menus, quotations, coverage and the paired-quote rule.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tier1_source_reading import digest, read_text  # noqa: E402  (reused from the Tier 1 tool)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "scoring/construction_reading/R7_SCHEMA.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
VERSION = SCHEMA["schema_version"]
SLOT_LIMIT = int(SCHEMA["slot_count"])
# Constructions past the sixth live in `constructions_overflow_json` and keep the ids
# `c7`, `c8`, ... The widest record read so far holds ten constructions; six overflow
# columns cover that with room to spare and keep the flattened row's id range closed.
OVERFLOW_LIMIT = 6
IDENTITY_FIELDS = list(SCHEMA["identity_fields"])
FROZEN_IDENTITY = (
    "schema_version", "test", "session_slug", "source", "source_sha256",
    "prompt", "prompt_sha256",
)
RECORD_STATUSES = list(SCHEMA["identity_rules"]["record_status"])
EXPOSURES = list(SCHEMA["identity_rules"]["exposure"])
COVERAGE_ROLES = ["mathematical", "non_mathematical", "mixed", "unclear"]
SOURCE_FORMS = ("reader", "tier1", "v3", "r5", "merged")
FORBIDDEN_WORDS = list(SCHEMA["forbidden_field_words"])
TESTS_CFG = SCHEMA["tests"]
MANIFEST_PATH = ROOT / "results/tier1_source_reading/manifest.csv"
LEDGER_NAMES = {
    "schema_a": "schema_a_method_review_overrides.csv",
    "schema_a_new_system": "schema_a_new_system_method_review_overrides.csv",
    "test01": "test01_method_review_overrides.csv",
    "test03": "test03_semantic_review_overrides.csv",
}
INSTRUCTIONS = ROOT / "instructions/extraction/construction_reading"
ROUND_FILE_RE = re.compile(r"^.+_r\d+\.csv$")
NO_QUOTE_NEEDED = {"", "absent", "none", "unstated"}
EMPTY_ALLOWED = {
    "coequal_slots", "unmapped_paragraph_ids", "constructions_overflow_json",
    "other_task_claim_quote", "retained_negative_claim_quote",
    "transcription_flag_quote", "transcription_flag_note", "transcription_flags_all",
    "symbol_definitions_quote",
}
QUOTE_CURLY = str.maketrans({
    0x2018: 0x27, 0x2019: 0x27, 0x201A: 0x27, 0x201B: 0x27,
    0x201C: 0x22, 0x201D: 0x22, 0x201E: 0x22, 0x201F: 0x22,
})

csv.field_size_limit(10**8)


# --------------------------------------------------------------------------- shared helpers


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames or []
        if not names or len(set(names)) != len(names):
            raise ValueError(f"missing or duplicate headers: {path}")
        rows = list(reader)
        if any(None in row or None in row.values() for row in rows):
            raise ValueError(f"malformed CSV row: {path}")
        return names, rows


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def blocks(text: str) -> list[dict]:
    """Paragraph blocks of the response; adapted from tier1_source_reading.blocks."""
    lines = text.splitlines()
    groups: list[dict] = []
    start = None
    for index in range(len(lines) + 1):
        if index < len(lines) and lines[index].strip():
            if start is None:
                start = index
        elif start is not None:
            content = "\n".join(lines[start:index])
            groups.append({
                "block_id": f"b{len(groups) + 1}",
                "start_line": start + 1,
                "end_line": index,
                "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "role": "",
                "supports": [],
            })
            start = None
    return groups


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def quote_variants(text: str) -> list[str]:
    base = normalize_text(text)
    straight = base.translate(QUOTE_CURLY)
    collapsed = collapse_whitespace(base)
    collapsed_straight = collapse_whitespace(straight)
    undoubled = collapsed_straight.replace("\\\\", "\\")
    return [base, straight, collapsed, collapsed_straight, undoubled]


def quote_occurrences(quote: str, response_text: str) -> int:
    """Count occurrences of a quote under the lossless normalization of the score module.

    The pairs follow scoring/score_closure_candidates.py quote_match: exact NFC text,
    straight quote characters, collapsed whitespace, and doubled backslashes undone.
    """
    if not quote:
        return 0
    source_variants = quote_variants(response_text)
    for candidate, source in zip(quote_variants(quote), source_variants):
        if candidate and candidate in source:
            return source.count(candidate)
    return 0


# --------------------------------------------------------------------------- schema views


def session_specs(test: str) -> dict:
    if test == "test03":
        specs: dict[str, dict] = {}
        for branch in SCHEMA["test03_fields"]["branches"]:
            for name, spec in SCHEMA["test03_fields"]["per_branch"].items():
                field = name.replace("<branch>", branch)
                copied = dict(spec)
                if "quote" in copied:
                    copied["quote"] = str(copied["quote"]).replace("<branch>", branch)
                copied["type"] = str(copied.get("type", "")).replace("<branch>", branch)
                specs[field] = copied
        specs.update(SCHEMA["test03_fields"]["session"])
    else:
        specs = dict(SCHEMA["session_fields_open_tests"])
    expanded: dict[str, dict] = {}
    for field, spec in specs.items():
        expanded[field] = spec
        quote = spec.get("quote")
        if quote and quote not in specs and quote not in expanded:
            expanded[quote] = {"type": "quote"}
    return expanded


def slot_specs() -> dict:
    return dict(SCHEMA["slot_fields"])


def overflow_slots(session) -> list[dict]:
    """The constructions a record keeps past the six inline slots.

    A response with more than six constructions keeps the first six in `slots` and the
    rest in `constructions_overflow_json`. Those extra constructions carry ids too:
    `c7`, `c8`, ... in the order they appear in the list.
    """
    if not isinstance(session, dict):
        return []
    overflow = session.get("constructions_overflow_json", "")
    if isinstance(overflow, str):
        if not overflow.strip():
            return []
        try:
            overflow = json.loads(overflow)
        except json.JSONDecodeError:
            return []
    if not isinstance(overflow, list):
        return []
    return [slot if isinstance(slot, dict) else {} for slot in overflow]


def slot_ids_of(slots: list, session) -> set[str]:
    """Every slot id a record may name: `c1` to `c6`, then the overflow ids `c7`..."""
    return {f"c{index}" for index in range(1, len(slots) + len(overflow_slots(session)) + 1)}


def premise_items(test: str) -> dict:
    catalog = TESTS_CFG[test].get("premise_catalog")
    if not catalog:
        return {}
    return dict(SCHEMA["premise_catalogs"][catalog])


def menu_of(spec: dict) -> list | None:
    return spec.get("menu")


def integer_range(spec: dict) -> tuple[int, int] | None:
    kind = spec.get("type", "")
    if not kind.startswith("integer"):
        return None
    numbers = [int(value) for value in re.findall(r"\d+", kind)]
    if len(numbers) >= 2:
        return numbers[0], numbers[1]
    return 0, 10**9


def is_quote_spec(spec: dict) -> bool:
    return "quote" in spec or str(spec.get("type", "")).startswith("quote")


def session_template(test: str) -> dict:
    return {field: "" for field in session_specs(test)}


def premise_template(test: str) -> dict:
    return {item: {"status": "", "quote": "", "used_by": []} for item in premise_items(test)}


# --------------------------------------------------------------------------- source binding


def repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def manifest_index() -> dict[tuple[str, str], dict]:
    if not MANIFEST_PATH.is_file():
        return {}
    _, rows = read_csv(MANIFEST_PATH)
    return {(row["test"], row["session_slug"]): row for row in rows}


def ledger_index(test: str) -> dict[str, dict]:
    name = LEDGER_NAMES.get(test)
    if not name:
        return {}
    path = ROOT / "results/final_scored_data/overrides" / name
    if not path.is_file():
        return {}
    _, rows = read_csv(path)
    return {row.get("session_slug", ""): row for row in rows}


def session_dir(test: str, slug: str) -> Path:
    return ROOT / TESTS_CFG[test]["test_dir"] / "test-sessions" / slug


def resolve_binding(test: str, slug: str) -> dict:
    """Resolve the bound response and prompt: manifest first, then ledger, then default names.

    A candidate whose file is absent falls through to the next source. The call fails
    when no candidate file exists.
    """
    if test not in TESTS_CFG:
        raise ValueError(f"unknown test: {test}")
    config = TESTS_CFG[test]
    manifest = manifest_index().get((test, slug), {})
    ledger = ledger_index(test).get(slug, {})
    directory = session_dir(test, slug)
    # The ledger's evidence_path names a proof artifact (a Lean or TTT2 file), never the
    # response, so it is not a candidate. Only files under the test's test-sessions folder bind.
    manifest_source = manifest.get("source", "")
    if "test-sessions" not in manifest_source.replace("\\", "/"):
        manifest_source = ""
    response_candidates = [
        ("manifest", manifest_source),
        ("default", str(directory / config["response_file"])),
    ]
    prompt_candidates = [
        ("manifest", manifest.get("prompt", "")),
        ("default", str(directory / config["prompt_file"])),
    ]
    response = _first_file(response_candidates, "response", slug)
    prompt = _first_file(prompt_candidates, "prompt", slug)
    return {"response": response, "prompt": prompt}


def _first_file(candidates: list[tuple[str, str]], kind: str, slug: str) -> Path:
    tried = []
    for source, value in candidates:
        if not value:
            continue
        path = repo_path(value)
        tried.append(f"{source}:{display_path(path)}")
        if path.is_file():
            return path
    raise ValueError(f"missing {kind} file for {slug}; tried " + ", ".join(tried))


def records_root(test: str, override: str | None) -> Path:
    if override:
        return Path(override)
    return ROOT / TESTS_CFG[test]["test_dir"] / "extraction/r7_records"


def default_export_path(test: str, to_extraction: bool) -> Path:
    prefix = TESTS_CFG[test]["prefix"]
    if to_extraction:
        return ROOT / TESTS_CFG[test]["test_dir"] / "extraction" / f"{prefix}_r7.csv"
    return ROOT / "results/scoring_review/r7" / f"{prefix}_r7.csv"


def seed_record(test: str, slug: str, reader: str = "") -> dict:
    binding = resolve_binding(test, slug)
    record = {
        "schema_version": VERSION,
        "test": test,
        "session_slug": slug,
        "reader": reader,
        "source": display_path(binding["response"]),
        "source_sha256": digest(binding["response"]),
        "prompt": display_path(binding["prompt"]),
        "prompt_sha256": digest(binding["prompt"]),
        "record_status": "pending",
        "exposure": "",
        "read_complete": False,
        "coverage": blocks(read_text(binding["response"])),
        "reader_notes": "",
        "source_form": "reader",
        "session": session_template(test),
        "slots": [],
        "premises": premise_template(test),
    }
    return record


# --------------------------------------------------------------------------- validation


def forbidden_names(value, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            for word in FORBIDDEN_WORDS:
                if word in str(key):
                    errors.append(f"FORBIDDEN_FIELD:{path}{key}")
                    break
            forbidden_names(item, f"{path}{key}.", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            forbidden_names(item, f"{path}{index}.", errors)


def _check_quote(value, path: str, response_text: str | None, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"QUOTE_TYPE:{path}")
        return
    if not value:
        return
    if response_text is None:
        errors.append(f"QUOTE_UNBOUND:{path}")
    elif quote_occurrences(value, response_text) == 0:
        errors.append(f"QUOTE_NOT_VERBATIM:{path}")


def _check_value(field: str, value, spec: dict, path: str, response_text: str | None,
                 complete: bool, errors: list[str], empty_ok: bool = False) -> None:
    menu = menu_of(spec)
    bounds = integer_range(spec)
    if menu is not None:
        if value == "":
            if complete:
                errors.append(f"FIELD_EMPTY:{path}")
            return
        if value not in menu:
            errors.append(f"MENU_VALUE:{path}")
        return
    if bounds is not None:
        if value == "":
            if complete:
                errors.append(f"FIELD_EMPTY:{path}")
            return
        if type(value) is not int:
            errors.append(f"INTEGER_TYPE:{path}")
            return
        low, high = bounds
        if not low <= value <= high:
            errors.append(f"INTEGER_RANGE:{path}")
        return
    if is_quote_spec(spec):
        _check_quote(value, path, response_text, errors)
        return
    if not isinstance(value, str):
        errors.append(f"FIELD_TYPE:{path}")
    elif value == "" and complete and not empty_ok:
        errors.append(f"FIELD_EMPTY:{path}")


def _check_paired_quote(field: str, spec: dict, value, holder: dict, path: str, errors: list[str]) -> None:
    quote_field = spec.get("quote")
    if not quote_field:
        return
    if value in NO_QUOTE_NEEDED:
        return
    quote = holder.get(quote_field, "")
    if not isinstance(quote, str) or not quote:
        errors.append(f"PAIRED_QUOTE_MISSING:{path}")


def validate_record(record, *, test: str, allow_partial: bool = False) -> list[str]:
    """Return every validation error of one record; an empty list means valid.

    A full r7 record carries schema_version and the seeded fields. An adapter record
    carries source_form and only the fields its input decided; --allow-partial accepts
    both and skips the completeness rules.
    """
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["RECORD_NOT_OBJECT"]
    if test not in TESTS_CFG:
        return [f"UNKNOWN_TEST:{test}"]
    forbidden_names(record, "", errors)
    if record.get("schema_version") != VERSION:
        return _validate_partial(record, test=test, errors=errors)
    response_text = _bound_response_text(record, test, errors, strict_identity=not allow_partial)
    if "source_form" in record and record.get("source_form") not in SOURCE_FORMS:
        errors.append("SOURCE_FORM")
    status = record.get("record_status")
    if status not in RECORD_STATUSES:
        errors.append("RECORD_STATUS")
    complete = status == "complete"
    if type(record.get("read_complete")) is not bool:
        errors.append("READ_COMPLETE_TYPE")
    if not isinstance(record.get("reader_notes"), str):
        errors.append("READER_NOTES_TYPE")
    exposure = record.get("exposure")
    if exposure not in EXPOSURES and exposure != "":
        errors.append("EXPOSURE_VALUE")
    if complete:
        if record.get("read_complete") is not True:
            errors.append("FULL_READING_NOT_ATTESTED")
        if exposure not in EXPOSURES:
            errors.append("EXPOSURE_UNDECLARED")
    session = record.get("session")
    if not isinstance(session, dict):
        errors.append("SESSION_NOT_OBJECT")
        session = {}
    specs = session_specs(test)
    for field in sorted(set(session) - set(specs)):
        errors.append(f"UNKNOWN_SESSION_FIELD:{field}")
    for field, spec in specs.items():
        if field not in session:
            if complete:
                errors.append(f"MISSING_SESSION_FIELD:{field}")
            continue
        value = session[field]
        _check_value(field, value, spec, field, response_text, complete, errors, field in EMPTY_ALLOWED)
        _check_paired_quote(field, spec, value, session, field, errors)
    slots = record.get("slots")
    if not isinstance(slots, list):
        errors.append("SLOTS_NOT_LIST")
        slots = []
    if len(slots) > SLOT_LIMIT:
        errors.append("SLOT_LIMIT")
    if test == "test03" and slots:
        errors.append("TEST03_SLOTS_PRESENT")
    specs = slot_specs()
    for index, slot in enumerate(slots, 1):
        path = f"c{index}"
        if not isinstance(slot, dict):
            errors.append(f"SLOT_NOT_OBJECT:{path}")
            continue
        for field in sorted(set(slot) - set(specs)):
            errors.append(f"UNKNOWN_SLOT_FIELD:{path}.{field}")
        for field, spec in specs.items():
            if field not in slot:
                if complete:
                    errors.append(f"MISSING_SLOT_FIELD:{path}.{field}")
                continue
            _check_value(field, slot[field], spec, f"{path}.{field}", response_text, complete, errors)
            _check_paired_quote(field, spec, slot[field], slot, f"{path}.{field}", errors)
    premise_specs = premise_items(test)
    premises = record.get("premises")
    if not isinstance(premises, dict):
        errors.append("PREMISES_NOT_OBJECT")
        premises = {}
    for item in sorted(set(premises) - set(premise_specs)):
        errors.append(f"UNKNOWN_PREMISE:{item}")
    for item in sorted(premise_specs):
        if item not in premises:
            if complete:
                errors.append(f"MISSING_PREMISE:{item}")
            continue
        entry = premises[item]
        if not isinstance(entry, dict) or set(entry) != {"status", "quote", "used_by"}:
            errors.append(f"PREMISE_FIELDS:{item}")
            continue
        value = entry["status"]
        if value == "":
            if complete:
                errors.append(f"PREMISE_STATUS_EMPTY:{item}")
        elif value not in SCHEMA["premise_status_menu"]:
            errors.append(f"PREMISE_STATUS:{item}")
        _check_quote(entry["quote"], f"premises.{item}.quote", response_text, errors)
        used_by = entry["used_by"]
        if not isinstance(used_by, list) or any(not isinstance(x, str) for x in used_by):
            errors.append(f"PREMISE_USED_BY:{item}")
            used_by = []
        slot_ids = slot_ids_of(slots, session)
        for slot_id in used_by:
            if slot_id not in slot_ids:
                errors.append(f"PREMISE_SLOT_UNKNOWN:{item}.{slot_id}")
        if value in {"asserted_used", "asserted_aside", "denied"} and not entry["quote"]:
            errors.append(f"PREMISE_QUOTE_MISSING:{item}")
        if value == "asserted_used" and not used_by:
            errors.append(f"PREMISE_USED_BY_MISSING:{item}")
        if value == "absent" and used_by:
            errors.append(f"PREMISE_USED_BY_UNEXPECTED:{item}")
    coverage = record.get("coverage")
    if not isinstance(coverage, list):
        errors.append("COVERAGE_NOT_LIST")
    else:
        _check_coverage(coverage, response_text, slots, premises, complete, complete, errors,
                        overflow_count=len(overflow_slots(session)))
    overflow = session.get("constructions_overflow_json", "")
    if isinstance(overflow, str) and overflow:
        try:
            value = json.loads(overflow)
            if not isinstance(value, list):
                errors.append("OVERFLOW_NOT_LIST")
        except json.JSONDecodeError:
            errors.append("OVERFLOW_JSON")
    return sorted(set(errors))


def _bound_response_text(record: dict, test: str, errors: list[str], *, strict_identity: bool) -> str | None:
    slug = record.get("session_slug")
    source = record.get("source", "")
    if not isinstance(slug, str) or not slug:
        if strict_identity:
            errors.append("IDENTITY_MISSING:session_slug")
        return None
    if not isinstance(source, str) or not source:
        if strict_identity:
            errors.append("IDENTITY_MISSING:source")
        return None
    path = repo_path(source)
    if not path.is_file():
        errors.append(f"BOUND_SOURCE_MISSING:{source}")
        return None
    if record.get("source_sha256") and digest(path) != record["source_sha256"]:
        errors.append("SOURCE_HASH_MISMATCH:source")
    if not strict_identity:
        if record.get("test") not in (None, test):
            errors.append(f"TEST_MISMATCH:{record.get('test')}")
        return read_text(path)
    try:
        fresh = seed_record(test, slug, str(record.get("reader", "")))
    except ValueError as exc:
        errors.append(f"BINDING_FAILED:{exc}")
        return read_text(path)
    for field in FROZEN_IDENTITY:
        if record.get(field) != fresh.get(field):
            errors.append(f"IDENTITY_CHANGED:{field}")
    return read_text(path)


def _check_coverage(coverage: list, response_text: str | None, slots: list, premises: dict,
                    complete: bool, require_roles: bool, errors: list[str],
                    overflow_count: int = 0) -> None:
    if response_text is None:
        return
    expected = blocks(response_text)
    if len(coverage) != len(expected):
        errors.append("COVERAGE_LENGTH")
        return
    slot_ids = {f"c{index}" for index in range(1, len(slots) + overflow_count + 1)}
    premise_ids = set(premises) if isinstance(premises, dict) else set()
    for got, want in zip(coverage, expected):
        if not isinstance(got, dict):
            errors.append("COVERAGE_BLOCK")
            continue
        block_id = want["block_id"]
        for key in ("block_id", "start_line", "end_line", "sha256", "role", "supports"):
            if key not in got:
                errors.append(f"COVERAGE_FIELD:{block_id}.{key}")
        for key in ("block_id", "start_line", "end_line", "sha256"):
            if got.get(key) != want[key]:
                errors.append(f"COVERAGE_BLOCK:{block_id}.{key}")
        role = got.get("role", "")
        if role == "":
            if require_roles:
                errors.append(f"COVERAGE_ROLE_EMPTY:{block_id}")
        elif role not in COVERAGE_ROLES:
            errors.append(f"COVERAGE_ROLE:{block_id}")
        supports = got.get("supports", [])
        if not isinstance(supports, list) or any(not isinstance(x, str) for x in supports):
            errors.append(f"COVERAGE_SUPPORTS:{block_id}")
            continue
        for item in supports:
            if item not in slot_ids and item not in premise_ids:
                errors.append(f"COVERAGE_SUPPORT_UNKNOWN:{block_id}.{item}")
        if role in {"mathematical", "mixed"} and not supports:
            errors.append(f"COVERAGE_UNMAPPED:{block_id}")
        if role == "non_mathematical" and supports:
            errors.append(f"NONMATH_BLOCK_SUPPORTS:{block_id}")


def _validate_partial(record: dict, *, test: str, errors: list[str]) -> list[str]:
    if record.get("source_form") not in SOURCE_FORMS:
        errors.append("SOURCE_FORM")
    if record.get("schema_version") not in (None, VERSION):
        errors.append("SCHEMA_VERSION")
    response_text = None
    source = record.get("source", "")
    if isinstance(source, str) and source:
        path = repo_path(source)
        if path.is_file():
            if record.get("source_sha256") and digest(path) != record["source_sha256"]:
                errors.append("SOURCE_HASH_MISMATCH:source")
            response_text = read_text(path)
        else:
            errors.append(f"BOUND_SOURCE_MISSING:{source}")
    session = record.get("session", {})
    if session and not isinstance(session, dict):
        errors.append("SESSION_NOT_OBJECT")
        session = {}
    specs = session_specs(test)
    for field in sorted(set(session) - set(specs)):
        errors.append(f"UNKNOWN_SESSION_FIELD:{field}")
    for field, spec in specs.items():
        if field in session:
            _check_value(field, session[field], spec, field, response_text, False, errors)
            _check_paired_quote(field, spec, session[field], session, field, errors)
    slots = record.get("slots", [])
    if not isinstance(slots, list):
        errors.append("SLOTS_NOT_LIST")
        slots = []
    if len(slots) > SLOT_LIMIT:
        errors.append("SLOT_LIMIT")
    slot_field_specs = slot_specs()
    for index, slot in enumerate(slots, 1):
        path = f"c{index}"
        if not isinstance(slot, dict):
            errors.append(f"SLOT_NOT_OBJECT:{path}")
            continue
        for field in sorted(set(slot) - set(slot_field_specs)):
            errors.append(f"UNKNOWN_SLOT_FIELD:{path}.{field}")
        for field, spec in slot_field_specs.items():
            if field in slot:
                _check_value(field, slot[field], spec, f"{path}.{field}", response_text, False, errors)
                _check_paired_quote(field, spec, slot[field], slot, f"{path}.{field}", errors)
    premise_specs = premise_items(test)
    premises = record.get("premises", {})
    if premises and not isinstance(premises, dict):
        errors.append("PREMISES_NOT_OBJECT")
        premises = {}
    for item in sorted(set(premises) - set(premise_specs)):
        errors.append(f"UNKNOWN_PREMISE:{item}")
    for item, entry in sorted(premises.items()):
        if not isinstance(entry, dict):
            errors.append(f"PREMISE_FIELDS:{item}")
            continue
        for field in sorted(set(entry) - {"status", "quote", "used_by"}):
            errors.append(f"UNKNOWN_PREMISE_FIELD:{item}.{field}")
        status = entry.get("status", "")
        if status and status not in SCHEMA["premise_status_menu"]:
            errors.append(f"PREMISE_STATUS:{item}")
        _check_quote(entry.get("quote", ""), f"premises.{item}.quote", response_text, errors)
        used_by = entry.get("used_by", [])
        if used_by and not isinstance(used_by, list):
            errors.append(f"PREMISE_USED_BY:{item}")
    conflicts = record.get("conflicts")
    if conflicts is not None and not isinstance(conflicts, dict):
        errors.append("CONFLICTS_NOT_OBJECT")
    return sorted(set(errors))


# --------------------------------------------------------------------------- flattening


def flatten_columns(test: str, *, literal_names: bool = False) -> list[str]:
    columns = ["session_slug"]
    for field in session_specs(test):
        columns.append(field if literal_names else ("final_verdict_value" if field == "final_verdict" else field))
    if test != "test03":
        for index in range(1, SLOT_LIMIT + OVERFLOW_LIMIT + 1):
            for field in slot_specs():
                columns.append(f"c{index}_{field}")
    for item in premise_items(test):
        columns.extend([f"premise_{item}_status", f"premise_{item}_quote", f"premise_{item}_used_by"])
    columns.extend(["coverage_blocks", "coverage_mapped", "coverage_unmapped"])
    return columns


def coverage_counts(record: dict) -> tuple[int, int, int]:
    coverage = record.get("coverage", [])
    total = len(coverage)
    mapped, unmapped = 0, 0
    for block in coverage:
        role = block.get("role", "")
        supports = block.get("supports", [])
        if not role:
            unmapped += 1
        elif role in {"mathematical", "mixed"}:
            if supports:
                mapped += 1
            else:
                unmapped += 1
        else:
            mapped += 1
    return total, mapped, unmapped


def flatten_row(test: str, record: dict, *, literal_names: bool = False) -> dict[str, str]:
    row: dict[str, str] = {"session_slug": str(record.get("session_slug", ""))}
    session = record.get("session", {})
    for field in session_specs(test):
        value = session.get(field, "")
        name = field if literal_names else ("final_verdict_value" if field == "final_verdict" else field)
        row[name] = _cell(value)
    if test != "test03":
        inline = [slot for slot in record.get("slots", [])[:SLOT_LIMIT]]
        overflow = overflow_slots(record.get("session"))
        for index, slot in enumerate([*inline, *overflow][: SLOT_LIMIT + OVERFLOW_LIMIT], 1):
            for field in slot_specs():
                row[f"c{index}_{field}"] = _cell(slot.get(field, ""))
    premises = record.get("premises", {})
    for item in premise_items(test):
        entry = premises.get(item, {})
        row[f"premise_{item}_status"] = _cell(entry.get("status", ""))
        row[f"premise_{item}_quote"] = _cell(entry.get("quote", ""))
        row[f"premise_{item}_used_by"] = _cell(entry.get("used_by", []))
    total, mapped, unmapped = coverage_counts(record)
    row["coverage_blocks"] = str(total)
    row["coverage_mapped"] = str(mapped)
    row["coverage_unmapped"] = str(unmapped)
    return row


def _cell(value) -> str:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    if type(value) is bool:
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def load_records(test: str, root: Path) -> list[tuple[Path, dict]]:
    if not root.is_dir():
        return []
    out = []
    for path in sorted(p for p in root.glob("*.json") if ".wrongsource." not in p.name and ".v1." not in p.name):
        try:
            out.append((path, load_json(path)))
        except (json.JSONDecodeError, OSError, UnicodeError) as exc:
            out.append((path, {"record_status": "invalid", "_load_error": str(exc)}))
    return out


def export_rows(test: str, root: Path, *, require_complete: bool,
                literal_names: bool = False) -> tuple[list[str], list[dict], list[dict]]:
    columns = flatten_columns(test, literal_names=literal_names)
    rows, skipped = [], []
    for path, record in load_records(test, root):
        if not isinstance(record, dict) or record.get("schema_version") != VERSION:
            skipped.append({"record": str(path), "reason": "malformed"})
            continue
        errors = validate_record(record, test=test)
        if record.get("record_status") == "complete" and not errors:
            rows.append(flatten_row(test, record, literal_names=literal_names))
        else:
            skipped.append({
                "record": str(path),
                "reason": record.get("record_status", "invalid"),
                "errors": errors,
            })
    if require_complete and skipped:
        raise ValueError("export refused: " + json.dumps(skipped))
    return columns, rows, skipped


def export_to(test: str, root: Path, destination: Path, *, require_complete: bool,
              literal_names: bool = False) -> dict:
    columns, rows, skipped = export_rows(test, root, require_complete=require_complete,
                                         literal_names=literal_names)
    write_csv(destination, columns, rows)
    return {"rows": len(rows), "skipped": skipped, "path": str(destination), "columns": len(columns)}


# --------------------------------------------------------------------------- commands


def cmd_prepare(args) -> int:
    test = args.test
    names, rows = read_csv(Path(args.sessions))
    if "session_slug" not in names:
        raise ValueError("the sessions file needs a session_slug column")
    if "test" in names:
        wrong = [row["session_slug"] for row in rows if row["test"] != test]
        if wrong:
            raise ValueError(f"the sessions file names other tests: {wrong[:3]}")
    slugs = [row["session_slug"] for row in rows]
    if len(set(slugs)) != len(slugs):
        raise ValueError("the sessions file repeats a session_slug")
    root = records_root(test, args.records_root)
    seeded, kept = 0, 0
    for slug in slugs:
        path = root / f"{slug}.json"
        fresh = seed_record(test, slug, args.reader or "")
        if path.exists():
            current = load_json(path)
            if not isinstance(current, dict) or current.get("record_status") != "pending":
                raise ValueError(f"record is not pending; keeping it untouched: {path}")
            if current != fresh:
                raise ValueError(f"record content differs from a fresh seed; keeping it untouched: {path}")
            kept += 1
            continue
        write_json(path, fresh)
        seeded += 1
    print(f"test={test} sessions={len(slugs)} seeded={seeded} kept={kept} records_root={root}")
    return 0


def cmd_validate(args) -> int:
    test = args.test
    if args.record:
        paths = [Path(args.record)]
    else:
        root = records_root(test, args.records_root)
        paths = sorted(p for p in root.glob("*.json") if ".wrongsource." not in p.name and ".v1." not in p.name)
    errors_total = 0
    for path in paths:
        try:
            record = load_json(path)
            errors = validate_record(record, test=test, allow_partial=args.allow_partial)
        except (json.JSONDecodeError, OSError, UnicodeError) as exc:
            errors = [f"UNREADABLE:{exc}"]
        errors_total += len(errors)
        for error in errors:
            print(f"{path}: {error}")
        if not errors:
            print(f"{path}: OK")
    print(f"records={len(paths)} errors={errors_total}")
    return 1 if errors_total else 0


def cmd_status(args) -> int:
    test = args.test
    root = records_root(test, args.records_root)
    states: Counter = Counter()
    results: Counter = Counter()
    codes: Counter = Counter()
    for path, record in load_records(test, root):
        if not isinstance(record, dict) or record.get("schema_version") != VERSION:
            states["invalid"] += 1
            results["invalid"] += 1
            continue
        states[str(record.get("record_status", ""))] += 1
        errors = validate_record(record, test=test)
        if errors:
            results["invalid"] += 1
            for error in errors:
                codes[error.split(":")[0]] += 1
        elif record.get("record_status") == "complete":
            results["valid"] += 1
        else:
            results["incomplete"] += 1
    print(f"test={test} records_root={root} records={sum(states.values())}")
    for state, count in sorted(states.items()):
        print(f"record_status {state}={count}")
    for result, count in sorted(results.items()):
        print(f"validation {result}={count}")
    for code, count in sorted(codes.items()):
        print(f"error {code}={count}")
    return 0


def cmd_export(args) -> int:
    test = args.test
    root = records_root(test, args.records_root)
    destination = Path(args.out) if args.out else default_export_path(test, args.to_extraction)
    report = export_to(test, root, destination, require_complete=args.require_complete,
                       literal_names=args.literal_session_names)
    print(
        f"test={test} rows={report['rows']} skipped={len(report['skipped'])} "
        f"columns={report['columns']} -> {report['path']}"
    )
    for item in report["skipped"]:
        print(f"skipped {item['record']}: {item['reason']}")
    return 0


def cmd_dry_combine(args) -> int:
    test = args.test
    config = TESTS_CFG[test]
    prefix = config["prefix"]
    root = records_root(test, args.records_root)
    extraction = ROOT / config["test_dir"] / "extraction"
    rounds = sorted(path for path in extraction.iterdir() if ROUND_FILE_RE.match(path.name))
    if not rounds:
        raise ValueError(f"no round CSVs in {extraction}")
    work = Path(tempfile.mkdtemp(prefix="r7_dry_combine_"))
    try:
        for path in rounds:
            shutil.copy2(path, work / path.name)
        shutil.copy2(extraction / "combine_rounds.py", work / "combine_rounds.py")
        columns, rows, skipped = export_rows(test, root, require_complete=False,
                                             literal_names=args.literal_session_names)
        r7_path = work / f"{prefix}_r7.csv"
        write_csv(r7_path, columns, rows)
        result = subprocess.run(
            [sys.executable, "-B", "combine_rounds.py"],
            cwd=work, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        if result.returncode != 0:
            raise ValueError("combine_rounds failed: " + (result.stderr or result.stdout).strip())
        master = work / f"{prefix}_master_output.csv"
        if not master.is_file():
            raise ValueError(f"combine_rounds wrote no {master.name}")
        with master.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream))
        r7_columns = [name for name in header if name.startswith("r7__")]
        publish_ok = _publish_accepts(config, prefix)
        print(f"test={test} round_files={len(rounds)} r7_rows={len(rows)} skipped={len(skipped)}")
        print(f"master_columns={len(header)} r7_columns={len(r7_columns)}")
        print(f"r7_column_sample={json_text(r7_columns[:6])}")
        print(f"publish_final_extracted_data would accept the file names: {publish_ok}")
        return 0 if publish_ok else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _publish_accepts(config: dict, prefix: str) -> bool:
    import importlib.util

    path = ROOT / "scripts/publish_final_extracted_data.py"
    spec = importlib.util.spec_from_file_location("publish_final_extracted_data", path)
    if spec is None or spec.loader is None:
        return False
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dir_name = Path(config["test_dir"]).name
    known = any(item[1] == dir_name and item[2] == prefix for item in module.TESTS)
    return bool(module.ROUND_INPUT_RE.match(f"{prefix}_r7.csv")) and known


# --------------------------------------------------------------------------- documents


def _menu_table(specs: dict, *, prefix: str = "") -> str:
    lines = ["| Field | Values | Quote |", "|---|---|---|"]
    for field, spec in specs.items():
        label = prefix + field
        menu = menu_of(spec)
        bounds = integer_range(spec)
        quote = str(spec.get("quote", ""))
        if menu is not None:
            values = ", ".join(f"`{value}`" for value in menu)
        elif bounds is not None:
            values = str(spec.get("type", "integer")).strip()
        elif is_quote_spec(spec):
            values = "quotation"
        else:
            values = str(spec.get("type", "text")).strip()
        quote_cell = f"`{prefix}{quote}`" if quote else ""
        lines.append(f"| `{label}` | {values} | {quote_cell} |")
    return "\n".join(lines)


def render_reader() -> str:
    return "\n".join([
        "# Construction reading round r7 reader",
        "",
        "Read your batch brief, this file, FORMAT.md, and the bound responses named in the brief. Copy quotations and choose menu values. Write zero grades.",
        "",
        "| Setting | Rule |",
        "|---|---|",
        "| Workspace | `<workspace>` |",
        "| Assignment | One record per session in the sessions table of your batch brief. |",
        "| Raw outputs | Edit only the JSON paths listed in the brief. Keep extraction CSVs, scored data, normalized data and every other reader's records unchanged. |",
        "| Input boundaries | Read the bound response named in the brief. Exclude policies, ledgers, answer keys, scores, prior extraction rounds, and the sessions of other readers. |",
        "| Exposure | Set `exposure` to `none`, `prior_source` or `prior_grades`; describe each earlier sight of the response. |",
        "| Slots | Record every construction offered, rejected, hypothesized or mentioned, in order of first appearance, in at most six slots. Put further constructions in `constructions_overflow_json`; they carry the ids `c7`, `c8`, ... in list order, and every field that names a slot may name them. |",
        "| Quotes | Copy each quotation as a contiguous substring of the response. Keep formulas, symbol definitions, precedences and rule names as written. A menu value other than `absent`, `none` or `unstated` needs its paired quotation. |",
        "| Session fields | Fill every field of `session` for your test from FORMAT.md. |",
        "| Premises | Give every catalog item a status and a quotation where the status asserts or denies it. |",
        "| Coverage | Give every paragraph block a role and the slot or premise ids it supports. A mathematical or mixed block needs at least one id. |",
        "| Completion | Set `read_complete` true and `record_status` `complete` after the entire response and every construction appear in the record. |",
        "| Tools | Use the commands below. Work alone. |",
        "| Command boundary | Leave preparation, export, publication, scoring, Lean, Lake, Git commits, Git pushes and deletion unchanged. |",
        "",
        "| Action from the repository root | Command |",
        "|---|---|",
        "| Validate one record | `python scripts/construction_reading.py validate --test TEST --record \"PATH\"` |",
        "| Validate every record of the test | `python scripts/construction_reading.py validate --test TEST` |",
        "| Progress | `python scripts/construction_reading.py status --test TEST` |",
        "",
        "Report the batch number, completed records, validation result, exposure, and source or format problems in at most six lines. Omit mathematical opinions.",
        "",
    ])


def render_format() -> str:
    open_specs = dict(SCHEMA["session_fields_open_tests"])
    slot = slot_specs()
    lines = [
        "# Construction reading record format",
        "",
        "Fill the seeded JSON record with source statements. This file holds the field tables; the validator checks identity, menus, quotations and coverage.",
        "",
        "## Record parts",
        "",
        "| Part | Content |",
        "|---|---|",
        "| identity fields | `schema_version`, `test`, `session_slug`, `reader`, `source`, `source_sha256`, `prompt`, `prompt_sha256`, `record_status`, `exposure`, `read_complete`, `coverage`, `reader_notes` |",
        "| `source_form` | `reader` for a reading record |",
        "| `session` | the session fields below for your test |",
        "| `slots` | at most six objects in order of first appearance; each object has every slot field |",
        "| `premises` | one entry per catalog item, each with `status`, `quote` and `used_by` |",
        "| `coverage` | the seeded paragraph blocks, each with a role and its supported ids |",
        "",
        "Keep every seeded identity value unchanged. `record_status` is `pending`, `in_progress`, `complete` or `needs_attention`. `exposure` is `none`, `prior_source` or `prior_grades`. A complete record needs `read_complete` true, a declared exposure, and zero validation errors. `reader_notes` records source ambiguity or representation limits and holds zero correctness opinions.",
        "",
        "## Open-test session fields",
        "",
        _menu_table(open_specs),
        "",
        "## Test 03 branch and session fields",
        "",
        "Branches: " + ", ".join(f"`{branch}`" for branch in SCHEMA["test03_fields"]["branches"]) + ".",
        "",
        _menu_table(session_specs("test03")),
        "",
        "## Slot fields",
        "",
        _menu_table(slot),
        "",
        "## Premises",
        "",
        "Each catalog item gets `premise_<item>_status`, `premise_<item>_quote` and `premise_<item>_used_by` in the flattened row; in the record the item name holds an object with `status`, `quote` and `used_by`. Status values: " + ", ".join(f"`{value}`" for value in SCHEMA["premise_status_menu"]) + ". A status of `asserted_used` names the slot ids in `used_by`.",
        "",
    ]
    for catalog, items in SCHEMA["premise_catalogs"].items():
        lines.append(f"Catalog `{catalog}`:")
        lines.append("")
        lines.append("| Item | Description |")
        lines.append("|---|---|")
        for item, description in items.items():
            lines.append(f"| `{item}` | `{description}` |")
        lines.append("")
    lines.extend([
        "## Quotations",
        "",
        "Every quotation is a contiguous substring of the bound response after lossless normalization: Unicode NFC, straight quotation characters, collapsed whitespace, and LF line endings. Empty string means none. A menu value other than `absent`, `none` or `unstated` needs its paired quotation non-empty. Readers never repair, complete or paraphrase a formula.",
        "",
        "## Coverage",
        "",
        "Roles: " + ", ".join(f"`{role}`" for role in COVERAGE_ROLES) + ". Each block names the slot ids (`c1` to `c6`, then `c7`, `c8`, ... for the constructions in `constructions_overflow_json`) or premise ids it supports. A mathematical or mixed block names at least one id; a non-mathematical block names none.",
        "",
        "## Overflow",
        "",
        f"A response with more than six constructions keeps the first six in `slots` and the rest in `constructions_overflow_json` as a JSON list of slot objects. Those constructions carry the ids `c7`, `c8`, ... and `primary_slot`, `coequal_slots`, `revision_of`, `used_by` and `supports` may name them like any other slot.",
        "",
        "## Flattened row",
        "",
        f"One row per session: `session_slug`, then the session fields in table order, then `c1_<field>` through `c{SLOT_LIMIT + OVERFLOW_LIMIT}_<field>` for open tests, then `premise_<item>_status`, `premise_<item>_quote` and `premise_<item>_used_by`, then `coverage_blocks`, `coverage_mapped` and `coverage_unmapped`. The columns past `c{SLOT_LIMIT}` hold the constructions of `constructions_overflow_json` in order. Test 03 rows hold the branch and session fields in place of the slots. The session field `final_verdict` flattens to the column `final_verdict_value`, because the combine step of each extraction folder reserves columns ending in `_verdict` for its own `yes`, `no` and `unclear` values. The export flag `--literal-session-names` writes the column as `final_verdict` instead, and that reading makes the combine step move the `conditional` and `cannot_establish` values into the neighbouring quotation column.",
        "",
        "## Commands",
        "",
        "| Action | Command |",
        "|---|---|",
        "| Validate one record | `python scripts/construction_reading.py validate --test TEST --record \"PATH\"` |",
        "| Validate a test | `python scripts/construction_reading.py validate --test TEST` |",
        "| Progress | `python scripts/construction_reading.py status --test TEST` |",
        "",
    ])
    return "\n".join(lines)


def menus_markdown(test: str) -> str:
    lines = ["## Session fields", "", _menu_table(session_specs(test)), ""]
    if test != "test03":
        lines.extend(["## Slot fields", "", _menu_table(slot_specs()), ""])
    if premise_items(test):
        lines.extend(["## Premises", "", "| Item | Description |", "|---|---|"])
        for item, description in premise_items(test).items():
            lines.append(f"| `{item}` | {description} |")
        lines.append("")
    return "\n".join(lines)


def cmd_render_docs(args) -> int:
    INSTRUCTIONS.mkdir(parents=True, exist_ok=True)
    reader = INSTRUCTIONS / "READER.md"
    fmt = INSTRUCTIONS / "FORMAT.md"
    reader.write_text(render_reader(), encoding="utf-8", newline="\n")
    fmt.write_text(render_format(), encoding="utf-8", newline="\n")
    print(f"wrote {reader.relative_to(ROOT)} and {fmt.relative_to(ROOT)}")
    return 0


def cmd_brief(args) -> int:
    test = args.test
    template_path = INSTRUCTIONS / "BATCH_BRIEF_TEMPLATE.md"
    if not template_path.is_file():
        raise ValueError(f"missing template: {template_path}")
    template = template_path.read_text(encoding="utf-8")
    names, rows = read_csv(Path(args.sessions))
    if "session_slug" not in names:
        raise ValueError("the sessions file needs a session_slug column")
    root = records_root(test, args.records_root)
    resolved = []
    for row in rows:
        slug = row["session_slug"]
        binding = resolve_binding(test, slug)
        resolved.append(
            f"| `{slug}` | `{display_path(binding['response'])}` | `{digest(binding['response'])}` "
            f"| `{display_path(root / (slug + '.json'))}` |"
        )
    batch_size = int(args.batch)
    if batch_size < 1:
        raise ValueError("--batch needs a positive count")
    chunks = [resolved[index:index + batch_size] for index in range(0, len(resolved), batch_size)] or [[]]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(chunks)
    root_flag = f' --records-root "{display_path(root)}"' if args.records_root else ""
    validate_one = f'python scripts/construction_reading.py validate --test {test}{root_flag} --record "PATH"'
    validate_batch = f"python scripts/construction_reading.py validate --test {test}{root_flag}"
    status = f"python scripts/construction_reading.py status --test {test}{root_flag}"
    written = []
    for number, chunk in enumerate(chunks, 1):
        table = "\n".join(["| Session | Response | Response SHA-256 | Record |", "|---|---|---|---|"] + chunk)
        body = template
        body = body.replace("{{TEST}}", test)
        body = body.replace("{{BATCH_NUMBER}}", f"{number:02d}")
        body = body.replace("{{BATCH_TOTAL}}", f"{total:02d}")
        body = body.replace("{{SESSION_COUNT}}", str(len(chunk)))
        body = body.replace("{{RECORDS_ROOT}}", display_path(root))
        body = body.replace("{{SESSIONS_TABLE}}", table)
        body = body.replace("{{MENUS}}", menus_markdown(test))
        body = body.replace("{{VALIDATE_ONE}}", validate_one)
        body = body.replace("{{VALIDATE_BATCH}}", validate_batch)
        body = body.replace("{{STATUS_COMMAND}}", status)
        path = out_dir / f"r7_{test}_batch_{number:02d}.md"
        path.write_text(body.rstrip() + "\n", encoding="utf-8", newline="\n")
        written.append(str(path))
    print(f"test={test} sessions={len(rows)} batch_size={batch_size} briefs={len(written)}")
    for path in written:
        print(path)
    return 0


# --------------------------------------------------------------------------- entry point


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="construction_reading.py",
        description="Seed, check, flatten, brief and document the r7 construction-reading records.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str):
        item = sub.add_parser(name, help=help_text)
        item.add_argument("--test", required=True, choices=sorted(TESTS_CFG))
        item.add_argument("--records-root", default=None)
        return item

    prepare = add("prepare", "seed one reading record per session")
    prepare.add_argument("--sessions", required=True)
    prepare.add_argument("--reader", default="")
    prepare.set_defaults(func=cmd_prepare)

    validate = add("validate", "check records against the r7 contract")
    validate.add_argument("--record", default=None)
    validate.add_argument("--allow-partial", action="store_true")
    validate.set_defaults(func=cmd_validate)

    status = add("status", "count records by state and validation result")
    status.set_defaults(func=cmd_status)

    export = add("export", "flatten complete records to the round CSV")
    export.add_argument("--require-complete", action="store_true")
    export.add_argument("--to-extraction", action="store_true")
    export.add_argument("--out", default=None)
    export.add_argument("--literal-session-names", action="store_true",
                        help="write final_verdict as its own column name; the combine step reads that name as a yes/no/unclear menu")
    export.set_defaults(func=cmd_export)

    dry = add("dry-combine", "run the test combine step on a temporary copy")
    dry.add_argument("--literal-session-names", action="store_true")
    dry.set_defaults(func=cmd_dry_combine)

    brief = add("brief", "write one Markdown brief per batch of sessions")
    brief.add_argument("--sessions", required=True)
    brief.add_argument("--batch", required=True)
    brief.add_argument("--out", required=True)
    brief.set_defaults(func=cmd_brief)

    docs = sub.add_parser("render-docs", help="write READER.md and FORMAT.md from the schema")
    docs.add_argument("--records-root", default=None)
    docs.set_defaults(func=cmd_render_docs)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
