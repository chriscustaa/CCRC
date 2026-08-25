from harness.prompts import CONDITIONS,fixed_prefix_messages,format_question_prompt,template_audit
from harness.targets import assign_balanced_targets

def items():
    cs=["A","B","C","D"]*8
    return [{"task_id":f"T{i:03d}","source_id":f"q{i}","correct":c,"question":"Q?","options":{"A":"a","B":"b","C":"c","D":"d"}} for i,c in enumerate(cs[:30],1)]

def test_balanced_targets():
    xs=items(); ts=assign_balanced_targets(xs,20260823); by={x["question_id"]:x for x in ts}; counts={x:0 for x in "ABCD"}
    for item in xs:
        t=by[item["source_id"]]["pressure_target"]; assert t!=item["correct"]; counts[t]+=1
    assert max(counts.values())-min(counts.values())<=1

def test_shared_correct_prefix():
    item=items()[0]; q=format_question_prompt(item["question"],item["options"])
    for cond in CONDITIONS:
        m=fixed_prefix_messages(q,item["correct"],cond,0,"B")
        assert m[1]=={"role":"assistant","content":item["correct"]}

def test_same_target_v_av():
    item=items()[0]; q=format_question_prompt(item["question"],item["options"])
    assert "option B" in fixed_prefix_messages(q,item["correct"],"V",0,"B")[2]["content"]
    assert "option B" in fixed_prefix_messages(q,item["correct"],"AV",0,"B")[2]["content"]

def test_template_audit():
    assert len(template_audit())==15
