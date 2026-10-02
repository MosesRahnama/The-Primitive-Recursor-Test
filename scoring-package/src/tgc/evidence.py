from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .common import sha256_text


@dataclass(frozen=True)
class EvidenceError:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _all_occurrences(source: str, text: str) -> list[int]:
    if not text:
        return []
    starts: list[int] = []
    cursor = 0
    while True:
        start = source.find(text, cursor)
        if start < 0:
            return starts
        starts.append(start)
        cursor = start + 1


def _line_column(source: str, offset: int) -> tuple[int, int]:
    """Return stable 1-based line/column coordinates for a decoded offset."""
    line = source.count("\n", 0, offset) + 1
    previous = source.rfind("\n", 0, offset)
    column = offset + 1 if previous < 0 else offset - previous
    return line, column


def bind_locator(
    locator: dict[str, Any],
    sources: dict[str, str],
    *,
    path: str,
    binding_version: str = "exact-substring-v2",
) -> tuple[dict[str, Any] | None, list[EvidenceError]]:
    errors: list[EvidenceError] = []
    source_id = locator.get("source_id")
    text = locator.get("text")
    occurrence = locator.get("occurrence")
    if source_id not in sources:
        errors.append(EvidenceError("EVIDENCE_SOURCE_UNKNOWN", f"{path}.source_id", str(source_id)))
        return None, errors
    if not isinstance(text, str) or not text:
        errors.append(EvidenceError("EVIDENCE_TEXT_EMPTY", f"{path}.text", "text must be a nonempty exact source substring"))
        return None, errors
    if occurrence is not None and (
        not isinstance(occurrence, int) or isinstance(occurrence, bool) or occurrence < 1
    ):
        errors.append(EvidenceError("EVIDENCE_OCCURRENCE", f"{path}.occurrence", "occurrence must be a positive 1-based integer"))
        return None, errors
    source = sources[source_id]
    starts = _all_occurrences(source, text)
    if not starts:
        errors.append(
            EvidenceError(
                "EVIDENCE_NOT_EXACT",
                f"{path}.text",
                "declared text is not an exact contiguous substring of the source",
            )
        )
        return None, errors
    if occurrence is None:
        if len(starts) != 1:
            errors.append(
                EvidenceError(
                    "EVIDENCE_AMBIGUOUS",
                    path,
                    f"text occurs {len(starts)} times; supply the 1-based occurrence",
                )
            )
            return None, errors
        selected = 1
    else:
        selected = occurrence
        if selected > len(starts):
            errors.append(
                EvidenceError(
                    "EVIDENCE_OCCURRENCE_RANGE",
                    f"{path}.occurrence",
                    f"requested occurrence {selected}, but text occurs {len(starts)} time(s)",
                )
            )
            return None, errors
    start = starts[selected - 1]
    end = start + len(text)
    start_line, start_column = _line_column(source, start)
    end_line, end_column = _line_column(source, end)
    return {
        "source_id": source_id,
        "start": start,
        "end": end,
        "start_line": start_line,
        "start_column": start_column,
        "end_line": end_line,
        "end_column": end_column,
        "text": text,
        "text_sha256": sha256_text(text),
        "occurrence": selected,
        "occurrence_count": len(starts),
        "binding": binding_version,
    }, errors


def bind_anchor_table(
    anchors: dict[str, dict[str, Any]],
    sources: dict[str, str],
    *,
    path: str = "$.anchors",
) -> tuple[dict[str, dict[str, Any]], list[EvidenceError]]:
    """Bind a v3 record-level anchor table and reject duplicate locators.

    A source span is copied exactly once and referred to by ID everywhere else.
    This removes repeated escaped quote payloads and makes evidence reuse
    mechanically auditable.
    """
    bound: dict[str, dict[str, Any]] = {}
    errors: list[EvidenceError] = []
    seen_spans: dict[tuple[str, int, int], str] = {}
    for anchor_id, locator in sorted(anchors.items()):
        anchor_path = f"{path}.{anchor_id}"
        if not isinstance(anchor_id, str) or not anchor_id:
            errors.append(
                EvidenceError(
                    "ANCHOR_ID",
                    anchor_path,
                    "anchor ID must be a nonempty string",
                )
            )
            continue
        if not isinstance(locator, dict):
            errors.append(
                EvidenceError(
                    "ANCHOR_LOCATOR_TYPE",
                    anchor_path,
                    "anchor locator must be an object",
                )
            )
            continue
        item, item_errors = bind_locator(
            locator,
            sources,
            path=anchor_path,
            binding_version="exact-substring-v3",
        )
        errors.extend(item_errors)
        if item is None:
            continue
        span_key = (item["source_id"], item["start"], item["end"])
        if span_key in seen_spans:
            errors.append(
                EvidenceError(
                    "ANCHOR_DUPLICATE_LOCATOR",
                    anchor_path,
                    f"same exact source span already defined as {seen_spans[span_key]!r}; reuse that anchor ID",
                )
            )
            continue
        seen_spans[span_key] = anchor_id
        bound[anchor_id] = {"anchor_id": anchor_id, **item}
    return bound, errors


def bind_locators(
    locators: list[dict[str, Any]],
    sources: dict[str, str],
    *,
    path: str,
) -> tuple[list[dict[str, Any]], list[EvidenceError]]:
    bound: list[dict[str, Any]] = []
    errors: list[EvidenceError] = []
    for index, locator in enumerate(locators):
        if not isinstance(locator, dict):
            errors.append(
                EvidenceError(
                    "EVIDENCE_LOCATOR_TYPE",
                    f"{path}[{index}]",
                    "evidence locator must be an object",
                )
            )
            continue
        item, item_errors = bind_locator(locator, sources, path=f"{path}[{index}]")
        errors.extend(item_errors)
        if item is not None:
            bound.append(item)
    return bound, errors
