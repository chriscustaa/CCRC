from harness.dataset import canonical_stem, select_balanced_unique_excluding

def make_questions(n=400):
    domains=["d1","d2","d3","d4"]
    diffs=["easy","medium","hard"]
    out=[]
    for i in range(n):
        out.append({
            "id":f"q{i}",
            "domain":domains[i%4],
            "difficulty":diffs[i%3],
            "question":f"Unique semantic question {i}?",
            "options":{"A":"a","B":"b","C":"c","D":"d"},
            "correct":"ABCD"[i%4],
        })
    return out

def test_80_fresh_after_190_excluded():
    qs=make_questions()
    excluded=qs[:190]
    ids={x["id"] for x in excluded}
    stems={canonical_stem(x["question"]) for x in excluded}
    selected=select_balanced_unique_excluding(qs,80,20260823,ids,stems)
    assert len(selected)==80
    assert not ({x["source_id"] for x in selected} & ids)
    assert not ({canonical_stem(x["question"]) for x in selected} & stems)
    assert len({canonical_stem(x["question"]) for x in selected})==80
