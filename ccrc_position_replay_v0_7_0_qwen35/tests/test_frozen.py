import json
from pathlib import Path

from harness.validate import verify_frozen

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_hashes_and_provenance():
    assert verify_frozen(ROOT / "frozen") == []
    provenance = json.loads((ROOT / "frozen" / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["counts"] == {
        "all_evidence_unique_stems": 1812,
        "all_items": 1000,
        "consensus600_overlaps": 58,
        "deduplicated_primary_items": 942,
        "planned_cells": 568,
        "replay_items": 71,
        "theta_020_gate": 35,
        "theta_020_verifier_escalation": 20,
    }
    assert provenance["original_theta_020_controller"]["repairs"] == 6
    assert provenance["original_theta_020_controller"]["harms"] == 3
    assert provenance["design"]["eight_cell_majority_forbidden"] is True

