from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

LETTERS=["A","B","C","D"]

def _rank(seed:int, task_id:str, letter:str)->bytes:
    return hashlib.sha256(f"{seed}|{task_id}|{letter}".encode()).digest()

def assign_balanced_targets(items:list[dict[str,Any]], seed:int)->list[dict[str,Any]]:
    counts=Counter()
    out=[]
    for item in sorted(items,key=lambda x:x["task_id"]):
        allowed=[x for x in LETTERS if x != item["correct"]]
        min_count=min(counts[x] for x in allowed)
        candidates=[x for x in allowed if counts[x]==min_count]
        target=min(candidates,key=lambda x:_rank(seed,item["task_id"],x))
        counts[target]+=1
        out.append({
            "task_id":item["task_id"],
            "question_id":item["source_id"],
            "correct_answer":item["correct"],
            "pressure_target":target,
            "assignment_method":"balanced_deterministic_global",
        })
    return out
