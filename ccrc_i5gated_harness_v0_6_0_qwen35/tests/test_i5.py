from harness.prompts import I5_CONTROL, canonical_from_displayed, core_messages, verifier_messages
from harness.runner import verifier_orders

ITEM = {"question": "Q?", "choices": ["one", "two", "three", "four"]}


def text(messages):
    return "\n".join(x["content"] for x in messages)


def test_i5_only_treatment_branches():
    assert I5_CONTROL not in text(core_messages(ITEM, i5=False, blind=False))
    assert I5_CONTROL in text(core_messages(ITEM, i5=True, blind=False))
    assert I5_CONTROL in text(core_messages(ITEM, i5=True, blind=True))
    assert I5_CONTROL not in text(verifier_messages(ITEM, [1, 0, 2, 3]))


def test_verifier_is_blind_and_permuted():
    o1, o2 = verifier_orders(123, "q1")
    assert o1 != [0, 1, 2, 3]
    assert o2 != [0, 1, 2, 3]
    assert o1 != o2
    assert "independently from scratch" in text(verifier_messages(ITEM, o1)).lower()
    displayed = "A"
    assert canonical_from_displayed(displayed, [2, 0, 1, 3]) == "C"
    assert canonical_from_displayed(None, [2, 0, 1, 3]) is None
