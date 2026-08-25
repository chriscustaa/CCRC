from harness.dataset import canonical_stem, select_balanced_unique_excluding

def make_questions(n=240):
    out=[]
    domains=["d1","d2","d3","d4"]
    diffs=["easy","medium","hard"]
    for i in range(n):
        out.append({
            "id": f"q{i}",
            "domain": domains[i%len(domains)],
            "difficulty": diffs[i%len(diffs)],
            "question": f"Unique question number {i}?",
            "options": {"A":"a","B":"b","C":"c","D":"d"},
            "correct": "ABCD"[i%4],
        })
    return out

def test_selection_excludes_prior_ids_and_stems():
    qs = make_questions()
    excluded = qs[:30]
    ids = {x["id"] for x in excluded}
    stems = {canonical_stem(x["question"]) for x in excluded}
    selected = select_balanced_unique_excluding(qs, 160, 123, ids, stems)
    assert len(selected) == 160
    assert not ({x["source_id"] for x in selected} & ids)
    assert not ({canonical_stem(x["question"]) for x in selected} & stems)
