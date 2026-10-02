"""Prepare, migrate, validate and export source-only Tier 1 supplements; never assign grades.

Version 2 supports ten disjoint reader identities, manifest-driven population and
assignment counts, a twenty-record pilot released across workers, per-record
comparison against one authorized extraction pack, and reviewer-only adjudication.
Version 1 records and stages remain readable and are upgraded by migration without
rewriting occupied records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "results/tier1_source_reading"
VERSION = "prt-tier1-source-reading/2"
LEGACY_VERSIONS = {"prt-tier1-source-reading/1"}
APPROVALS_VERSION = "prt-tier1-source-reading-approvals/2"
TESTS = ("schema_a", "schema_a_new_system", "test01")
READERS = tuple(f"reader_{i}" for i in range(1, 11))
PILOT_TOTAL = 20
CHECKPOINT = 20
PRIORITY = {
    "SOURCE_READING_DISAGREEMENT": 0,
    "SOURCE_HASH_OR_QUOTE_MISMATCH": 1,
    "SOURCE_ASSERTION_UNRESOLVED": 2,
    "SOURCE_ASSERTION_COVERAGE_INCOMPLETE": 3,
}
INSTRUCTIONS = ROOT / "instructions/extraction/tier1"
KINDS = {
    "termination_verdict", "method_offer", "definition", "supporting_claim",
    "rejection_reason", "example", "qualification", "withdrawal", "other_math",
}
STANCES = {"asserted", "offered", "rejected", "hypothetical", "quoted", "unclear"}
DETAIL_FIELDS = {
    "method_name", "object", "domain", "parameters", "comparison", "scope",
    "conditions", "conclusion", "justification", "origin", "revision", "other",
}
RECORD_STATES = {"pending", "in_progress", "complete", "needs_attention"}
EXPOSURE_STATES = {"undeclared", "none", "prior_source", "prior_extractions_or_grades"}
COMPARISON_STATES = {
    "unreviewed", "consistent", "source_absence", "extraction_omission",
    "source_ambiguity", "template_limit", "conflict",
}
ADJUDICATION_STATES = {"unreviewed", "proposed", "rejected", "accepted"}
UNREVIEWED = "unreviewed"
PROTOCOL_KEYS = {
    "source_read_before_extraction", "extraction_pack", "extraction_pack_sha256",
    "comparison_exposure",
}
COMPARISON_KEYS = {"status", "fields", "evidence_ids", "notes"}
ADJUDICATION_KEYS = {"status", "reviewer", "decision", "accepted_evidence_ref"}
GRADE_MARKERS = (
    "score", "grade", "correct", "validity", "credited", "points", "marks",
    "boundary_compliance",
)
BOUND_FIELDS = ("test", "session_slug", "reader", "source", "source_sha256", "prompt", "prompt_sha256")
LEGACY_TOP_KEYS = {
    "schema_version", "test", "session_slug", "reader", "source", "source_sha256",
    "prompt", "prompt_sha256", "record_status", "exposure", "read_complete",
    "claims", "evidence", "coverage", "reader_notes",
}
TOP_KEYS = LEGACY_TOP_KEYS | {"reading_protocol", "comparison", "adjudication"}
CLAIM_KEYS = {"id", "kind", "stance", "evidence_ids", "related_to", "details", "unstated_fields"}
MANIFEST_FIELDS = [
    "reader", "order", "test", "session_slug", "source", "source_sha256",
    "prompt", "prompt_sha256", "record",
]
RAW_FIELDS = [
    "test", "session_slug", "source", "source_sha256", "prompt", "prompt_sha256",
    "reader", "schema_version", "record", "record_sha256", "exposure_json",
    "claims_json", "evidence_json", "coverage_json", "reader_notes",
    "additional_reading", "discrepancy_status", "discrepancy_fields",
    "adjudication_status", "accepted_evidence_ref",
]
SUPPLEMENT_FIELDS = [
    "additional_reading", "discrepancy_status", "discrepancy_fields",
    "adjudication_status", "accepted_evidence_ref",
]
NORMALIZED_FIELDS = [
    "t1_evidence_status", "t1_schema_version", "t1_reader", "t1_record",
    "t1_record_sha256", "t1_claims_json", "t1_evidence_json", "t1_coverage_json",
    "t1_exposure_json",
] + SUPPLEMENT_FIELDS
INPUT_PATHS = (
    "results/scoring_review/remaining_work.csv",
    "scoring/override_queue/closure_sessions.csv",
    "scoring/override_queue/active/selection.csv",
    "instructions/extraction/tier1/READER.md",
    "instructions/extraction/tier1/FORMAT.md",
    "scoring/CLOSURE_STATUS.md",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f"missing or duplicate headers: {path}")
        result = list(reader)
        if any(None in row or None in row.values() for row in result):
            raise ValueError(f"malformed CSV row: {path}")
        return result


def write_csv(path: Path, rows: list[dict], fields: list[str], *, new: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if new else "w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json_new(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def blocks(text: str) -> list[dict]:
    lines = text.splitlines()
    groups, start = [], None
    for i in range(len(lines) + 1):
        if i < len(lines) and lines[i].strip():
            if start is None:
                start = i
        elif start is not None:
            content = "\n".join(lines[start:i])
            groups.append({
                "block_id": f"b{len(groups) + 1}", "start_line": start + 1,
                "end_line": i, "sha256": hashlib.sha256(content.encode()).hexdigest(),
                "role": "unread", "claim_ids": [],
            })
            start = None
    return groups


def seed(row: dict[str, str]) -> dict:
    return {
        "schema_version": VERSION,
        **{k: row[k] for k in BOUND_FIELDS},
        "record_status": "pending",
        "exposure": {"status": "undeclared", "details": ""},
        "read_complete": False,
        "reading_protocol": {
            "source_read_before_extraction": False, "extraction_pack": "",
            "extraction_pack_sha256": "", "comparison_exposure": False,
        },
        "comparison": {"status": UNREVIEWED, "fields": [], "evidence_ids": [], "notes": ""},
        "adjudication": {
            "status": UNREVIEWED, "reviewer": "", "decision": "", "accepted_evidence_ref": "",
        },
        "claims": [], "evidence": [],
        "coverage": blocks(read_text(Path(row["source"]))), "reader_notes": "",
    }


def legacy_seed(row: dict[str, str]) -> dict:
    return {
        "schema_version": "prt-tier1-source-reading/1",
        **{k: row[k] for k in BOUND_FIELDS},
        "record_status": "pending",
        "exposure": {"status": "undeclared", "details": ""},
        "read_complete": False, "claims": [], "evidence": [],
        "coverage": blocks(read_text(Path(row["source"]))), "reader_notes": "",
    }


def is_pristine_seed(record: dict) -> bool:
    return (
        isinstance(record, dict)
        and record.get("record_status") == "pending"
        and record.get("read_complete") is False
        and record.get("claims") == [] and record.get("evidence") == []
        and isinstance(record.get("exposure"), dict)
        and record["exposure"].get("status") == "undeclared"
        and all(
            isinstance(b, dict) and b.get("role") == "unread" and not b.get("claim_ids")
            for b in record.get("coverage", [])
        )
    )


def check_ownership(rows: list[dict]) -> None:
    sessions, records, orders = {}, {}, set()
    for row in rows:
        key = (row["test"], row["session_slug"])
        if key in sessions:
            raise ValueError(f"duplicate ownership: {key} belongs to {sessions[key]} and {row['reader']}")
        sessions[key] = row["reader"]
        path = str(Path(row["record"]).resolve()).lower()
        if path in records:
            raise ValueError(f"duplicate ownership: record path {path} is assigned twice")
        records[path] = row["reader"]
        try:
            order = int(row["order"])
        except (TypeError, ValueError):
            raise ValueError(f"malformed order: {row['order']}") from None
        if order < 1 or (row["reader"], order) in orders:
            raise ValueError(f"duplicate or invalid order: {row['reader']} {order}")
        orders.add((row["reader"], order))


def select_rows(remaining: list[dict], closure: list[dict]) -> list[tuple[dict, str]]:
    keyed = {(r["test"], r["session_slug"]): r for r in closure}
    if len(keyed) != len(closure):
        raise ValueError("duplicate closure identifiers")
    candidates = {}
    for item in remaining:
        key = item["test"], item["session_identifier"]
        category = item["work_class"]
        if key not in keyed:
            raise ValueError(f"remaining session absent from closure: {key}")
        if key not in candidates or PRIORITY.get(category, 4) < PRIORITY.get(candidates[key], 4):
            candidates[key] = category
    buckets = defaultdict(list)
    for key, category in candidates.items():
        buckets[(PRIORITY.get(category, 4), category, key[0])].append(key)
    for bucket in buckets.values():
        bucket.sort(key=lambda k: (keyed[k]["source_sha256"], k[1]))
    keys = []
    for index in range(max(map(len, buckets.values()), default=0)):
        keys.extend(buckets[k][index] for k in sorted(buckets) if index < len(buckets[k]))
    return [(keyed[k], candidates[k]) for k in keys]


def planning_inputs() -> list[Path]:
    return [ROOT / relative for relative in INPUT_PATHS]


def prepare() -> dict:
    if STAGE.exists():
        raise ValueError("reading stage already exists; use migrate to preserve occupied records")
    inputs = planning_inputs()
    before = {str(p): digest(p) for p in inputs}
    closure = read_csv(inputs[1])
    keyed = {(r["test"], r["session_slug"]) for r in closure}
    if len(keyed) != len(closure) or not closure:
        raise ValueError("closure population is empty or contains duplicates")
    active = {(r["surface"], r["session_slug"]) for r in read_csv(inputs[2])}
    chosen = select_rows(read_csv(inputs[0]), closure)
    pending, _ = current_pending()
    if not chosen:
        raise ValueError("no pending sessions remain to assign; nothing was seeded")
    if {(r["test"], r["session_slug"]) for r, _ in chosen} != pending:
        raise ValueError("pending list changed during selection; nothing was seeded")
    manifest, selection, seeded = [], [], []
    order = Counter()
    for index, (original, reason) in enumerate(chosen):
        source = Path(original["source"]).resolve()
        if digest(source) != original["source_sha256"]:
            raise ValueError(f"source changed since closure inventory: {source}")
        prompt = source.with_name("prompt.txt" if original["test"] == "test01" else "prompt_1.txt")
        reader = READERS[index % len(READERS)]
        order[reader] += 1
        row = {
            "reader": reader, "order": str(order[reader]), "test": original["test"],
            "session_slug": original["session_slug"], "source": str(source),
            "source_sha256": digest(source), "prompt": str(prompt), "prompt_sha256": digest(prompt),
            "record": str(STAGE / "records" / original["test"] / (original["session_slug"] + ".json")),
        }
        manifest.append(row)
        selection.append({
            "test": row["test"], "session_slug": row["session_slug"],
            "selection_reason": reason, "source": row["source"],
            "source_sha256": row["source_sha256"], "reader": reader,
            "existing_engine_roster": str((row["test"], row["session_slug"]) in active).lower(),
        })
        seeded.append((Path(row["record"]), seed(row)))
    check_ownership(manifest)
    protected = {INSTRUCTIONS / "READER.md", INSTRUCTIONS / "FORMAT.md"}
    for folder in ("results/final_extracted_data", "results/normalized_data", "results/final_scored_data"):
        protected.update((ROOT / folder).glob("*.csv"))
    protected.update((ROOT / "results/final_scored_data/overrides").rglob("*.csv"))
    protected.update((ROOT / "scoring/override_queue/active").rglob("*.json"))
    for row in manifest:
        protected.update((Path(row["source"]), Path(row["prompt"])))
    protection = {str(p.resolve()): digest(p) for p in sorted(protected)}
    if any(digest(Path(p)) != value for p, value in before.items()):
        raise ValueError("planning inputs changed during selection; nothing was seeded")
    write_csv(STAGE / "manifest.csv", manifest, MANIFEST_FIELDS, new=True)
    for path, value in seeded:
        write_json_new(path, value)
    write_csv(ROOT / "scoring/tier1_reading_selection.csv", selection, list(selection[0]), new=True)
    population = [{"test": r["test"], "session_slug": r["session_slug"], "source_sha256": r["source_sha256"]} for r in closure]
    write_json_new(STAGE / "bindings.json", {
        "schema_version": VERSION, "manifest_sha256": digest(STAGE / "manifest.csv"),
        "input_hashes": before, "protected_files": protection, "population": population,
        "authorization": (
            f"{len(manifest)} Tier 1 source readings across {len(READERS)} disjoint assignments; "
            f"a {PILOT_TOTAL}-record pilot across workers precedes later checkpoints; no Tier 2 expansion"
        ),
        "readers": list(READERS),
    })
    write_json_new(STAGE / "review_approvals.json", approvals_template())
    write_json_new(STAGE / "dispatch_control.json", {
        "state": "HOLD",
        "reason": "Supervisor review of the reader plan and the twenty-record pilot is required.",
        "review_note": "", "manifest_sha256": digest(STAGE / "manifest.csv"),
    })
    verify_protection(protection)
    return {
        "prepared": len(manifest), "readers": dict(order), "completed": 0,
        "selection_reasons": dict(Counter(r["selection_reason"] for r in selection)),
        "protected_files": len(protection),
    }


def approvals_template() -> dict:
    return {
        "schema_version": APPROVALS_VERSION,
        "pilot_acceptance": {"accepted": False, "reviewer": "", "review_note": "", "accepted_records": []},
        "readers": {
            reader: {
                "released": False, "review_note": "", "authorized_orders": [],
                "remaining_work_sha256": "", "extraction_packs": [],
            }
            for reader in READERS
        },
    }


def load_approvals() -> dict:
    path = STAGE / "review_approvals.json"
    if not path.is_file():
        raise ValueError("review approvals are missing")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("malformed review approval")
    if "schema_version" not in value:
        readers = {}
        for reader, entry in value.items():
            readers[reader] = _approval_entry(entry, legacy=True)
        return {"schema_version": APPROVALS_VERSION,
                "pilot_acceptance": {"accepted": False, "reviewer": "", "review_note": "", "accepted_records": []},
                "readers": readers}
    if set(value) != {"schema_version", "pilot_acceptance", "readers"} or value["schema_version"] != APPROVALS_VERSION:
        raise ValueError("malformed review approval")
    pilot = value["pilot_acceptance"]
    if not isinstance(pilot, dict) or set(pilot) != {"accepted", "reviewer", "review_note", "accepted_records"}:
        raise ValueError("malformed pilot acceptance")
    if type(pilot["accepted"]) is not bool or any(not isinstance(pilot[k], str) for k in ("reviewer", "review_note")):
        raise ValueError("malformed pilot acceptance")
    if not isinstance(pilot["accepted_records"], list):
        raise ValueError("malformed pilot acceptance")
    if pilot["accepted"] and (not pilot["reviewer"].strip() or not pilot["review_note"].strip() or not pilot["accepted_records"]):
        raise ValueError("accepted pilot has no reviewer, note or record list")
    readers_value = value["readers"]
    if not isinstance(readers_value, dict):
        raise ValueError("malformed review approval")
    readers = {reader: _approval_entry(entry) for reader, entry in readers_value.items()}
    return {"schema_version": APPROVALS_VERSION, "pilot_acceptance": pilot, "readers": readers}


def _approval_entry(entry, legacy: bool = False) -> dict:
    if not isinstance(entry, dict):
        raise ValueError("malformed review approval")
    expected = {"released", "review_note", "authorized_orders", "remaining_work_sha256"}
    if set(entry) != expected and set(entry) != expected | {"extraction_packs"}:
        raise ValueError("malformed review approval")
    if type(entry["released"]) is not bool or not isinstance(entry["review_note"], str):
        raise ValueError("malformed review approval")
    if not isinstance(entry["remaining_work_sha256"], str):
        raise ValueError("malformed review approval")
    orders = entry["authorized_orders"]
    if (
        not isinstance(orders, list)
        or any(type(n) is not int or n < 1 for n in orders)
        or len(set(orders)) != len(orders)
    ):
        raise ValueError("malformed authorized orders")
    packs = entry.get("extraction_packs", [])
    if not isinstance(packs, list) or any(
        not isinstance(p, dict) or set(p) != {"path", "sha256"}
        or not isinstance(p["path"], str) or not isinstance(p["sha256"], str)
        for p in packs
    ):
        raise ValueError("malformed extraction packs")
    normalized = {
        "released": entry["released"], "review_note": entry["review_note"],
        "authorized_orders": list(orders), "remaining_work_sha256": entry["remaining_work_sha256"],
        "extraction_packs": [dict(p) for p in packs],
    }
    if normalized["released"]:
        if not normalized["review_note"].strip() or not normalized["remaining_work_sha256"]:
            raise ValueError("released assignment has no review note or pending-list binding")
    else:
        if normalized["authorized_orders"] or normalized["extraction_packs"]:
            raise ValueError("unreleased assignment cannot carry later orders or packs")
    return normalized


def save_approvals(value: dict) -> None:
    write_json(STAGE / "review_approvals.json", value)


def dispatch_control() -> dict:
    path = STAGE / "dispatch_control.json"
    if not path.is_file():
        return {"state": "HOLD", "reason": "Dispatch approval is missing.", "review_note": "", "manifest_sha256": ""}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or set(value) != {"state", "reason", "review_note", "manifest_sha256"}:
        raise ValueError("malformed dispatch control")
    if any(not isinstance(item, str) for item in value.values()) or value["state"] not in {"HOLD", "READY"}:
        raise ValueError("malformed dispatch control")
    if value["state"] == "READY" and (not value["review_note"].strip() or value["manifest_sha256"] != digest(STAGE / "manifest.csv")):
        raise ValueError("dispatch approval lacks a review note or the current manifest hash")
    return value


def require_dispatch_ready() -> None:
    control = dispatch_control()
    if control["state"] != "READY":
        raise ValueError("DISPATCH_HOLD: " + control["reason"])


def verify_protection(protection: dict[str, str]) -> None:
    changed = [p for p, value in protection.items() if not Path(p).is_file() or digest(Path(p)) != value]
    if changed:
        raise ValueError("protected files changed; do not restore them: " + json.dumps(changed))


def load_manifest(reader: str | None = None) -> tuple[list[dict], dict]:
    binding_path = STAGE / "bindings.json"
    if not binding_path.is_file():
        raise ValueError("bindings are missing; the stage is not prepared")
    binding = json.loads(binding_path.read_text(encoding="utf-8-sig"))
    if not isinstance(binding, dict) or not isinstance(binding.get("manifest_sha256"), str):
        raise ValueError("malformed bindings")
    if digest(STAGE / "manifest.csv") != binding["manifest_sha256"]:
        raise ValueError("assignment manifest changed")
    for path in (INSTRUCTIONS / "READER.md", INSTRUCTIONS / "FORMAT.md"):
        recorded = binding.get("input_hashes", {}).get(str(path))
        if recorded is None or digest(path) != recorded:
            raise ValueError(f"bound reading instructions changed: {path}")
    rows = read_csv(STAGE / "manifest.csv")
    check_ownership(rows)
    if reader:
        rows = [r for r in rows if r["reader"] == reader]
        if not rows:
            raise ValueError(f"reader has no assignment: {reader}")
    for r in rows:
        expected = STAGE / "records" / r["test"] / (r["session_slug"] + ".json")
        if Path(r["record"]).resolve() != expected.resolve():
            raise ValueError("record path is outside its assigned location")
    return rows, binding


def require_approvals_cover(rows: list[dict], approvals: dict) -> None:
    readers = {r["reader"] for r in rows}
    missing = sorted(readers - set(approvals["readers"]))
    if missing:
        raise ValueError("review approvals do not cover the assigned readers: " + json.dumps(missing))


def authorized_rows(reader: str | None) -> list[dict]:
    if dispatch_control()["state"] != "READY":
        return []
    rows, _ = load_manifest(reader)
    approvals = load_approvals()
    require_approvals_cover(rows, approvals)
    return [
        r for r in rows
        if int(r["order"]) in approvals["readers"][r["reader"]]["authorized_orders"]
    ]


def current_pending() -> tuple[set[tuple[str, str]], str]:
    path = ROOT / "results/scoring_review/remaining_work.csv"
    status = ROOT / "scoring/CLOSURE_STATUS.md"
    before = digest(path), digest(status)
    pending = {(r["test"], r["session_identifier"]) for r in read_csv(path)}
    reported = [line.split("|")[2].strip() for line in read_text(status).splitlines()
                if line.startswith("| Pending sessions |")]
    if reported != [str(len(pending))] or before != (digest(path), digest(status)):
        raise ValueError("pending list and status disagree or changed during reading; wait for the coding agent")
    return pending, before[0]


def pack_grade_columns(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        try:
            header = next(reader)
        except StopIteration:
            return []
    return [name for name in header if any(marker in name.lower() for marker in GRADE_MARKERS)]


def register_extraction_pack(entry: dict, pack: str) -> None:
    path = Path(pack)
    if not path.is_file():
        raise ValueError("extraction pack is not a file")
    forbidden = pack_grade_columns(path)
    if forbidden:
        raise ValueError("extraction pack contains grade columns: " + ", ".join(forbidden))
    pair = {"path": str(path.resolve()), "sha256": digest(path)}
    if pair not in entry["extraction_packs"]:
        entry["extraction_packs"].append(pair)


def release(reader: str, note: str, limit: int | None = None, extraction_pack: str | None = None) -> dict:
    if not note.strip():
        raise ValueError("a supervisor source-review note is required")
    require_dispatch_ready()
    rows, _ = load_manifest(reader)
    rows = [r for r in rows if r["reader"] == reader]
    approvals = load_approvals()
    require_approvals_cover(rows, approvals)
    entry = approvals["readers"][reader]
    pilot = approvals["pilot_acceptance"]
    pending, pending_hash = current_pending()
    by_order = {int(r["order"]): r for r in rows}
    for order in entry["authorized_orders"]:
        row = by_order.get(order)
        if row is None:
            raise ValueError("authorized order is not in the manifest")
        record = json.loads(Path(row["record"]).read_text(encoding="utf-8-sig"))
        if record.get("record_status") != "complete":
            raise ValueError(f"prior authorized record is not complete: {row['record']}")
        errors = validate_record(record, row, authorized_packs=entry["extraction_packs"])
        if errors:
            raise ValueError(f"prior authorized record is not valid: {row['record']}:{json.dumps(errors)}")
    if not pilot["accepted"]:
        authorized_total = sum(len(e["authorized_orders"]) for e in approvals["readers"].values())
        budget = PILOT_TOTAL - authorized_total
        if budget <= 0:
            raise ValueError(
                "the twenty-record pilot is fully authorized; supervisor pilot acceptance is required before further release"
            )
        batch = budget if limit is None else min(limit, budget)
    else:
        batch = CHECKPOINT if limit is None else min(limit, CHECKPOINT)
    if batch < 1:
        raise ValueError("a release must authorize at least one record")
    already = set(entry["authorized_orders"])
    candidates = [by_order[o] for o in sorted(by_order) if o not in already]
    unresolved = [r for r in candidates if (r["test"], r["session_slug"]) in pending]
    new_orders = [int(r["order"]) for r in unresolved[:batch]]
    if not new_orders:
        raise ValueError("no unresolved pending orders remain for this reader")
    if extraction_pack:
        register_extraction_pack(entry, extraction_pack)
    if digest(ROOT / "results/scoring_review/remaining_work.csv") != pending_hash:
        raise ValueError("pending list changed before release; retry after the coding agent finishes")
    entry.update({
        "released": True, "review_note": note,
        "authorized_orders": sorted(already | set(new_orders)),
        "remaining_work_sha256": pending_hash,
    })
    save_approvals(approvals)
    authorized_total = sum(len(e["authorized_orders"]) for e in approvals["readers"].values())
    return {
        "reader": reader, "authorized_records": len(new_orders),
        "authorized_total": len(entry["authorized_orders"]),
        "pilot_records_authorized": authorized_total,
        "pilot_budget_remaining": max(0, PILOT_TOTAL - authorized_total),
        "resolved_unstarted_omitted": len(candidates) - len(unresolved),
        "remaining_unauthorized": len(unresolved) - len(new_orders),
        "review_note": note,
    }


def accept_pilot(reviewer: str, note: str) -> dict:
    if not reviewer.strip():
        raise ValueError("a pilot reviewer identity is required")
    if not note.strip():
        raise ValueError("a supervisor pilot-acceptance note is required")
    require_dispatch_ready()
    rows, _ = load_manifest(None)
    approvals = load_approvals()
    require_approvals_cover(rows, approvals)
    if reviews_own_work(reviewer, rows):
        raise ValueError("the pilot reviewer must be separate from the readers")
    pilot = approvals["pilot_acceptance"]
    if pilot["accepted"]:
        raise ValueError("the pilot is already accepted; retain its reviewer and note")
    by_reader_order = {(r["reader"], int(r["order"])): r for r in rows}
    accepted = []
    for reader, entry in approvals["readers"].items():
        for order in entry["authorized_orders"]:
            row = by_reader_order.get((reader, order))
            if row is None:
                raise ValueError("authorized order is not in the manifest")
            record = json.loads(Path(row["record"]).read_text(encoding="utf-8-sig"))
            errors = validate_record(record, row, authorized_packs=entry["extraction_packs"])
            if record.get("record_status") != "complete" or errors:
                raise ValueError(
                    f"pilot record is not complete or valid: {row['record']}:{json.dumps(errors)}"
                )
            accepted.append({
                "test": row["test"], "session_slug": row["session_slug"],
                "record": row["record"], "record_sha256": digest(Path(row["record"])),
            })
    if len(accepted) != PILOT_TOTAL:
        raise ValueError(
            f"pilot acceptance requires exactly {PILOT_TOTAL} authorized complete records; found {len(accepted)}"
        )
    pilot.update({"accepted": True, "reviewer": reviewer, "review_note": note, "accepted_records": accepted})
    save_approvals(approvals)
    return {"accepted_records": len(accepted), "reviewer": reviewer, "review_note": note}


def reviews_own_work(reviewer: str, rows: list[dict]) -> bool:
    return reviewer in {r["reader"] for r in rows}


def validate_record(record: dict, row: dict, *, allow_incomplete: bool = False, authorized_packs: list | None = None) -> list[str]:
    errors: list[str] = []

    def require(condition, code):
        if not condition:
            errors.append(code)

    if not isinstance(record, dict):
        return ["RECORD_NOT_OBJECT"]
    version = record.get("schema_version")
    if version == VERSION:
        keys = TOP_KEYS
    elif version in LEGACY_VERSIONS:
        keys = LEGACY_TOP_KEYS
    else:
        return ["SCHEMA_VERSION"]
    require(set(record) == keys, "RECORD_FIELDS")
    for key in BOUND_FIELDS:
        require(record.get(key) == row[key], f"BOUND_FIELD:{key}")
    source_texts = {}
    for kind in ("source", "prompt"):
        path = Path(row[kind])
        require(path.is_file() and digest(path) == row[f"{kind}_sha256"], f"SOURCE_HASH:{kind}")
        if path.is_file():
            source_texts["response" if kind == "source" else "prompt"] = read_text(path)
    if errors:
        return sorted(set(errors))
    status = record.get("record_status")
    require(status in RECORD_STATES, "RECORD_STATUS")
    require(type(record.get("read_complete")) is bool, "READ_COMPLETE_TYPE")
    require(isinstance(record.get("reader_notes"), str), "READER_NOTES_TYPE")
    if status != "complete" and not allow_incomplete:
        errors.append("RECORD_INCOMPLETE")
    exposure = record.get("exposure")
    require(isinstance(exposure, dict) and set(exposure) == {"status", "details"}, "EXPOSURE_FIELDS")
    if isinstance(exposure, dict):
        require(exposure.get("status") in EXPOSURE_STATES, "EXPOSURE_STATUS")
        require(isinstance(exposure.get("details"), str), "EXPOSURE_DETAILS_TYPE")
        if exposure.get("status") not in {"none", "undeclared"}:
            require(bool(str(exposure.get("details", "")).strip()), "EXPOSURE_DETAILS_REQUIRED")
        if status == "complete":
            require(exposure.get("status") != "undeclared", "EXPOSURE_UNDECLARED")
    if status == "complete":
        require(record.get("read_complete") is True, "FULL_READING_NOT_ATTESTED")
    quotes = {}
    evidence = record.get("evidence")
    require(isinstance(evidence, list), "EVIDENCE_NOT_LIST")
    for q in evidence if isinstance(evidence, list) else []:
        if not isinstance(q, dict) or set(q) != {"id", "source", "text", "occurrence"}:
            errors.append("EVIDENCE_FIELDS")
            continue
        require(isinstance(q["id"], str) and bool(q["id"]) and q["id"] not in quotes, "EVIDENCE_ID")
        text = q["text"]
        require(isinstance(text, str) and bool(text.strip()), f"EMPTY_QUOTE:{q['id']}")
        origin = source_texts.get(q["source"])
        require(origin is not None, f"QUOTE_SOURCE:{q['id']}")
        require(type(q["occurrence"]) is int and q["occurrence"] > 0, f"QUOTE_OCCURRENCE:{q['id']}")
        positions: list[int] = []
        if origin is not None and isinstance(text, str) and text and type(q["occurrence"]) is int:
            count, cursor = 0, 0
            while True:
                cursor = origin.find(text, cursor)
                if cursor < 0:
                    break
                count += 1
                positions.append(cursor)
                cursor += 1
            require(0 < q["occurrence"] <= count, f"QUOTE_NOT_EXACT:{q['id']}")
        if isinstance(q["id"], str):
            quotes[q["id"]] = dict(q)
            if positions and 0 < q["occurrence"] <= len(positions):
                start = positions[q["occurrence"] - 1]
                quotes[q["id"]]["_lines"] = (
                    origin[:start].count("\n") + 1,
                    origin[:start + len(text)].count("\n") + 1,
                )
    items = record.get("claims")
    require(isinstance(items, list), "CLAIMS_NOT_LIST")
    claims = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or set(item) != CLAIM_KEYS:
            errors.append("CLAIM_FIELDS")
            continue
        cid = item["id"]
        if not isinstance(cid, str) or not cid or cid in claims:
            errors.append("CLAIM_ID")
            continue
        claims[cid] = item
        require(item["kind"] in KINDS, f"CLAIM_KIND:{cid}")
        require(item["stance"] in STANCES, f"CLAIM_STANCE:{cid}")
        refs = item["evidence_ids"]
        require(isinstance(refs, list) and bool(refs) and all(isinstance(x, str) and x in quotes for x in refs), f"CLAIM_EVIDENCE:{cid}")
        if isinstance(refs, list):
            require(any(quotes.get(x, {}).get("source") == "response" for x in refs if isinstance(x, str)), f"RESPONSE_EVIDENCE_REQUIRED:{cid}")
        require(isinstance(item["related_to"], list), f"CLAIM_LINKS:{cid}")
        require(isinstance(item["details"], list), f"DETAILS_NOT_LIST:{cid}")
        for detail in item["details"] if isinstance(item["details"], list) else []:
            if not isinstance(detail, dict) or set(detail) != {"field", "value", "evidence_ids"}:
                errors.append(f"DETAIL_FIELDS:{cid}")
                continue
            require(detail["field"] in DETAIL_FIELDS, f"DETAIL_FIELD_NAME:{cid}")
            refs2 = detail["evidence_ids"]
            require(isinstance(refs2, list) and bool(refs2) and all(isinstance(x, str) and x in quotes for x in refs2), f"DETAIL_EVIDENCE:{cid}")
            value = detail["value"]
            require(isinstance(value, str) and bool(value.strip()), f"DETAIL_VALUE:{cid}")
            if isinstance(refs2, list) and isinstance(value, str):
                require(any(quotes[x]["source"] == "response" and value in quotes[x]["text"] for x in refs2 if isinstance(x, str) and x in quotes), f"DETAIL_NOT_VERBATIM:{cid}")
        absent = item["unstated_fields"]
        require(isinstance(absent, list) and all(isinstance(x, str) and x in DETAIL_FIELDS for x in absent), f"UNSTATED_FIELDS:{cid}")
        if isinstance(absent, list) and isinstance(item["details"], list):
            require(not (set(absent) & {d.get("field") for d in item["details"] if isinstance(d, dict)}), f"STATED_AND_UNSTATED:{cid}")
            if status == "complete" and item["kind"] == "method_offer":
                accounted = set(absent) | {d.get("field") for d in item["details"] if isinstance(d, dict)}
                require({"method_name", "object", "domain", "comparison", "scope", "conditions", "conclusion", "justification"} <= accounted, f"METHOD_DETAILS_UNACCOUNTED:{cid}")
    if version == VERSION:
        protocol = record.get("reading_protocol")
        require(isinstance(protocol, dict) and set(protocol) == PROTOCOL_KEYS, "READING_PROTOCOL_FIELDS")
        if isinstance(protocol, dict) and set(protocol) == PROTOCOL_KEYS:
            require(type(protocol["source_read_before_extraction"]) is bool, "SOURCE_FIRST_TYPE")
            require(isinstance(protocol["extraction_pack"], str), "PACK_PATH_TYPE")
            require(isinstance(protocol["extraction_pack_sha256"], str), "PACK_HASH_TYPE")
            require(type(protocol["comparison_exposure"]) is bool, "COMPARISON_EXPOSURE_TYPE")
            packed = bool(protocol["extraction_pack"]) or bool(protocol["extraction_pack_sha256"])
            if packed:
                require(bool(protocol["extraction_pack"]) and bool(protocol["extraction_pack_sha256"]), "COMPARISON_PACK_REQUIRED")
                require(protocol["comparison_exposure"] is True, "COMPARISON_PACK_UNBOUND")
                if protocol["extraction_pack"] and protocol["extraction_pack_sha256"]:
                    pack = Path(protocol["extraction_pack"])
                    require(pack.is_file(), "COMPARISON_PACK_MISSING")
                    if pack.is_file():
                        require(digest(pack) == protocol["extraction_pack_sha256"], "COMPARISON_PACK_HASH")
                    if authorized_packs is not None:
                        allowed = {
                            (str(Path(p.get("path", "")).resolve()), str(p.get("sha256", "")))
                            for p in authorized_packs if isinstance(p, dict)
                        }
                        require((str(pack.resolve()), protocol["extraction_pack_sha256"]) in allowed, "COMPARISON_PACK_NOT_AUTHORIZED")
                    require(protocol["source_read_before_extraction"] is True, "SOURCE_FIRST_REQUIRED")
        comparison = record.get("comparison")
        require(isinstance(comparison, dict) and set(comparison) == COMPARISON_KEYS, "COMPARISON_FIELDS")
        if isinstance(comparison, dict) and set(comparison) == COMPARISON_KEYS:
            cstatus = comparison["status"]
            require(cstatus in COMPARISON_STATES, "COMPARISON_STATUS")
            cfields = comparison["fields"]
            require(isinstance(cfields, list) and all(isinstance(x, str) and x in DETAIL_FIELDS for x in cfields), "COMPARISON_DETAIL_FIELDS")
            require(isinstance(comparison["notes"], str), "COMPARISON_NOTES_TYPE")
            refs3 = comparison["evidence_ids"]
            valid3 = isinstance(refs3, list) and all(isinstance(x, str) and x in quotes for x in refs3)
            require(valid3, "COMPARISON_EVIDENCE")
            if cstatus in COMPARISON_STATES and cstatus != UNREVIEWED:
                if isinstance(cfields, list):
                    if cstatus == "consistent":
                        require(not cfields, "COMPARISON_FIELDS_UNEXPECTED")
                    else:
                        require(bool(cfields), "COMPARISON_FIELDS_REQUIRED")
                if valid3:
                    require(bool(refs3) and any(quotes.get(x, {}).get("source") == "response" for x in refs3), "COMPARISON_EVIDENCE_REQUIRED")
                require(bool(claims), "SOURCE_OBSERVATIONS_REQUIRED")
                if isinstance(protocol, dict):
                    require(
                        protocol.get("comparison_exposure") is True and bool(protocol.get("extraction_pack")),
                        "COMPARISON_PACK_REQUIRED",
                    )
            elif cstatus == UNREVIEWED:
                if isinstance(cfields, list):
                    require(not cfields, "COMPARISON_FIELDS_UNEXPECTED")
                if isinstance(refs3, list):
                    require(not refs3, "COMPARISON_EVIDENCE_UNEXPECTED")
        adjudication = record.get("adjudication")
        require(isinstance(adjudication, dict) and set(adjudication) == ADJUDICATION_KEYS, "ADJUDICATION_FIELDS")
        if isinstance(adjudication, dict) and set(adjudication) == ADJUDICATION_KEYS:
            astatus = adjudication["status"]
            require(astatus in ADJUDICATION_STATES, "ADJUDICATION_STATUS")
            for field in ("reviewer", "decision", "accepted_evidence_ref"):
                require(isinstance(adjudication[field], str), f"ADJUDICATION_TYPE:{field}")
            if astatus in ADJUDICATION_STATES and astatus != UNREVIEWED:
                if isinstance(adjudication["reviewer"], str):
                    require(bool(adjudication["reviewer"].strip()), "ADJUDICATION_REVIEWER_REQUIRED")
                    require(adjudication["reviewer"] != record.get("reader"), "ADJUDICATION_REVIEWER_IS_READER")
                if isinstance(adjudication["decision"], str):
                    require(bool(adjudication["decision"].strip()), "ADJUDICATION_DECISION_REQUIRED")
                if astatus == "accepted" and isinstance(adjudication["accepted_evidence_ref"], str):
                    require(bool(adjudication["accepted_evidence_ref"].strip()), "ADJUDICATION_REF_REQUIRED")
        if status == "complete":
            require(
                isinstance(protocol, dict) and protocol.get("source_read_before_extraction") is True,
                "SOURCE_FIRST_NOT_ATTESTED",
            )
    for cid, item in claims.items():
        if isinstance(item["related_to"], list):
            require(all(isinstance(x, str) and x in claims for x in item["related_to"]), f"UNKNOWN_CLAIM_LINK:{cid}")
    expected = blocks(source_texts["response"])
    coverage = record.get("coverage")
    require(isinstance(coverage, list) and len(coverage) == len(expected), "BLOCK_COVERAGE_LENGTH")
    covered = set()
    if isinstance(coverage, list):
        for got, want in zip(coverage, expected):
            if not isinstance(got, dict) or set(got) != set(want):
                errors.append("COVERAGE_FIELDS")
                continue
            for key in ("block_id", "start_line", "end_line", "sha256"):
                require(got[key] == want[key], f"BOUND_BLOCK:{want['block_id']}:{key}")
            require(got["role"] in {"unread", "mathematical", "non_mathematical", "mixed", "unclear"}, "BLOCK_ROLE")
            refs = got["claim_ids"]
            valid_refs = isinstance(refs, list) and all(isinstance(x, str) and x in claims for x in refs)
            require(valid_refs, f"BLOCK_CLAIM_IDS:{want['block_id']}")
            if valid_refs:
                covered.update(refs)
            if status == "complete":
                require(got["role"] != "unread", f"UNREAD_BLOCK:{want['block_id']}")
                if got["role"] in {"mathematical", "mixed", "unclear"}:
                    require(bool(refs), f"UNLINKED_MATH_BLOCK:{want['block_id']}")
                    for cid in refs if valid_refs else []:
                        cited = [quotes[qid] for qid in claims[cid]["evidence_ids"] if isinstance(qid, str) and qid in quotes]
                        require(any(q["source"] == "response" and "_lines" in q and q["_lines"][0] <= want["end_line"] and q["_lines"][1] >= want["start_line"] for q in cited), f"BLOCK_QUOTE_NOT_LOCAL:{want['block_id']}:{cid}")
                if got["role"] == "non_mathematical":
                    require(not refs, f"NONMATH_HAS_CLAIMS:{want['block_id']}")
    if status == "complete":
        require(set(claims) <= covered, "CLAIM_WITHOUT_COVERAGE")
    return sorted(set(errors))


def comparison_value(record: dict, key: str, default):
    value = record.get("comparison")
    if isinstance(value, dict) and key in value:
        return value[key]
    return default


def adjudication_value(record: dict, key: str, default: str = "") -> str:
    value = record.get("adjudication")
    if isinstance(value, dict) and isinstance(value.get(key), str):
        return value[key]
    return default


def supplement_json(record: dict) -> str:
    return json_text({
        "claims": record.get("claims", []),
        "evidence": record.get("evidence", []),
        "reader_notes": record.get("reader_notes", ""),
    })


def inspect(reader: str | None, record_path: str | None, allow_incomplete: bool) -> tuple[dict, list[tuple[dict, dict]]]:
    rows, _ = load_manifest(reader)
    control = dispatch_control()
    approvals = load_approvals()
    authorized = {r["record"]: r for r in authorized_rows(reader)}
    if record_path:
        selected = Path(record_path).resolve()
        rows = [r for r in rows if Path(r["record"]).resolve() == selected]
        if not rows:
            raise ValueError("record is not owned by this reader")
    counts, invalid, complete = Counter(), [], []
    per_reader = {}
    for row in rows:
        owner = per_reader.setdefault(row["reader"], {
            "assigned": 0, "authorized_orders": [], "valid_completed": 0, "issues": 0,
            "states": Counter(), "next_record": None,
            "released": bool(approvals["readers"].get(row["reader"], {}).get("released")),
        })
        owner["assigned"] += 1
        entry = approvals["readers"].get(row["reader"], {})
        packs = entry.get("extraction_packs", []) if isinstance(entry, dict) else []
        if row["record"] in authorized:
            owner["authorized_orders"].append(int(row["order"]))
        try:
            data = json.loads(Path(row["record"]).read_text(encoding="utf-8-sig"))
            errors = validate_record(data, row, allow_incomplete=allow_incomplete or row["record"] not in authorized, authorized_packs=packs)
            if control["state"] == "READY" and row["record"] not in authorized and isinstance(data, dict):
                exposed = bool(
                    isinstance(data.get("reading_protocol"), dict)
                    and data["reading_protocol"].get("comparison_exposure")
                )
                if data.get("record_status") != "pending" or exposed:
                    errors.append("RECORD_NOT_AUTHORIZED")
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, KeyError) as exc:
            data, errors = {}, [f"UNREADABLE_OR_MALFORMED:{exc}"]
        if not isinstance(data, dict):
            data = {}
        counts[data.get("record_status", "invalid")] += 1
        owner["states"][data.get("record_status", "invalid")] += 1
        if row["record"] in authorized and data.get("record_status") != "complete" and owner["next_record"] is None:
            owner["next_record"] = row["record"]
        if errors:
            invalid.append({"record": row["record"], "errors": sorted(set(errors))})
            owner["issues"] += 1
        elif data.get("record_status") == "complete":
            complete.append((row, data))
            owner["valid_completed"] += 1
    pilot = approvals["pilot_acceptance"]
    authorized_total = sum(len(e["authorized_orders"]) for e in approvals["readers"].values())
    return {
        "dispatch": control, "assigned": len(rows),
        "currently_authorized": sum(r["record"] in authorized for r in rows),
        "states": dict(counts), "valid_completed": len(complete), "per_reader": per_reader,
        "pilot": {
            "accepted": pilot["accepted"], "authorized_total": authorized_total,
            "budget_remaining": max(0, PILOT_TOTAL - authorized_total),
        },
        "issues": invalid,
    }, complete


def export(require_complete: bool) -> dict:
    require_dispatch_ready()
    report, records = inspect(None, None, not require_complete)
    if report["issues"]:
        raise ValueError("export refused: " + json.dumps(report["issues"]))
    manifest, binding = load_manifest()
    raw = []
    for row, record in records:
        raw.append({
            **{key: row[key] for key in ("test", "session_slug", "source", "source_sha256", "prompt", "prompt_sha256", "reader", "record")},
            "schema_version": record.get("schema_version", VERSION),
            "record_sha256": digest(Path(row["record"])),
            "exposure_json": json_text(record["exposure"]),
            "claims_json": json_text(record["claims"]),
            "evidence_json": json_text(record["evidence"]),
            "coverage_json": json_text(record["coverage"]),
            "reader_notes": record["reader_notes"],
            "additional_reading": supplement_json(record),
            "discrepancy_status": comparison_value(record, "status", UNREVIEWED),
            "discrepancy_fields": ";".join(comparison_value(record, "fields", [])),
            "adjudication_status": adjudication_value(record, "status", UNREVIEWED),
            "accepted_evidence_ref": adjudication_value(record, "accepted_evidence_ref"),
        })
    by_key = {(r["test"], r["session_slug"]): r for r in raw}
    assigned = {(r["test"], r["session_slug"]) for r in manifest}
    normalized = []
    for identity in binding["population"]:
        key = identity["test"], identity["session_slug"]
        evidence = by_key.get(key)
        exposure = json.loads(evidence["exposure_json"])["status"] if evidence else None
        state = ("source_transcribed" if exposure == "none" else "source_transcribed_exposed") if evidence else ("awaiting_reading" if key in assigned else "not_assigned")
        normalized.append({
            **identity,
            "t1_evidence_status": state,
            "t1_schema_version": evidence["schema_version"] if evidence else VERSION,
            "t1_reader": evidence["reader"] if evidence else "",
            "t1_record": evidence["record"] if evidence else "",
            "t1_record_sha256": evidence["record_sha256"] if evidence else "",
            "t1_claims_json": evidence["claims_json"] if evidence else "",
            "t1_evidence_json": evidence["evidence_json"] if evidence else "",
            "t1_coverage_json": evidence["coverage_json"] if evidence else "",
            "t1_exposure_json": evidence["exposure_json"] if evidence else "",
            "additional_reading": evidence["additional_reading"] if evidence else "",
            "discrepancy_status": evidence["discrepancy_status"] if evidence else UNREVIEWED,
            "discrepancy_fields": evidence["discrepancy_fields"] if evidence else "",
            "adjudication_status": evidence["adjudication_status"] if evidence else UNREVIEWED,
            "accepted_evidence_ref": evidence["accepted_evidence_ref"] if evidence else "",
        })
    raw_path = ROOT / "results/final_extracted_data/tier1_source_evidence.csv"
    normalized_path = ROOT / "results/scoring_review/tier1_source_evidence.csv"
    write_csv(raw_path, raw, RAW_FIELDS)
    write_csv(normalized_path, normalized, [
        "test", "session_slug", "source_sha256",
    ] + NORMALIZED_FIELDS)
    protection = binding.get("protected_files", {})
    if protection:
        verify_protection(protection)
    return {
        "completed_raw_rows": len(raw), "normalized_population_rows": len(normalized),
        "raw_output": str(raw_path), "normalized_candidate": str(normalized_path),
        "grades_written": 0, "protected_files_verified": len(protection),
    }


def migrate(note: str, *, extend: bool = False, rebalance: bool = False) -> dict:
    if not isinstance(note, str) or not note.strip():
        raise ValueError("a supervisor migration note is required")
    manifest_path = STAGE / "manifest.csv"
    bindings_path = STAGE / "bindings.json"
    if not manifest_path.is_file() or not bindings_path.is_file():
        raise ValueError("no bound reading stage to migrate; use prepare")
    binding = json.loads(bindings_path.read_text(encoding="utf-8-sig"))
    if not isinstance(binding, dict) or not isinstance(binding.get("manifest_sha256"), str):
        raise ValueError("malformed bindings; nothing was changed")
    if digest(manifest_path) != binding["manifest_sha256"]:
        raise ValueError("manifest does not match its bindings; nothing was changed")
    control = dispatch_control()
    if control["state"] != "HOLD":
        raise ValueError("migration requires the dispatch control in HOLD")
    rows = read_csv(manifest_path)
    check_ownership(rows)
    protected = binding.get("protected_files", {})
    instruction_paths = {str((INSTRUCTIONS / name).resolve()) for name in ("READER.md", "FORMAT.md")}
    manifest_files = set()
    for _row in rows:
        manifest_files.add(str(Path(_row["source"]).resolve()))
        manifest_files.add(str(Path(_row["prompt"]).resolve()))
    changed = [
        p for p, value in protected.items()
        if str(Path(p).resolve()) not in instruction_paths
        and str(Path(p).resolve()) not in manifest_files
        and (not Path(p).is_file() or digest(Path(p)) != value)
    ]
    if changed:
        raise ValueError("protected files changed; do not restore them: " + json.dumps(changed))
    approvals = load_approvals()
    if rebalance and any(e.get("released") for e in approvals["readers"].values()):
        raise ValueError("a released assignment cannot be rebalanced")
    manifest_rows = [dict(r) for r in rows]
    reassignable = []
    for index, row in enumerate(manifest_rows):
        record_path = Path(row["record"])
        if not record_path.is_file():
            raise ValueError(f"missing record: {record_path}")
        try:
            record = json.loads(record_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"unreadable record: {record_path}:{exc}") from None
        for key in BOUND_FIELDS:
            if not isinstance(record, dict) or record.get(key) != row[key]:
                raise ValueError(f"record differs from its manifest row: {row['record']}:{key}")
        if digest(Path(row["source"])) != row["source_sha256"]:
            raise ValueError(f"stale source hash: {row['source']}")
        if digest(Path(row["prompt"])) != row["prompt_sha256"]:
            raise ValueError(f"stale prompt hash: {row['prompt']}")
        if rebalance and is_pristine_seed(record):
            reassignable.append(index)
    counts = Counter()
    reassignable_set = set(reassignable)
    for index, row in enumerate(manifest_rows):
        if index not in reassignable_set:
            counts[row["reader"]] += 1
    reassigned = 0
    for index in reassignable:
        row = manifest_rows[index]
        reader = min(READERS, key=lambda name: (counts[name], READERS.index(name)))
        counts[reader] += 1
        row["reader"] = reader
        value = seed(row)
        write_json(Path(row["record"]), value)
        reassigned += 1
    if rebalance:
        order = Counter()
        for row in manifest_rows:
            order[row["reader"]] += 1
            row["order"] = str(order[row["reader"]])
    added = []
    if extend:
        closure = read_csv(ROOT / "scoring/override_queue/closure_sessions.csv")
        closure_map = {(r["test"], r["session_slug"]): r for r in closure}
        if len(closure_map) != len(closure):
            raise ValueError("duplicate closure identifiers")
        owned = {(r["test"], r["session_slug"]) for r in manifest_rows}
        pending = read_csv(ROOT / "results/scoring_review/remaining_work.csv")
        candidates, seen = [], set()
        for item in pending:
            key = item["test"], item["session_identifier"]
            if key in seen or key in owned or key not in closure_map:
                continue
            seen.add(key)
            candidates.append((key, closure_map[key]))
        candidates.sort(key=lambda item: (item[0][0], item[1]["source_sha256"], item[0][1]))
        for key, original in candidates:
            source = Path(original["source"]).resolve()
            if not source.is_file() or digest(source) != original["source_sha256"]:
                raise ValueError(f"stale source hash for new session: {key}")
            prompt = source.with_name("prompt.txt" if original["test"] == "test01" else "prompt_1.txt")
            if not prompt.is_file():
                raise ValueError(f"missing prompt for new session: {key}")
            reader = min(READERS, key=lambda name: (counts[name], READERS.index(name)))
            counts[reader] += 1
            row = {
                "reader": reader, "order": str(counts[reader]), "test": original["test"],
                "session_slug": original["session_slug"], "source": str(source),
                "source_sha256": original["source_sha256"], "prompt": str(prompt),
                "prompt_sha256": digest(prompt),
                "record": str(STAGE / "records" / original["test"] / (original["session_slug"] + ".json")),
            }
            if Path(row["record"]).exists():
                raise ValueError(f"record already exists outside the manifest: {row['record']}")
            write_json_new(Path(row["record"]), seed(row))
            manifest_rows.append(row)
            added.append(row)
    check_ownership(manifest_rows)
    write_csv(manifest_path, manifest_rows, MANIFEST_FIELDS)
    input_hashes = {}
    for path in planning_inputs():
        if path.is_file():
            input_hashes[str(path)] = digest(path)
    new_protected = dict(protected)
    for name in ("READER.md", "FORMAT.md"):
        path = INSTRUCTIONS / name
        new_protected[str(path)] = digest(path)
    for row in manifest_rows:
        new_protected[row["source"]] = row["source_sha256"]
        new_protected[row["prompt"]] = row["prompt_sha256"]
    population = binding.get("population")
    if extend or not isinstance(population, list):
        closure = read_csv(ROOT / "scoring/override_queue/closure_sessions.csv")
        population = [
            {"test": r["test"], "session_slug": r["session_slug"], "source_sha256": r["source_sha256"]}
            for r in closure
        ]
    write_json(bindings_path, {
        "schema_version": VERSION,
        "migrated_from": binding.get("schema_version", "unknown"),
        "migration_note": note,
        "manifest_sha256": digest(manifest_path),
        "input_hashes": input_hashes,
        "protected_files": new_protected,
        "population": population,
        "authorization": (
            f"{len(manifest_rows)} Tier 1 source readings across {len(READERS)} disjoint assignments; "
            f"a {PILOT_TOTAL}-record pilot across workers precedes later checkpoints; no Tier 2 expansion"
        ),
        "readers": list(READERS),
    })
    for name in READERS:
        approvals["readers"].setdefault(name, {
            "released": False, "review_note": "", "authorized_orders": [],
            "remaining_work_sha256": "", "extraction_packs": [],
        })
    save_approvals(approvals)
    write_json(STAGE / "dispatch_control.json", {
        "state": "HOLD", "reason": control["reason"],
        "review_note": control["review_note"], "manifest_sha256": digest(manifest_path),
    })
    verify_protection(new_protected)
    return {
        "preserved_records": len(rows), "reassigned_unstarted": reassigned,
        "added_records": len(added), "readers": dict(counts), "migration_note": note,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    for name in ("status", "validate"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--reader")
        cmd.add_argument("--record")
        if name == "validate":
            cmd.add_argument("--allow-incomplete", action="store_true")
    out = sub.add_parser("export")
    out.add_argument("--require-complete", action="store_true")
    sub.add_parser("verify-protection")
    approval = sub.add_parser("release")
    approval.add_argument("--reader", required=True)
    approval.add_argument("--review-note", required=True)
    approval.add_argument("--limit", type=int)
    approval.add_argument("--extraction-pack")
    accept = sub.add_parser("accept-pilot")
    accept.add_argument("--reviewer", required=True)
    accept.add_argument("--review-note", required=True)
    move = sub.add_parser("migrate")
    move.add_argument("--review-note", required=True)
    move.add_argument("--extend", action="store_true")
    move.add_argument("--rebalance-unstarted", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare()
        elif args.command == "export":
            result = export(args.require_complete)
        elif args.command == "release":
            result = release(args.reader, args.review_note, args.limit, args.extraction_pack)
        elif args.command == "accept-pilot":
            result = accept_pilot(args.reviewer, args.review_note)
        elif args.command == "migrate":
            result = migrate(args.review_note, extend=args.extend, rebalance=args.rebalance_unstarted)
        elif args.command == "verify-protection":
            _, binding = load_manifest()
            protection = binding.get("protected_files", {})
            verify_protection(protection)
            result = {"protected_files_verified": len(protection)}
        else:
            if args.command == "validate":
                require_dispatch_ready()
            result, _ = inspect(args.reader, args.record, args.command == "status" or args.allow_incomplete)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("issues") else 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    csv.field_size_limit(2**31 - 1)
    raise SystemExit(main())
