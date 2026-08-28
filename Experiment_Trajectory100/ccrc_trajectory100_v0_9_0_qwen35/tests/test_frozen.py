import json
from collections import Counter
from pathlib import Path

from harness.validate import verify_frozen

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def test_frozen_hashes_and_selection():
    assert verify_frozen(ROOT / "frozen") == []
    items = load_jsonl(ROOT / "frozen" / "pilot_items.jsonl")
    assert Counter(x["sample_stratum"] for x in items) == Counter({"low_gap_core": 60, "near_gap_control": 40})
    assert Counter(x["prior_baseline_correct"] for x in items) == Counter({True: 50, False: 50})
    core = [x for x in items if x["sample_stratum"] == "low_gap_core"]
    assert sum(not x["prior_baseline_correct"] for x in core) == 43
    provenance = json.loads((ROOT / "frozen" / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["protected_confirmatory_7818_used_for_selection_or_tuning"] is False
    assert provenance["counts"]["deduplicated_preconfirmatory_pool"] == 1542
