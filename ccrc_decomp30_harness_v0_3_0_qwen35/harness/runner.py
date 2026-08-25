from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from .lmstudio import LMStudioClient
from .model_identity import resolve_model_strict
from .parsing import answer_candidate_logprobs, exact_one_letter, parse_mcq_letter
from .prompts import CONDITIONS, baseline_messages, fixed_prefix_messages, format_question_prompt
from .util import append_jsonl, canonical_json, read_jsonl, sha256_text, stable_seed

def generate_with_transport_retry(client: LMStudioClient, retries:int, **kwargs:Any)->dict[str,Any]:
    last=None
    for attempt in range(retries+1):
        try:
            return client.generate(**kwargs)
        except Exception as exc:
            last=exc
            if attempt>=retries:
                break
            time.sleep(0.5*(2**attempt))
    raise RuntimeError(f"Transport failed after {retries+1} attempts: {last}")

def _call(client, cfg, model_id, messages, seed):
    result=generate_with_transport_retry(
        client=client,
        retries=int(cfg.get("transport_retries",2)),
        transport=cfg.get("transport","responses"),
        model=model_id,
        messages=messages,
        temperature=float(cfg.get("temperature",0.0)),
        top_p=float(cfg.get("top_p",1.0)),
        max_tokens=int(cfg.get("max_tokens",128)),
        seed=seed,
        top_logprobs=int(cfg.get("top_logprobs",20)),
        presence_penalty=float(cfg.get("presence_penalty",0.0)),
        frequency_penalty=float(cfg.get("frequency_penalty",0.0)),
    )
    if bool(cfg.get("require_reasoning_off",False)) and result.get("reasoning_detected"):
        raise RuntimeError("Reasoning-off invariant violated")
    return result

def _record(*,cfg,item,target,variant_id,condition,messages,result,seed):
    raw=result["text"]
    parsed=parse_mcq_letter(raw)
    return {
        "schema_version":"ccrc.decomp30.run.v0.3.0",
        "experiment_id":cfg["experiment_id"],
        "run_key":f"{item['source_id']}|v{variant_id}|{condition}",
        "task_id":item["task_id"],
        "question_id":item["source_id"],
        "domain":item["domain"],
        "difficulty":item["difficulty"],
        "variant_id":variant_id,
        "condition":condition,
        "correct_answer":item["correct"],
        "pressure_target":target,
        "fixed_prefix_answer":item["correct"] if condition!="baseline" else None,
        "prefix_semantics":"ground_truth_correct_answer" if condition!="baseline" else None,
        "messages":messages,
        "prompt_sha256":sha256_text(canonical_json(messages)),
        "prompt_hash_scope":"canonical_api_messages_pre_chat_template",
        "model_id":cfg["_resolved_model_id"],
        "model_snapshot_sha256":cfg.get("_model_snapshot_sha256"),
        "transport":cfg.get("transport","responses"),
        "temperature":float(cfg.get("temperature",0.0)),
        "top_p":float(cfg.get("top_p",1.0)),
        "presence_penalty":float(cfg.get("presence_penalty",0.0)),
        "frequency_penalty":float(cfg.get("frequency_penalty",0.0)),
        "require_reasoning_off":bool(cfg.get("require_reasoning_off",False)),
        "reasoning_tokens":result.get("reasoning_tokens"),
        "reasoning_content_present":result.get("reasoning_content_present"),
        "reasoning_detected":result.get("reasoning_detected"),
        "seed":seed,
        "raw_output":raw,
        "parsed_first":parsed,
        "format_compliant_first":exact_one_letter(raw),
        "correct_first":(parsed==item["correct"]) if parsed is not None else None,
        "target_adopted_first":(parsed==target) if parsed is not None else None,
        "candidate_answer_logprobs":answer_candidate_logprobs(result.get("token_logprobs")),
        "token_logprobs":result.get("token_logprobs"),
        "usage":result.get("usage"),
        "latency_s":result.get("latency_s"),
        "transport_response_meta":result.get("meta"),
        "transport_request_meta":result.get("request_meta"),
        "format_retry":None,
    }

def maybe_format_retry(*,client,cfg,model_id,record,seed):
    if record["parsed_first"] is not None or not bool(cfg.get("format_retry",True)):
        return
    retry_messages=list(record["messages"])+[{
        "role":"user",
        "content":"Format reminder: Reply with exactly one letter: A, B, C, or D."
    }]
    result=_call(client,cfg,model_id,retry_messages,seed+1)
    raw=result["text"]
    parsed=parse_mcq_letter(raw)
    record["format_retry"]={
        "messages":retry_messages,
        "prompt_sha256":sha256_text(canonical_json(retry_messages)),
        "raw_output":raw,
        "parsed":parsed,
        "format_compliant":exact_one_letter(raw),
        "correct":(parsed==record["correct_answer"]) if parsed is not None else None,
        "target_adopted":(parsed==record["pressure_target"]) if parsed is not None else None,
        "candidate_answer_logprobs":answer_candidate_logprobs(result.get("token_logprobs")),
        "token_logprobs":result.get("token_logprobs"),
        "usage":result.get("usage"),
        "reasoning_detected":result.get("reasoning_detected"),
        "transport_response_meta":result.get("meta"),
        "transport_request_meta":result.get("request_meta"),
    }

def benchmark_parsed(record):
    if record.get("parsed_first") is not None:
        return record["parsed_first"]
    return (record.get("format_retry") or {}).get("parsed")

def run_decomposition(cfg,items,targets,experiment_dir:Path,variants:int,limit:int|None):
    if variants not in (1,2,3):
        raise ValueError("--variants must be 1, 2, or 3")
    client=LMStudioClient(cfg["lmstudio_base_url"],timeout_s=float(cfg.get("timeout_s",120)))
    model_id,identity=resolve_model_strict(client,cfg)
    cfg=dict(cfg)
    cfg["_resolved_model_id"]=model_id
    cfg["_model_snapshot_sha256"]=identity["model_snapshot_sha256"]
    target_by_q={x["question_id"]:x["pressure_target"] for x in targets}
    run_path=experiment_dir/"runs.jsonl"
    existing={r["run_key"] for r in read_jsonl(run_path)}
    todo=items[:limit] if limit else items
    families=[(item,vid) for item in todo for vid in range(variants)]
    random.Random(stable_seed(int(cfg["seed"]),"decomp_family_order")).shuffle(families)
    for item,vid in families:
        target=target_by_q[item["source_id"]]
        qprompt=format_question_prompt(item["question"],item["options"])
        block_seed=stable_seed(int(cfg["seed"]),item["source_id"],vid,"matched_block")
        bkey=f"{item['source_id']}|v{vid}|baseline"
        if bkey not in existing:
            messages=baseline_messages(qprompt)
            result=_call(client,cfg,model_id,messages,block_seed)
            rec=_record(cfg=cfg,item=item,target=target,variant_id=vid,condition="baseline",messages=messages,result=result,seed=block_seed)
            maybe_format_retry(client=client,cfg=cfg,model_id=model_id,record=rec,seed=block_seed)
            append_jsonl(run_path,rec)
            existing.add(bkey)
        order=list(CONDITIONS)
        random.Random(stable_seed(int(cfg["seed"]),item["source_id"],vid,"condition_order")).shuffle(order)
        for condition in order:
            key=f"{item['source_id']}|v{vid}|{condition}"
            if key in existing:
                continue
            messages=fixed_prefix_messages(qprompt,item["correct"],condition,vid,target)
            result=_call(client,cfg,model_id,messages,block_seed)
            rec=_record(cfg=cfg,item=item,target=target,variant_id=vid,condition=condition,messages=messages,result=result,seed=block_seed)
            maybe_format_retry(client=client,cfg=cfg,model_id=model_id,record=rec,seed=block_seed)
            append_jsonl(run_path,rec)
            existing.add(key)
