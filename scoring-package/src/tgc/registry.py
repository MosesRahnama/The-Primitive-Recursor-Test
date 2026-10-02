"""Typed access to the generated modular construction registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_LATEX_WRAPPER_RE = re.compile(
    r"\\(?:text|mathsf|mathrm|mathtt|mathbf|operatorname)\{([^{}]*)\}"
)


_KIND_ONLY_IDENTITY = {
    "root_control_proof",
    "global_multiset_measure",
    "recursive_aux_measure",
    "phased_measure",
    "structural_induction_untyped",
    "other_unparseable",
}


def _default_identity_policy(
    kind: str,
    transform_adapter: str,
    schema: dict[str, Any],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Backward-compatible identity defaults for frozen v3.0 contracts.

    The first live v3 round proved that exact explanatory prose cannot be a
    mathematical identity key.  New construction modules publish these fields
    explicitly, but deployed v3.0 contracts must be replayable under the fixed
    engine.  These defaults are therefore part of the engine's versioned
    semantics rather than an ad-hoc migration.
    """
    properties = tuple(sorted((schema.get("properties") or {}).keys()))
    if kind in _KIND_ONLY_IDENTITY:
        return "kind_occurrence_v1", (), properties
    if kind == "lex_tuple":
        return "lex_tuple_shape_v1", ("components", "order"), properties
    if kind == "call_measure":
        return "call_measure_scope_v1", ("argument", "measure", "scope"), ("scope",)
    if kind in {"additive_measure", "poly_interpretation"}:
        return "interpretation_core_v1", ("definitions", "named"), ("domain",)
    if transform_adapter == "path_order_v3":
        return "path_order_v1", ("precedence", "precedence_quantifier", "status"), ()
    return "full_payload_v1", properties, ()


def _migrate_identity_adapter(kind: str, adapter: str) -> str:
    """Versioned engine semantics for FROZEN contracts (engine 3.1.2).

    Contracts frozen with the earlier ``selected_fields_v1`` policy replay
    under their historical adapter; this is part of the engine's versioned
    semantics, not a contract mutation (the frozen bytes are untouched).
    Current generated contracts explicitly carry the refined identity fields,
    including aggregate argument identity, and do not rely on this migration.
    """
    if kind == "call_measure" and adapter == "selected_fields_v1":
        return "call_measure_scope_v1"
    return adapter


def fold_glyph_tokens(value: str, glyph_folds: tuple[tuple[str, str], ...]) -> str:
    """Apply contract glyph folds; word-shaped folds rewrite whole tokens only.

    Prompt-supplied renames (pear -> app) are ordinary English words: a plain
    substring replace would silently corrupt surrounding prose ("appears").
    A fold whose source spelling is word-shaped binds to token boundaries;
    non-word glyph folds keep plain substring semantics.
    """
    for old, new in glyph_folds:
        if re.fullmatch(r"\w+", old):
            value = re.sub(r"\b" + re.escape(old) + r"\b", new, value)
        else:
            value = value.replace(old, new)
    return value


def fold_symbol_reference(
    value: Any, glyph_folds: tuple[tuple[str, str], ...]
) -> Any:
    """Normalize a signature-symbol REFERENCE (never math content).

    Live-round findings (2026-07-27): faithful transcription copies the
    response's dress onto symbol names — glyphs (recΔ) and layout-only LaTeX
    wrappers (\\text{rec}\\Delta). A symbol field refers to the signature, so
    strip wrapper commands, map \\Delta to its glyph, then apply the
    instance's glyph folds. Raw spellings stay in receipts/anchors.
    """
    if not isinstance(value, str):
        return value
    previous = None
    while previous != value:
        previous = value
        value = _LATEX_WRAPPER_RE.sub(r"\1", value)
    value = value.replace("\\Delta", "Δ")
    value = fold_glyph_tokens(value, glyph_folds)
    return value.strip()


@dataclass(frozen=True)
class ConstructionDefinition:
    kind: str
    title: str
    cue: str
    cue_terms: tuple[str, ...]
    selection_priority: int
    selection_rule: str
    selection_exclusions: tuple[str, ...]
    transcription_schema: dict[str, Any]
    concrete_required: tuple[str, ...]
    concrete_any_of: tuple[tuple[str, ...], ...]
    completeness: dict[str, Any]
    transform_adapter: str
    evidence_units: dict[str, Any]
    checker_route: str
    template_policy: dict[str, Any]
    identity_adapter: str
    identity_fields: tuple[str, ...]
    annotation_fields: tuple[str, ...]

    @property
    def is_frame_only(self) -> bool:
        """Whether this kind carries no registry-declared mathematical object."""

        return (
            not self.identity_fields
            and not self.concrete_required
            and not self.concrete_any_of
        )

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
        *,
        allow_legacy_identity_policy: bool = False,
    ) -> "ConstructionDefinition":
        kind = str(value["kind"])
        schema = dict(value["transcription_schema"])
        transform_adapter = str(value.get("transform_adapter") or "generic_v3")
        identity_fields = {
            "identity_adapter",
            "identity_fields",
            "annotation_fields",
        }
        missing_identity_fields = identity_fields - set(value)
        if missing_identity_fields and not allow_legacy_identity_policy:
            raise ValueError(
                f"{kind}: current construction definition requires explicit "
                f"identity policy fields {sorted(missing_identity_fields)}"
            )
        default_adapter, default_fields, default_annotations = (
            _default_identity_policy(kind, transform_adapter, schema)
            if allow_legacy_identity_policy
            else ("", (), ())
        )
        identity_adapter = str(
            value.get("identity_adapter") or default_adapter
        )
        if (
            kind == "call_measure"
            and identity_adapter == "selected_fields_v1"
            and not allow_legacy_identity_policy
        ):
            raise ValueError(
                "call_measure: selected_fields_v1 is a retired identity "
                "adapter; explicit early-v3 replay authorization is required"
            )
        if allow_legacy_identity_policy:
            identity_adapter = _migrate_identity_adapter(
                kind, identity_adapter
            )
        return cls(
            kind=kind,
            title=str(value.get("title") or value["kind"]),
            cue=str(value.get("cue") or ""),
            cue_terms=tuple(str(item) for item in value.get("cue_terms", [])),
            selection_priority=int(value.get("selection_priority", 500)),
            selection_rule=str(value.get("selection_rule") or value.get("cue") or ""),
            selection_exclusions=tuple(
                str(item) for item in value.get("selection_exclusions", [])
            ),
            transcription_schema=schema,
            concrete_required=tuple(str(item) for item in value.get("concrete_required", [])),
            concrete_any_of=tuple(
                tuple(str(item) for item in branch)
                for branch in value.get("concrete_any_of", [])
            ),
            completeness=dict(value.get("completeness", {})),
            transform_adapter=transform_adapter,
            evidence_units=dict(value.get("evidence_units", {"mode": "top_level"})),
            checker_route=str(value.get("checker_route") or "unsupported"),
            template_policy=dict(value.get("template_policy", {})),
            identity_adapter=identity_adapter,
            identity_fields=tuple(
                str(item) for item in value.get("identity_fields", default_fields)
            ),
            annotation_fields=tuple(
                str(item)
                for item in value.get("annotation_fields", default_annotations)
            ),
        )

    def required_evidence_pointers(self, transcription: dict[str, Any]) -> tuple[str, ...]:
        """Return semantic evidence units, not every primitive JSON leaf."""
        mode = self.evidence_units.get("mode", "top_level")
        if mode == "definition_entries":
            pointers: list[str] = []
            definitions = transcription.get("definitions")
            if isinstance(definitions, list):
                pointers.extend(
                    f"/transcription/definitions/{index}"
                    for index, item in enumerate(definitions)
                    if isinstance(item, dict)
                )
            for field in self.evidence_units.get("fields", []):
                if field != "definitions" and field in transcription:
                    pointers.append(f"/transcription/{field}")
            return tuple(pointers)
        if mode == "top_level":
            return tuple(f"/transcription/{key}" for key in transcription)
        raise ValueError(f"{self.kind}: unsupported evidence-unit mode {mode!r}")

    def completeness_issues(
        self,
        transcription: dict[str, Any],
        signature: dict[str, list[str]],
        *,
        specificity: str,
        glyph_folds: tuple[tuple[str, str], ...] = (),
    ) -> list[dict[str, str]]:
        if specificity != "concrete":
            return []
        issues: list[dict[str, str]] = []
        missing = set(self.concrete_required) - set(transcription)
        if missing:
            issues.append(
                {
                    "code": "CONCRETE_FIELD_REQUIRED",
                    "path": "/transcription",
                    "message": f"missing required fields {sorted(missing)}",
                }
            )
        if self.concrete_any_of and not any(
            set(branch) <= set(transcription) for branch in self.concrete_any_of
        ):
            issues.append(
                {
                    "code": "CONCRETE_ANY_OF",
                    "path": "/transcription",
                    "message": f"requires one complete branch from {list(self.concrete_any_of)}",
                }
            )
        if (
            self.completeness.get("definitions")
            == "all_signature_symbols_exactly_once"
            and transcription.get("interpretation_scope") != "dependency_pair"
        ):
            definitions = transcription.get("definitions")
            if not isinstance(definitions, list):
                issues.append(
                    {
                        "code": "DEFINITIONS_REQUIRED",
                        "path": "/transcription/definitions",
                        "message": "concrete interpretation requires a definitions array",
                    }
                )
            else:
                effective: dict[Any, int] = {}
                revision_errors: list[str] = []
                source_symbols: list[Any] = []
                for index, item in enumerate(definitions):
                    if not isinstance(item, dict):
                        continue
                    symbol = fold_symbol_reference(item.get("symbol"), glyph_folds)
                    revision = item.get("revision", "initial")
                    source_symbols.append(symbol)
                    if symbol in effective:
                        if revision == "replacement":
                            effective[symbol] = index
                        else:
                            revision_errors.append(
                                f"definition[{index}] duplicate {symbol!r} lacks replacement marker"
                            )
                    else:
                        if revision == "replacement":
                            revision_errors.append(
                                f"definition[{index}] replacement {symbol!r} has no prior definition"
                            )
                        effective[symbol] = index
                wanted = set(signature)
                observed = set(effective)
                if observed != wanted or revision_errors:
                    issues.append(
                        {
                            "code": "DEFINITION_SYMBOL_SET",
                            "path": "/transcription/definitions",
                            "message": (
                                f"concrete interpretation requires one effective definition for "
                                f"exactly {sorted(wanted)}; source_symbols={source_symbols} "
                                f"effective={sorted(str(item) for item in observed)} "
                                f"revision_errors={revision_errors}"
                            ),
                        }
                    )
        return issues


@dataclass(frozen=True)
class ConstructionRegistry:
    definitions: dict[str, ConstructionDefinition]

    @classmethod
    def from_config(
        cls,
        value: dict[str, Any],
        *,
        allow_legacy_identity_policy: bool = False,
    ) -> "ConstructionRegistry":
        return cls(
            {
                kind: ConstructionDefinition.from_dict(
                    definition,
                    allow_legacy_identity_policy=allow_legacy_identity_policy,
                )
                for kind, definition in sorted(value.items())
            }
        )

    def get(self, kind: str) -> ConstructionDefinition:
        try:
            return self.definitions[kind]
        except KeyError as error:
            raise KeyError(f"unknown construction kind {kind!r}") from error

    @property
    def kinds(self) -> tuple[str, ...]:
        return tuple(self.definitions)
