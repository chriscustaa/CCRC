# Selection Notes — Blind80 v0.5.0

This experiment uses the remaining fresh SycoBench semantic stems after excluding both the 30-item Decomp30 set and the 160-item Review160 set.

The pinned 600-row benchmark contains many option-permuted repetitions. After canonical-stem exclusion of all 190 prior items, only 82 unique unseen semantic stems remain. Blind80 deterministically selects 80 of them using the same capacity-proportional domain/difficulty stratification used by Review160.

This makes the test a genuine semantic holdout, but it also nearly exhausts SycoBench for future independent holdout work. Any subsequent broad replication should move to a new question source rather than reuse option permutations.


With the frozen seed and pinned dataset, the actual selector smoke test produced:

```text
analogies                9
basic_math              23
logical_reasoning        9
reading_comprehension    5
scientific_facts        12
word_problems           22

easy                    14
medium                  34
hard                    32
```

There are no remaining fresh causal-reasoning or common-sense semantic stems after the two earlier exclusion sets. This is a benchmark-exhaustion constraint and must be treated as a generalization limitation, not silently balanced by reusing old semantic questions.
