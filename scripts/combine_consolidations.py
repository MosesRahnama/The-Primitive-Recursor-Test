r"""Mechanical per-batch consolidation combiner for ALL benchmark tests.

For a given test, merges each batch's per-round consolidation CSVs
(`<PREFIX>_r1_consolidation.csv`, `<PREFIX>_r2_consolidation.csv`, ...) into one
wide `<PREFIX>_batch_XXX_final_consolidation.csv` with columns prefixed
`r1__`, `r2__`, ... plus a full mechanical audit
(`<PREFIX>_batch_XXX_final_consolidation_audit.txt`).

This is the shared, test-parameterized engine that replaced the historical
per-test batch combiners; the merge semantics and gates carry over unchanged:

  * header duplication check per input;
  * session_slug presence + duplicate check per input;
  * slug ORDER identity across all rounds (hard fail on mismatch);
  * controlled-vocabulary validation of every coded cell, with the allowed
    sets pulled from the test's own pipeline ROUNDS definition (never a
    hand-copied list that can drift);
  * DP-based repair of malformed rows (embedded commas splitting a row into
    the wrong number of fields), identical scoring to the precedent;
  * hard fail on any output row with no non-slug payload (a batch whose
    consolidation finals are not yet filled is NOT combinable -- combine runs
    AFTER the consolidators);
  * full output re-read + cell-by-cell copy verification;
  * audit txt written next to the output.

DETERMINISTIC SCAFFOLDING ONLY: no semantic decision is made here; every cell
is copied verbatim from the consolidation CSVs the AI consolidators filled.

Usage:
  python scripts/combine_consolidations.py --test <key> [--batch batch_001|all]
      [--out-dir DIR]   (--out-dir redirects output, used for regression tests)
  python scripts/combine_consolidations.py --list
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

# test key -> (pipeline module file, pipeline --test key or None, results folder, prefix)
TESTS: dict[str, tuple[str, str | None, str, str]] = {
    "schema-test-A-tests": ("schema_a_pipeline.py", "schema-test-A-tests",
                            "schema-test-A-tests", "SCHEMA_A"),
    "schema-test-A-new-system-tests": ("schema_a_pipeline.py", "schema-test-A-new-system-tests",
                                       "schema-test-A-new-system-tests", "SCHEMA_A_NEW_SYSTEM"),
    "schema-test-B-tests": ("schema_b_pipeline.py", "schema-test-B-tests",
                            "schema-test-B-tests", "SCHEMA_B"),
    "schema-test-B-new-system-tests": ("schema_b_pipeline.py", "schema-test-B-new-system-tests",
                                       "schema-test-B-new-system-tests", "SCHEMA_B_NEW_SYSTEM"),
    "test-01-kernel-tests": ("test01_pipeline.py", None,
                             "test-01-kernel-tests", "TEST01"),
    "test-02-completion-tests-nat-lex": ("test0x_pipeline.py", "test-02-completion-tests-nat-lex",
                                         "test-02-completion-tests-nat-lex", "TEST02"),
    "test-03-completion-tests-ordinal": ("test0x_pipeline.py", "test-03-completion-tests-ordinal",
                                         "test-03-completion-tests-ordinal", "TEST03"),
    "test-04-measure-verification-tests": ("test0x_pipeline.py", "test-04-measure-verification-tests",
                                           "test-04-measure-verification-tests", "TEST04"),
    "test-05-candidate-class-reasoning-tests": ("test0x_pipeline.py", "test-05-candidate-class-reasoning-tests",
                                                "test-05-candidate-class-reasoning-tests", "TEST05"),
    "test-06-branch-realism-tests": ("test0x_pipeline.py", "test-06-branch-realism-tests",
                                     "test-06-branch-realism-tests", "TEST06"),
}


def load_pipeline(module_file: str, test_key: str | None):
    """Import the test's pipeline module and configure it, so ROUNDS / vocab
    are read from the single source of truth."""
    path = SCRIPTS / module_file
    name = f"_combine_{module_file[:-3]}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    if test_key is not None and hasattr(mod, "configure"):
        mod.configure(test_key)
    return mod


def build_allowed(mod) -> dict[str, dict[str, set[str] | None]]:
    """round key -> (column -> allowed value set; None = free text), for the
    consolidation headers of each round, derived from the pipeline ROUNDS.
    Per-round because every round has its own `extraction_notes` vocabulary
    under the same column name."""
    per_round: dict[str, dict[str, set[str] | None]] = {}
    for rk, rnd in mod.ROUNDS.items():
        allowed: dict[str, set[str] | None] = {"session_slug": None}
        per_field: dict[str, set[str] | None] = {}
        for f in rnd.fields:
            if f == "extraction_notes":
                per_field[f] = set(rnd.notes_vocab)
            elif f in rnd.vocab:
                per_field[f] = set(rnd.vocab[f]) | {""}
            else:
                per_field[f] = None  # free text / quotes / rationales
        for tag in ("extractor1", "extractor2", "final"):
            for f, vals in per_field.items():
                allowed[f"{tag}_{f}"] = vals
        per_round[rk] = allowed
    return per_round


def free_text_penalty(value: str, token_count: int, consumed_tokens: list[str]) -> int:
    if token_count == 0:
        return 4
    penalty = token_count - 1
    if value.startswith(" "):
        penalty += 8
    if token_count == 1 and consumed_tokens and consumed_tokens[0] in {
        "yes", "no", "unclear", "none", "file_missing", "non_numbered_response",
    }:
        penalty += 2
    return penalty


def repair_row(header: list[str], tokens: list[str],
               allowed_of: dict[str, set[str] | None]) -> tuple[int, list[str]]:
    target_len = len(header)
    token_len = len(tokens)
    tokens_t = tuple(tokens)

    @lru_cache(maxsize=None)
    def solve(header_index: int, token_index: int) -> tuple[int, tuple[str, ...]] | None:
        if header_index == target_len:
            if token_index == token_len:
                return 0, ()
            return None
        column = header[header_index]
        if column == "session_slug":
            if token_index < token_len and "__2026-" in tokens_t[token_index]:
                rest = solve(header_index + 1, token_index + 1)
                if rest is not None:
                    score, values = rest
                    return score, (tokens_t[token_index],) + values
            return None
        allowed = allowed_of.get(column)
        if allowed is not None:
            best: tuple[int, tuple[str, ...]] | None = None
            if token_index < token_len and tokens_t[token_index] in allowed:
                rest = solve(header_index + 1, token_index + 1)
                if rest is not None:
                    score, values = rest
                    best = score, (tokens_t[token_index],) + values
            if "" in allowed:
                rest = solve(header_index + 1, token_index)
                if rest is not None:
                    score, values = rest
                    candidate = score + 5, ("",) + values
                    if best is None or candidate[0] < best[0]:
                        best = candidate
            return best
        best = None
        for consume_count in range(0, token_len - token_index + 1):
            consumed = list(tokens_t[token_index: token_index + consume_count])
            value = "" if consume_count == 0 else ",".join(consumed)
            rest = solve(header_index + 1, token_index + consume_count)
            if rest is None:
                continue
            score, values = rest
            candidate = score + free_text_penalty(value, consume_count, consumed), (value,) + values
            if best is None or candidate[0] < best[0]:
                best = candidate
        return best

    repaired = solve(0, 0)
    if repaired is None:
        raise ValueError(
            f"unable to normalize row for slug {tokens[0] if tokens else '<empty>'}: {len(tokens)} fields")
    score, values = repaired
    if len(values) != target_len:
        raise ValueError(
            f"normalization produced wrong field count for {tokens[0] if tokens else '<empty>'}")
    return score, list(values)


def read_csv_checked(path: Path, allowed_of: dict[str, set[str] | None]
                     ) -> tuple[list[str], list[dict[str, str]], list[str]]:
    repairs: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"{path.name}: missing header")
        rows: list[dict[str, str]] = []
        for row_number, tokens in enumerate(reader, start=2):
            if len(tokens) != len(header):
                score, tokens = repair_row(header, tokens, allowed_of)
                repairs.append(
                    f"{path.name}: row={row_number} slug={tokens[0]} normalized_score={score}")
            row = dict(zip(header, tokens))
            for column in header:
                allowed = allowed_of.get(column)
                if allowed is not None and row[column] not in allowed:
                    raise ValueError(
                        f"{path.name}: row={row_number} slug={row.get('session_slug', '')} "
                        f"column={column} invalid categorical value={row[column]!r}")
            rows.append(row)
        return header, rows, repairs


def duplicated(values: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for value in values:
        if value in seen and value not in dupes:
            dupes.append(value)
        seen.add(value)
    return dupes


def combine_batch(prefix: str, bdir: Path, rounds: list[str],
                  allowed_per_round: dict[str, dict[str, set[str] | None]],
                  out_dir: Path | None = None) -> tuple[bool, str]:
    """Combine one batch. Returns (ok, message)."""
    audit: list[str] = []
    loaded: dict[str, dict] = {}
    out_base = out_dir if out_dir is not None else bdir
    out_csv = out_base / f"{prefix}_final_consolidation.csv"
    out_audit = out_base / f"{prefix}_final_consolidation_audit.txt"

    for rk in rounds:
        path = bdir / f"{prefix}_{rk}_consolidation.csv"
        if not path.exists():
            return False, f"{bdir.name}: missing {path.name}; nothing combined"
        header, rows, repairs = read_csv_checked(path, allowed_per_round[rk])
        if duplicated(header):
            return False, f"{path.name}: duplicate headers: {duplicated(header)}"
        if "session_slug" not in header:
            return False, f"{path.name}: missing session_slug column"
        slugs = [row["session_slug"] for row in rows]
        if duplicated(slugs):
            return False, f"{path.name}: duplicate session_slug values: {duplicated(slugs)[:5]}"
        loaded[rk] = {"filename": path.name, "header": header, "rows": rows,
                      "slugs": slugs, "by_slug": {r["session_slug"]: r for r in rows}}
        audit.append(f"{rk}: {path.name} rows={len(rows)} columns={len(header)} "
                     f"duplicate_headers=0 duplicate_slugs=0 normalized_rows={len(repairs)}")
        audit.extend(f"  normalized: {rep}" for rep in repairs)

    base_slugs = loaded[rounds[0]]["slugs"]
    for rk in rounds[1:]:
        if loaded[rk]["slugs"] != base_slugs:
            base_set, other_set = set(base_slugs), set(loaded[rk]["slugs"])
            return False, (f"{rk}: slug order/content mismatch; "
                           f"missing={sorted(base_set - other_set)[:5]} "
                           f"extra={sorted(other_set - base_set)[:5]}")

    output_header = ["session_slug"]
    for rk in rounds:
        output_header.extend(f"{rk}__{c}" for c in loaded[rk]["header"] if c != "session_slug")
    if duplicated(output_header):
        return False, f"output duplicate headers: {duplicated(output_header)[:5]}"

    output_rows: list[dict[str, str]] = []
    for slug in base_slugs:
        out_row = {"session_slug": slug}
        for rk in rounds:
            src = loaded[rk]["by_slug"][slug]
            for c in loaded[rk]["header"]:
                if c != "session_slug":
                    out_row[f"{rk}__{c}"] = src[c]
        output_rows.append(out_row)

    blank = [r["session_slug"] for r in output_rows
             if not any(v for k, v in r.items() if k != "session_slug")]
    if blank:
        return False, (f"{bdir.name}: {len(blank)} row(s) with no non-slug data "
                       f"(consolidation finals not yet filled?), e.g. {blank[:3]}; "
                       f"combine runs AFTER the consolidators finish")

    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_header, extrasaction="raise")
        writer.writeheader()
        writer.writerows(output_rows)

    # Re-read + cell-by-cell copy verification.
    reread_header, reread_rows, reread_repairs = read_csv_checked(out_csv, {"session_slug": None})
    if reread_repairs:
        return False, "generated output required normalization on reread"
    if reread_header != output_header:
        return False, "output reread header does not match constructed header"
    if [r["session_slug"] for r in reread_rows] != base_slugs:
        return False, "output reread slug order does not match base slug order"
    for i, slug in enumerate(base_slugs):
        for rk in rounds:
            src = loaded[rk]["by_slug"][slug]
            for c in loaded[rk]["header"]:
                if c != "session_slug" and reread_rows[i][f"{rk}__{c}"] != src[c]:
                    return False, f"copy mismatch row={i+1} slug={slug} column={rk}__{c}"

    audit.append("slug_order_identical=yes")
    audit.append(f"output: {out_csv.name} rows={len(output_rows)} "
                 f"columns={len(output_header)} duplicate_headers=0")
    audit.append("blank_payload_rows=0")
    audit.append("output_reread_match=yes")
    audit.append("cell_copy_check=passed")
    audit.append("column_order=session_slug," + ",".join(rounds))
    out_audit.write_text("\n".join(audit) + "\n", encoding="utf-8")
    return True, f"{bdir.name}: combined {len(output_rows)} rows x {len(output_header)} cols -> {out_csv.name}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mechanical per-batch consolidation combiner (all tests)")
    ap.add_argument("--test", choices=sorted(TESTS), help="which test to combine")
    ap.add_argument("--batch", default="all", help="batch_XXX or 'all' (default)")
    ap.add_argument("--out-dir", default=None,
                    help="redirect output files (regression testing); default = the batch dir")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list or not args.test:
        print("tests:", ", ".join(sorted(TESTS)))
        return 0

    module_file, pipe_key, folder, prefix = TESTS[args.test]
    mod = load_pipeline(module_file, pipe_key)
    rounds = list(mod.ROUNDS.keys())
    allowed_per_round = build_allowed(mod)

    # Flat layout: batches/ IS the single batch (its manifest lives directly here).
    batches_dir = ROOT / "results" / folder / "extraction" / "batches"
    if (batches_dir / "batch_manifest.json").exists():
        batches = [batches_dir]
    elif batches_dir.is_dir():  # legacy fallback: batch_* subfolders
        batches = sorted(p for p in batches_dir.iterdir()
                         if p.is_dir() and p.name.startswith("batch_"))
    else:
        batches = []

    if not batches:
        print(f"{args.test}: no batch found (no batches/batch_manifest.json).")
        return 0

    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    rc = 0
    for bdir in batches:
        if not bdir.is_dir():
            print(f"  SKIP {bdir.name}: not found")
            rc = 2
            continue
        ok, msg = combine_batch(prefix, bdir, rounds, allowed_per_round, out_dir)
        print(("  OK   " if ok else "  HOLD ") + msg)
        if not ok:
            rc = 2
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
