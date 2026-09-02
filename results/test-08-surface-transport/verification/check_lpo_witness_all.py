#!/usr/bin/env python3
"""Certification-pass extension of the bundle's LPO witness checker.

The bundle ships `scripts/check_lpo_witness.py`, which checks the two claimed
precedences only against the UNBLINDED `.ari` transports. This script reuses the
bundle's own parser and `lpo_gt` implementation unchanged and additionally checks
the BLINDED transports, by pushing each claimed precedence through
`BLINDING_MAP.json`. It also reports, for comparison, the precedence TTT2
independently searched and recorded in each `*_lpo.cpf`.

This is a static witness check. It is not a substitute for the CeTA-replayed CPF.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

BUNDLE = pathlib.Path(
    r"<manuscript repository, not distributed>"
    r"\systems\GPT-Pro\surface_transport_bundle\surface_transport_bundle"
)
RUNS = pathlib.Path(__file__).resolve().parent / "ttt2"


def _load_module(name: str):
    path = BUNDLE / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(BUNDLE / "scripts"))
_load_module("validate_transport")
witness = _load_module("check_lpo_witness")

# The two precedences claimed by the bundle, high to low.
CLAIMED = {
    "bmssp_exec_walk_weight": witness.WITNESSES["bmssp_exec_walk_weight.ari"],
    "equality_extract_prefix_letlift": witness.WITNESSES[
        "equality_extract_prefix_letlift.ari"
    ],
}

# Which run file carries the TTT2 precedence for each system/costume.
CPF = {
    ("bmssp_exec_walk_weight", "unblinded"): "B_unblinded_lpo.cpf",
    ("bmssp_exec_walk_weight", "blinded"): "B_blinded_lpo.cpf",
    ("equality_extract_prefix_letlift", "unblinded"): "E_unblinded_lpo.cpf",
    ("equality_extract_prefix_letlift", "blinded"): "E_blinded_lpo.cpf",
}


def ttt2_precedence(cpf_name: str) -> dict[str, int]:
    root = ET.parse(RUNS / cpf_name).getroot()
    out: dict[str, int] = {}
    for entry in root.iter():
        if entry.tag.split("}")[-1] != "statusPrecedenceEntry":
            continue
        fields = {c.tag.split("}")[-1]: c.text for c in entry}
        out[fields["name"]] = int(fields["precedence"])
    return out


def check(ari_name: str, precedence: list[str], label: str) -> bool:
    sig, rules = witness.load(BUNDLE / "trs" / ari_name)
    missing = set(sig) - set(precedence)
    if missing:
        print(f"FAIL {label}: precedence omits {sorted(missing)}")
        return False
    rank = {sym: len(precedence) - i for i, sym in enumerate(precedence)}
    failures = [
        idx
        for idx, (lhs, rhs) in enumerate(rules, 1)
        if not witness.lpo_gt(lhs, rhs, sig, rank)
    ]
    if failures:
        print(f"FAIL {label}: LPO failed on rules {failures}")
        return False
    print(f"OK   {label}: all {len(rules)} rules oriented; " + " > ".join(precedence))
    return True


def main() -> int:
    blinding = json.loads((BUNDLE / "BLINDING_MAP.json").read_text(encoding="utf-8"))
    ok = True

    for system, claimed in CLAIMED.items():
        ok &= check(f"{system}.ari", list(claimed), f"{system} [unblinded, claimed]")

        symbols = blinding[system]["symbols"]
        transported = [symbols[s] for s in claimed]
        ok &= check(
            f"{system}_blinded.ari",
            transported,
            f"{system} [blinded, claimed pushed through BLINDING_MAP]",
        )

        # Report TTT2's own searched precedence and whether it is blinding-invariant.
        unb = ttt2_precedence(CPF[(system, "unblinded")])
        bli = ttt2_precedence(CPF[(system, "blinded")])
        pushed = {symbols[s]: v for s, v in unb.items()}
        same = pushed == bli
        print(f"     TTT2 searched precedence  unblinded: {unb}")
        print(f"     TTT2 searched precedence  blinded  : {bli}")
        print(f"     TTT2 precedence invariant under BLINDING_MAP: {same}")
        if not same:
            ok = False
        # The claimed witness and the TTT2 witness are different objects; both
        # orient. Record the distinction rather than collapsing it.
        claimed_rank = {s: len(claimed) - i for i, s in enumerate(claimed)}
        print(
            f"     claimed witness == TTT2 witness (as a ranking): "
            f"{sorted(claimed_rank.items()) == sorted(unb.items())}"
        )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
