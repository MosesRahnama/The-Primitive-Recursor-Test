from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .adapters import (
    adapter_selftest,
    build_adapter,
    init_adapter,
    validate_adapter,
)
from .benchmark import (
    copy_portable_source,
    generate_benchmark_contracts,
    load_benchmark_package,
    validate_benchmark_package,
)
from .checkers import checker_from_contract, load_legacy_checker, toy_checker
from .collection import compile_pass_directory, load_compiled_directories, write_gate_csv
from .common import (
    V3_CHECKER_INPUT_VERSION,
    read_json,
    sha256_file,
    write_json_atomic,
    write_text_atomic,
)
from .config import InstanceContract
from .consensus import gate_dataset
from .deploy import deploy_profile
from .deploy_v3 import verify_deployed_run
from .diagnostics import audit_pass_directory, doctor, pass_status
from .permutation_audit import write_permutation_stability_audit
from .release import build_release, verify_release
from .scoring import score_gate_report
from .validation import validate_record_file

if hasattr(sys.stdout, "reconfigure"):
    # Live-round finding (2026-07-27): records legitimately contain glyphs
    # (recΔ); a cp1252 console must not crash report printing.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# OpenAI-shaped chat/completions endpoints usable as constructor backends. The proposer
# contract is vendor-neutral (the model only ever sees {accepted, reason/local_id}), so
# provider choice is an operational matter — cost, availability, quota — not a semantic one.
# Each reads its key from the matching env var (OPENAI_API_KEY / DEEPSEEK_API_KEY / ...).
_OPENAI_COMPAT_BASE_URLS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
}
# Reasoning models reject function tools on chat/completions unless reasoning_effort is
# 'none'; they need the Responses API to keep BOTH tools and reasoning.
_OPENAI_RESPONSES_BACKENDS = {
    "openai-responses": "https://api.openai.com/v1/responses",
}


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def command_validate(args: argparse.Namespace) -> int:
    contract = InstanceContract.load(Path(args.contract))
    run_manifest = (
        read_json(Path(args.run_manifest)) if args.run_manifest else None
    )
    _, issues = validate_record_file(
        Path(args.record),
        contract,
        require_independence=not args.allow_nonindependent,
        run_manifest=run_manifest,
        official_mode=not args.provisional,
    )
    result = {
        "record": str(Path(args.record).resolve()),
        "valid": not issues,
        "issues": [issue.as_dict() for issue in issues],
    }
    _print(result)
    return 0 if not issues else 1


def command_compile_pass(args: argparse.Namespace) -> int:
    contract = InstanceContract.load(Path(args.contract))
    run_manifest = (
        read_json(Path(args.run_manifest)) if args.run_manifest else None
    )
    report = compile_pass_directory(
        Path(args.input),
        Path(args.output),
        contract,
        require_independence=not args.allow_nonindependent,
        run_manifest=run_manifest,
    )
    _print(report)
    return 0 if report["invalid_count"] == 0 else 1


def command_gate(args: argparse.Namespace) -> int:
    records = load_compiled_directories([Path(value) for value in args.compiled])
    report = gate_dataset(records)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable gate report already exists: {output}")
    write_json_atomic(output, report)
    if args.csv:
        write_gate_csv(report, Path(args.csv))
    _print(
        {
            "output": str(output.resolve()),
            "session_count": report["session_count"],
            "gate_status_counts": report["gate_status_counts"],
            "unresolved_total": report["unresolved_total"],
        }
    )
    return 0


def command_score_single(args: argparse.Namespace) -> int:
    from .prt_selective import _csv_text, write_single_claims
    from .single_extractor import score_single_run

    run_dir = Path(args.run_dir).resolve()
    artifact_root = Path(args.artifact_root).resolve() if args.artifact_root else Path(__file__).resolve().parents[2]
    report = score_single_run(run_dir, artifact_root=artifact_root)
    output_dir = run_dir / "scoring"
    write_json_atomic(output_dir / "scores.json", report)
    rows = [{**row, "reasons": ";".join(row["reasons"])} for row in report["rows"]]
    write_text_atomic(output_dir / "scores.csv", _csv_text(rows, (
        "session_slug", "extraction_mode", "extractor_count", "status", "input_sha256", "policy_version",
        "method_mathematical_validity", "method_correct_and_admissible", "reasons",
    )))
    write_single_claims(output_dir / "claims.csv", {report["contract"]["instance_key"]: {"single_extractor": report}})
    _print({"output": str(output_dir), **{k: report[k] for k in (
        "session_count", "extractor_count", "invalid_count", "unknown_count", "report_sha256")}})
    return 1 if report["unknown_count"] else 0


def command_score(args: argparse.Namespace) -> int:
    gate_report = read_json(Path(args.gate))
    allow_substitution = bool(
        getattr(args, "allow_contract_substitution", False)
    )
    substitution_reason = getattr(args, "contract_substitution_reason", None)
    allow_early_v3_replay = bool(
        getattr(args, "allow_early_v3_replay", False)
    )
    early_v3_replay_reason = getattr(args, "early_v3_replay_reason", None)
    early_v3_checker_interface = getattr(
        args, "early_v3_checker_interface", None
    )
    if allow_substitution and (
        not isinstance(substitution_reason, str) or not substitution_reason.strip()
    ):
        raise ValueError(
            "--allow-contract-substitution requires --contract-substitution-reason"
        )
    if substitution_reason and not allow_substitution:
        raise ValueError(
            "--contract-substitution-reason requires --allow-contract-substitution"
        )
    if allow_early_v3_replay and (
        not isinstance(early_v3_replay_reason, str)
        or not early_v3_replay_reason.strip()
    ):
        raise ValueError(
            "--allow-early-v3-replay requires --early-v3-replay-reason"
        )
    if early_v3_replay_reason and not allow_early_v3_replay:
        raise ValueError(
            "--early-v3-replay-reason requires --allow-early-v3-replay"
        )
    if early_v3_checker_interface and not allow_early_v3_replay:
        raise ValueError(
            "--early-v3-checker-interface requires --allow-early-v3-replay"
        )
    if early_v3_checker_interface and not args.contract:
        raise ValueError(
            "--early-v3-checker-interface requires --contract"
        )
    contract = None
    if args.toy_checker:
        checker = toy_checker
    elif args.contract:
        contract = InstanceContract.load(
            Path(args.contract),
            allow_early_v3_replay=allow_early_v3_replay,
        )
        checker = checker_from_contract(
            contract,
            artifact_root=Path(args.artifact_root) if args.artifact_root else None,
            allow_early_v3_replay=allow_early_v3_replay,
            early_v3_checker_interface=early_v3_checker_interface,
        )
    elif args.checker_module:
        checker = load_legacy_checker(
            Path(args.checker_module),
            function_name=args.checker_function,
            expected_sha256=args.checker_sha256,
            expected_checker_input_schema_version=(
                V3_CHECKER_INPUT_VERSION
                if gate_report.get("gate_report_version")
                == "tgc-gate-report/3.0.0"
                else None
            ),
        )
    else:
        raise ValueError("score requires --contract, --toy-checker, or --checker-module")
    policy_override = None
    if getattr(args, "policy_from_contract", False):
        if contract is None:
            raise ValueError("--policy-from-contract requires --contract")
        from .policy import boundary_policy as build_boundary_policy

        policy_override = build_boundary_policy(contract)
    report = score_gate_report(
        gate_report,
        checker,
        checker_binding=getattr(
            checker,
            "__tgc_binding__",
            contract.checker_binding if contract is not None else None,
        ),
        boundary_policy_override=policy_override,
        allow_contract_substitution=allow_substitution,
        contract_substitution_reason=substitution_reason,
        allow_early_v3_replay=allow_early_v3_replay,
        early_v3_replay_reason=early_v3_replay_reason,
    )
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f"immutable score report already exists: {output}")
    write_json_atomic(output, report)
    _print(
        {
            "output": str(output.resolve()),
            "session_count": report["session_count"],
            "lane_counts": report["lane_counts"],
            "metric_counts": report["metric_counts"],
        }
    )
    return 0


def command_audit_permutation_stability(args: argparse.Namespace) -> int:
    report = write_permutation_stability_audit(
        pair_gate_paths=[Path(value) for value in args.pair_gate],
        pair_score_paths=[Path(value) for value in args.pair_score],
        triple_gate_path=Path(args.triple_gate),
        triple_score_path=Path(args.triple_score),
        output_json_path=Path(args.output),
        output_csv_path=Path(args.csv),
    )
    _print(
        {
            "output": str(Path(args.output).resolve()),
            "csv": str(Path(args.csv).resolve()),
            "session_count": report["session_count"],
            "extraction_unstable_count": report["extraction_unstable_count"],
            "decision_unstable_count": report["decision_unstable_count"],
            "pairwise_unstable_count": report["pairwise_unstable_count"],
            "flagged_count": report["flagged_count"],
        }
    )
    return 0


def command_deploy(args: argparse.Namespace) -> int:
    manifest = deploy_profile(Path(args.profile))
    _print(manifest)
    return 0


def command_verify_run(args: argparse.Namespace) -> int:
    result = verify_deployed_run(Path(args.run_dir))
    _print(result)
    return 0 if result["valid"] else 1


def command_pass_status(args: argparse.Namespace) -> int:
    report = pass_status(Path(args.run_dir), int(args.pass_number))
    _print(report)
    return 0 if report["file_set"]["matches_roster"] else 1


def command_seed_tiebreak(args: argparse.Namespace) -> int:
    from .deploy_v3 import seed_tiebreak

    result = seed_tiebreak(Path(args.run_dir), Path(args.gate))
    _print(result)
    return 0


def command_construct(args: argparse.Namespace) -> int:
    """Supervised construction for one seeded session (engine 3.3.0)."""
    from .constructor import (
        AnthropicConstructorClient,
        OpenAICompatConstructorClient,
        OpenAIResponsesConstructorClient,
        SupervisedConstructor,
        run_constructor_session,
    )

    run_dir = Path(args.run_dir).resolve()
    from .deploy_v3 import verify_deployed_run
    from .validation import load_sources, validate_record

    verification = verify_deployed_run(run_dir)
    if not verification["valid"]:
        _print(verification)
        return 1
    if not getattr(args, "attest_independent", False):
        print("ERROR: --attest-independent is required for a blind construction pass", file=sys.stderr)
        return 2
    contract = InstanceContract.load(run_dir / "contract")
    run_manifest = read_json(run_dir / "RUN_MANIFEST.json")
    if args.session_slug not in {entry["session_slug"] for entry in run_manifest["roster"]}:
        print("ERROR: session is not in the selected roster", file=sys.stderr)
        return 2
    pass_dir = run_dir / "extraction" / f"e{int(args.pass_number):02d}"
    from .collection_v3 import _pass_for_input_dir

    pass_entry = _pass_for_input_dir(run_manifest, pass_dir)
    if "tiebreak_slugs" in pass_entry and args.session_slug not in pass_entry["tiebreak_slugs"]:
        print("ERROR: session is not in the tiebreak roster", file=sys.stderr)
        return 2
    extra_pass = ({k: v for k, v in pass_entry.items() if k != "tiebreak_slugs"}
                  if int(args.pass_number) == 3 else None)
    seeded_path = pass_dir / f"{args.session_slug}.json"
    seeded_sha256 = sha256_file(seeded_path)
    seeded = read_json(seeded_path)
    if not validate_record(seeded, contract, run_manifest=run_manifest, extra_pass_entry=extra_pass):
        print("ERROR: this session already has a valid record; refusing replacement", file=sys.stderr)
        return 2
    sources, source_issues = load_sources(seeded)
    if source_issues or len(sources) != 1 or not next(iter(sources.values()), "").strip():
        _print({"error": "invalid construction source", "issues": [x.as_dict() for x in source_issues]})
        return 1
    source_text = next(iter(sources.values()))
    client_options = {}
    if run_manifest.get("extraction_mode") == "single":
        client_options["instructions"] = "\n\n".join(
            (contract.contract_dir / filename).read_text(encoding="utf-8")
            for filename in ("CLASSIFICATION_GUIDE.md", "TRANSFORMATIONS.md")
        )
    checker = None
    if args.probe_checker:
        checker = checker_from_contract(
            contract, artifact_root=Path.cwd()
        )
    constructor = SupervisedConstructor(
        contract,
        seeded,
        sources,
        run_manifest=run_manifest,
        checker=checker,
        constructor_id=(getattr(args, "extractor_id", None)
                        or f"constructor:{args.backend}:{args.model}"),
        independence_attestation=True,
        extra_pass_entry=extra_pass,
    )
    if args.backend == "anthropic":
        client = AnthropicConstructorClient(
            constructor.tools,
            source_text,
            model=args.model,
            **client_options,
        )
    elif args.backend in _OPENAI_RESPONSES_BACKENDS:
        client = OpenAIResponsesConstructorClient(
            constructor.tools,
            source_text,
            model=args.model,
            base_url=_OPENAI_RESPONSES_BACKENDS[args.backend],
            **client_options,
        )
    elif args.backend in _OPENAI_COMPAT_BASE_URLS:
        client = OpenAICompatConstructorClient(
            constructor.tools,
            source_text,
            model=args.model,
            base_url=_OPENAI_COMPAT_BASE_URLS[args.backend],
            **client_options,
        )
    else:
        raise SystemExit(
            f"backend {args.backend!r} is not wired for CLI use; scripted "
            "clients are a library/test surface"
        )
    record, audit = run_constructor_session(constructor, client)
    issues = validate_record(record, contract, run_manifest=run_manifest, extra_pass_entry=extra_pass)
    audit["valid"] = not issues and record.get("record_status") == "complete"
    audit["issues"] = [issue.as_dict() for issue in issues]
    if sha256_file(seeded_path) != seeded_sha256:
        print("ERROR: another writer changed this record; construction result was not saved", file=sys.stderr)
        return 2
    write_json_atomic(seeded_path, record)
    # The construction audit lives OUTSIDE the pass directory: the pass
    # file-set contract requires exactly one <slug>.json per roster entry.
    audit_dir = run_dir / "construction_audits" / pass_dir.name
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"{args.session_slug}.json"
    write_json_atomic(audit_path, audit)
    _print(
        {
            "session_slug": args.session_slug,
            "record": str(seeded_path),
            "construction_audit": str(audit_path),
            "claims": audit["claims"],
            "null_attempts": audit["null_attempts"],
            "bypass_attempts": audit["bypass_attempts"],
        }
    )
    return 0 if audit["valid"] else 1


def command_repair_brief(args: argparse.Namespace) -> int:
    from .diagnostics import repair_brief

    report = read_json(Path(args.audit))
    text = repair_brief(report)
    if args.output:
        output = Path(args.output)
        if output.exists():
            print(f"ERROR: repair brief already exists: {output}", file=sys.stderr)
            return 2
        output.write_text(text, encoding="utf-8", newline=chr(10))
        print(str(output.resolve()))
    else:
        print(text)
    return 0


def command_audit_pass(args: argparse.Namespace) -> int:
    contract = InstanceContract.load(Path(args.contract))
    run_manifest = (
        read_json(Path(args.run_manifest)) if args.run_manifest else None
    )
    report = audit_pass_directory(
        Path(args.input),
        contract,
        run_manifest=run_manifest,
        require_independence=not args.allow_nonindependent,
        official_mode=not args.provisional,
    )
    if args.output:
        output = Path(args.output)
        if output.exists():
            # Live-round friction F1: silently keeping a stale report made us
            # measure "still failing" after the fix had landed. Refuse LOUDLY
            # with a nonzero exit; never overwrite an immutable audit.
            print(
                f"ERROR: immutable pass audit already exists: {output} "
                "(choose a new --output name; audits are create-once)",
                file=sys.stderr,
            )
            return 2
        write_json_atomic(output, report)
    _print(report)
    return 0 if report["invalid_count"] == 0 else 1


def command_doctor(args: argparse.Namespace) -> int:
    result = doctor(
        Path(args.contract),
        run_dir=Path(args.run_dir) if args.run_dir else None,
        artifact_root=(
            Path(args.artifact_root) if args.artifact_root else None
        ),
    )
    _print(result)
    return 0 if result["valid"] else 1


def command_validate_benchmark(args: argparse.Namespace) -> int:
    result = validate_benchmark_package(Path(args.package))
    _print(result)
    return 0 if result["valid"] else 1


def command_generate_benchmark(args: argparse.Namespace) -> int:
    result = generate_benchmark_contracts(
        Path(args.package),
        destination=Path(args.destination) if args.destination else None,
    )
    _print(result)
    return 0


def command_copy_benchmark(args: argparse.Namespace) -> int:
    package = load_benchmark_package(Path(args.package))
    copy_portable_source(package, Path(args.destination))
    result = {
        "source": str(package.root),
        "destination": str(Path(args.destination).resolve()),
        "package_name": package.name,
        "package_version": package.version,
    }
    _print(result)
    return 0


def command_init_adapter(args: argparse.Namespace) -> int:
    result = init_adapter(Path(args.destination))
    _print(result)
    return 0


def command_build_adapter(args: argparse.Namespace) -> int:
    result = build_adapter(Path(args.adapter))
    _print(result)
    return 0


def command_validate_adapter(args: argparse.Namespace) -> int:
    result = validate_adapter(Path(args.adapter))
    _print(result)
    return 0 if result["valid"] else 1


def command_adapter_selftest(args: argparse.Namespace) -> int:
    result = adapter_selftest(Path(args.adapter))
    _print(result)
    return 0 if result["valid"] else 1


def command_release_build(args: argparse.Namespace) -> int:
    result = build_release(
        Path(args.root),
        Path(args.destination),
        version=args.version,
        license_path=Path(args.license) if args.license else None,
        include_legacy_replay=args.include_legacy_replay,
    )
    _print(result)
    return 0


def command_release_verify(args: argparse.Namespace) -> int:
    result = verify_release(Path(args.stage))
    _print(result)
    return 0 if result["valid"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tgc",
        description="Transcribe-Gate-Certify: modular source-bound extraction, field-level consensus, deterministic certification, transferable adapters, and reproducible release tooling.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-record", help="validate one source-bound extraction record")
    validate.add_argument("--contract", required=True)
    validate.add_argument("--record", required=True)
    validate.add_argument("--run-manifest", help="required for official v3 validation")
    validate.add_argument("--allow-nonindependent", action="store_true")
    validate.add_argument("--provisional", action="store_true", help="allow an unbound/non-final v3 record for development only")
    validate.set_defaults(function=command_validate)

    compile_pass = sub.add_parser("compile-pass", help="compile one pass directory into immutable normalized records")
    compile_pass.add_argument("--contract", required=True)
    compile_pass.add_argument("--input", required=True)
    compile_pass.add_argument("--output", required=True)
    compile_pass.add_argument("--run-manifest", help="required for v3 pass compilation")
    compile_pass.add_argument("--allow-nonindependent", action="store_true")
    compile_pass.set_defaults(function=command_compile_pass)

    gate = sub.add_parser("gate", help="gate two or three compiled pass directories")
    gate.add_argument("--compiled", action="append", required=True, help="repeat for each compiled pass directory")
    gate.add_argument("--output", required=True)
    gate.add_argument("--csv", help="optional compatibility/reporting CSV")
    gate.set_defaults(function=command_gate)

    score = sub.add_parser("score", help="score a gate report with a pinned checker")
    score.add_argument("--gate", required=True)
    score.add_argument("--output", required=True)
    score.add_argument("--toy-checker", action="store_true")
    score.add_argument("--contract", help="generated contract; uses its pinned checker binding")
    score.add_argument(
        "--policy-from-contract",
        action="store_true",
        help=(
            "score under the --contract's boundary policy instead of the gate "
            "rows' embedded bundle; recorded in lineage as an explicit "
            "substitution (for re-scoring frozen rounds under a newer contract)"
        ),
    )
    score.add_argument(
        "--allow-contract-substitution",
        action="store_true",
        help=(
            "historical replay only: allow the scoring contract to differ "
            "from the gate contract; requires --contract-substitution-reason"
        ),
    )
    score.add_argument(
        "--contract-substitution-reason",
        help="nonempty reason receipted in lineage for an authorized replay",
    )
    score.add_argument(
        "--allow-early-v3-replay",
        action="store_true",
        help=(
            "historical replay only: admit the closed set of early-v3 schema "
            "migrations; requires --early-v3-replay-reason"
        ),
    )
    score.add_argument(
        "--early-v3-replay-reason",
        help="nonempty reason receipted for an authorized early-v3 replay",
    )
    score.add_argument(
        "--early-v3-checker-interface",
        choices=["legacy_tuple_v1", "native_v1"],
        help=(
            "operator-supplied interface for a frozen early-v3 contract that "
            "omits one; valid only with --allow-early-v3-replay"
        ),
    )
    score.add_argument("--artifact-root", help="root for resolving a contract's relative checker module path")
    score.add_argument("--checker-module", help="advanced override for a pinned legacy checker module")
    score.add_argument("--checker-function", default="check_object")
    score.add_argument("--checker-sha256")
    score.set_defaults(function=command_score)

    single_score = sub.add_parser("score-single", help="score one registered PRT extractor with source coverage checks")
    single_score.add_argument("--run-dir", required=True)
    single_score.add_argument("--artifact-root")
    single_score.set_defaults(function=command_score_single)

    permutation_audit = sub.add_parser(
        "audit-permutation-stability",
        help="emit read-only pair-vs-triple lane stability telemetry",
    )
    permutation_audit.add_argument(
        "--pair-gate",
        action="append",
        required=True,
        help="repeat exactly three times; matching is by pass set and score lineage",
    )
    permutation_audit.add_argument(
        "--pair-score",
        action="append",
        required=True,
        help="repeat exactly three times; matching is by bound gate report hash",
    )
    permutation_audit.add_argument("--triple-gate", required=True)
    permutation_audit.add_argument("--triple-score", required=True)
    permutation_audit.add_argument("--output", required=True, help="immutable JSON output")
    permutation_audit.add_argument("--csv", required=True, help="immutable CSV output")
    permutation_audit.set_defaults(function=command_audit_permutation_stability)

    deploy = sub.add_parser("deploy", help="transactionally deploy a hash-bound contract and seeded blind-pass directories")
    deploy.add_argument("--profile", required=True)
    deploy.set_defaults(function=command_deploy)

    verify_run = sub.add_parser("verify-run", help="verify a deployed v3 run, contract, roster, dispatches, and seed bindings")
    verify_run.add_argument("--run-dir", required=True)
    verify_run.set_defaults(function=command_verify_run)

    tiebreak_parser = sub.add_parser("seed-tiebreak", help="seed a blind pass-3 tiebreak from a gate report, bound to the deployed run")
    tiebreak_parser.add_argument("--run-dir", required=True)
    tiebreak_parser.add_argument("--gate", required=True)
    tiebreak_parser.set_defaults(function=command_seed_tiebreak)

    construct_parser = sub.add_parser("construct", help="supervised construction for one seeded session: closed tool schemas, exact-quote anchoring, silent checker probes, faithfulness-gated output")
    construct_parser.add_argument("--run-dir", required=True)
    construct_parser.add_argument("--pass-number", required=True, type=int)
    construct_parser.add_argument("--session-slug", required=True)
    construct_parser.add_argument(
        "--backend", default="anthropic",
        choices=["anthropic", *sorted(_OPENAI_COMPAT_BASE_URLS),
                 *sorted(_OPENAI_RESPONSES_BACKENDS)])
    construct_parser.add_argument("--model", default="claude-opus-5")
    construct_parser.add_argument("--probe-checker", action="store_true", help="record silent deterministic checker probes in the construction audit")
    construct_parser.add_argument("--attest-independent", action="store_true", help="attest this pass has not seen another pass or score labels")
    construct_parser.add_argument("--extractor-id", help="identity of the independent reader/session; never reuse across passes")
    construct_parser.set_defaults(function=command_construct)

    brief_parser = sub.add_parser("repair-brief", help="generate the per-pass repair dispatch box from an audit report")
    brief_parser.add_argument("--audit", required=True)
    brief_parser.add_argument("--output")
    brief_parser.set_defaults(function=command_repair_brief)

    status_parser = sub.add_parser("pass-status", help="mid-flight fill status for one pass: file-set conformance + filled/placeholder/unparseable counts")
    status_parser.add_argument("--run-dir", required=True)
    status_parser.add_argument("--pass-number", required=True)
    status_parser.set_defaults(function=command_pass_status)

    audit_pass = sub.add_parser("audit-pass", help="validate every raw record in one pass and summarize coverage/evidence defects")
    audit_pass.add_argument("--contract", required=True)
    audit_pass.add_argument("--run-manifest")
    audit_pass.add_argument("--input", required=True)
    audit_pass.add_argument("--output")
    audit_pass.add_argument("--allow-nonindependent", action="store_true")
    audit_pass.add_argument("--provisional", action="store_true")
    audit_pass.set_defaults(function=command_audit_pass)

    doctor_parser = sub.add_parser("doctor", help="verify contract/checker wiring and optionally a deployed v3 run")
    doctor_parser.add_argument("--contract", required=True)
    doctor_parser.add_argument("--run-dir")
    doctor_parser.add_argument("--artifact-root")
    doctor_parser.set_defaults(function=command_doctor)

    validate_benchmark_parser = sub.add_parser(
        "validate-benchmark",
        help="validate a portable benchmark package descriptor and modular source",
    )
    validate_benchmark_parser.add_argument("--package", required=True)
    validate_benchmark_parser.set_defaults(function=command_validate_benchmark)

    generate_benchmark_parser = sub.add_parser(
        "generate-benchmark",
        help="generate hash-closed contracts from a portable benchmark package",
    )
    generate_benchmark_parser.add_argument("--package", required=True)
    generate_benchmark_parser.add_argument("--destination")
    generate_benchmark_parser.set_defaults(function=command_generate_benchmark)

    copy_benchmark_parser = sub.add_parser(
        "copy-benchmark-source",
        help="copy only path-neutral benchmark source for relocation/audit",
    )
    copy_benchmark_parser.add_argument("--package", required=True)
    copy_benchmark_parser.add_argument("--destination", required=True)
    copy_benchmark_parser.set_defaults(function=command_copy_benchmark)

    init_adapter_parser = sub.add_parser(
        "init-adapter",
        help="create a path-neutral starter adapter workspace",
    )
    init_adapter_parser.add_argument("--destination", required=True)
    init_adapter_parser.set_defaults(function=command_init_adapter)

    build_adapter_parser = sub.add_parser(
        "build-adapter",
        help="generate a hash-closed contract from an adapter workspace",
    )
    build_adapter_parser.add_argument("--adapter", required=True)
    build_adapter_parser.set_defaults(function=command_build_adapter)

    validate_adapter_parser = sub.add_parser(
        "validate-adapter",
        help="validate adapter source, checker binding, and deterministic regeneration",
    )
    validate_adapter_parser.add_argument("--adapter", required=True)
    validate_adapter_parser.set_defaults(function=command_validate_adapter)

    adapter_selftest_parser = sub.add_parser(
        "adapter-selftest",
        help="run an adapter's full deploy/compile/gate/check/score fixture",
    )
    adapter_selftest_parser.add_argument("--adapter", required=True)
    adapter_selftest_parser.set_defaults(function=command_adapter_selftest)

    release_build = sub.add_parser("build-release", help="build an immutable, checksummed artifact release")
    release_build.add_argument("--root", required=True)
    release_build.add_argument("--destination", required=True)
    release_build.add_argument("--version", required=True)
    release_build.add_argument("--license")
    release_build.add_argument(
        "--include-legacy-replay",
        action="store_true",
        help=(
            "opt in to the historical v1/v2 replay sources and assets; "
            "the default artifact is forward-v3 only"
        ),
    )
    release_build.set_defaults(function=command_release_build)

    release_verify = sub.add_parser("verify-release", help="verify a staged release manifest and every file hash")
    release_verify.add_argument("--stage", required=True)
    release_verify.set_defaults(function=command_release_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.function(args))
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
