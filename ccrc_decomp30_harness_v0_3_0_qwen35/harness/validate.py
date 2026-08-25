from __future__ import annotations
from collections import Counter,defaultdict
from pathlib import Path
from .prompts import CONDITIONS,baseline_messages,fixed_prefix_messages,format_question_prompt
from .util import canonical_json,read_json,read_jsonl,sha256_text

def validate_experiment(experiment_dir:Path,require_full:bool=False):
    items=read_jsonl(experiment_dir/"items.jsonl")
    targets=read_jsonl(experiment_dir/"targets.jsonl")
    runs=read_jsonl(experiment_dir/"runs.jsonl")
    manifest=read_json(experiment_dir/"manifest.json")
    errors=[];warnings=[]
    item_by={x["source_id"]:x for x in items}
    target_by={x["question_id"]:x["pressure_target"] for x in targets}
    if len(item_by)!=len(items):errors.append("Duplicate source_id")
    if set(target_by)!=set(item_by):errors.append("targets.jsonl does not exactly match items.jsonl")
    for qid,t in target_by.items():
        if t==item_by[qid]["correct"]:errors.append(f"Target equals correct: {qid}")
    keys=[r.get("run_key") for r in runs]
    if len(keys)!=len(set(keys)):errors.append("Duplicate run_key")
    run_by={r["run_key"]:r for r in runs}
    frozen_model=(manifest.get("planned_model") or {}).get("model_id")
    frozen_snapshot=(manifest.get("planned_model") or {}).get("observed_snapshot_sha256")
    for r in runs:
        qid=r["question_id"]
        if qid not in item_by:
            errors.append(f"Unknown question: {qid}");continue
        item=item_by[qid];target=target_by[qid]
        if r.get("pressure_target")!=target:errors.append(f"Target drift: {r['run_key']}")
        if r.get("model_id")!=frozen_model:errors.append(f"Model drift: {r['run_key']}")
        if r.get("model_snapshot_sha256")!=frozen_snapshot:errors.append(f"Runtime drift: {r['run_key']}")
        if r.get("reasoning_detected"):errors.append(f"Reasoning detected: {r['run_key']}")
        if float(r.get("temperature",-1))!=0.0:errors.append(f"Temperature drift: {r['run_key']}")
        if float(r.get("top_p",-1))!=1.0:errors.append(f"top_p drift: {r['run_key']}")
        if float(r.get("presence_penalty",-999))!=0.0:errors.append(f"presence penalty drift: {r['run_key']}")
        if float(r.get("frequency_penalty",-999))!=0.0:errors.append(f"frequency penalty drift: {r['run_key']}")
        qprompt=format_question_prompt(item["question"],item["options"])
        if r["condition"]=="baseline":
            expected=baseline_messages(qprompt)
            if r.get("fixed_prefix_answer") is not None:errors.append(f"Baseline prefix present: {r['run_key']}")
        else:
            expected=fixed_prefix_messages(qprompt,item["correct"],r["condition"],int(r["variant_id"]),target)
            if r.get("fixed_prefix_answer")!=item["correct"]:errors.append(f"Fixed prefix drift: {r['run_key']}")
            assistant=[m["content"] for m in r["messages"] if m["role"]=="assistant"]
            if assistant!=[item["correct"]]:errors.append(f"Assistant prefix mismatch: {r['run_key']}")
        if r.get("messages")!=expected:errors.append(f"Prompt mismatch: {r['run_key']}")
        if r.get("prompt_sha256")!=sha256_text(canonical_json(expected)):errors.append(f"Prompt hash mismatch: {r['run_key']}")
        cand=r.get("candidate_answer_logprobs") or {}
        if item["correct"] not in cand or target not in cand:warnings.append(f"Missing correct/target logprob: {r['run_key']}")
        if r.get("parsed_first") is None and not r.get("format_retry"):warnings.append(f"Unparsed without retry: {r['run_key']}")
    variants=defaultdict(set)
    for r in runs:variants[r["question_id"]].add(int(r["variant_id"]))
    for qid,vids in variants.items():
        for vid in vids:
            for cond in ["baseline"]+CONDITIONS:
                k=f"{qid}|v{vid}|{cond}"
                if k not in run_by:errors.append(f"Missing matched run: {k}")
    if require_full:
        expected_count=len(items)*3*(1+len(CONDITIONS))
        if len(runs)!=expected_count:errors.append(f"Full count mismatch: expected {expected_count}, observed {len(runs)}")
        for qid in item_by:
            for vid in range(3):
                for cond in ["baseline"]+CONDITIONS:
                    k=f"{qid}|v{vid}|{cond}"
                    if k not in run_by:errors.append(f"Full run missing: {k}")
    return {"ok":not errors,"n_items":len(items),"n_targets":len(targets),"n_runs":len(runs),"require_full":require_full,"errors":errors,"warnings":warnings}
