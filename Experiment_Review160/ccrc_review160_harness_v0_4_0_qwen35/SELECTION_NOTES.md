# Selection Notes — Review160 v0.4.0

The fourth experiment uses **semantic-stem holdout**, not merely source-ID holdout.

SycoBench-600 contains many option-permuted repetitions of the same underlying question stem. The prior 30-item experiment consumed semantic stems in every domain. Reusing another option permutation of one of those stems would make the fourth experiment less genuinely held out.

Accordingly, v0.4.0 excludes:

1. all 30 prior source IDs; and
2. every upstream row whose canonical question stem matches one of those prior 30.

This leaves 242 fresh unique semantic stems in SycoBench v1.0.1. The deterministic 160-item selection therefore uses capacity-proportional domain/difficulty stratification rather than artificial equal-domain quotas.

With the frozen seed and current pinned dataset, the expected selected distribution is:

```text
analogies               17
basic_math              47
causal_reasoning         1
common_sense             1
logical_reasoning       17
reading_comprehension   11
scientific_facts        22
word_problems           44

easy                    30
medium                  65
hard                    65
```

The low causal-reasoning/common-sense counts are a property of SycoBench's repeated-stem construction after strict semantic exclusion, not a sampling bug.

## Interpretation consequence

The 160-item result is a strong **fresh semantic holdout screen**, but it is not evenly domain-general. Any promotion decision should therefore be based on the overall paired result plus domain-stratified inspection, and later replication should use a genuinely new question source if broad domain balance becomes necessary.

The harness writes the actual domain and difficulty counts into `manifest.json` at prepare time so this limitation is part of the immutable record.
