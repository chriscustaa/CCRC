# Selection Notes

The holdout is selected from `cais/mmlu` `all/test` at the exact revision in the config.

Algorithm:
1. Validate four choices and a canonical A-D answer.
2. Deduplicate canonicalized question stems.
3. Group by subject.
4. Allocate `N / subject_count` as evenly as possible; deterministic hashed subject order assigns remainder slots.
5. Within each subject, rank rows by SHA-256 over seed, subject, source index, question, and choices.
6. Select the first quota rows. The correct answer is **not** an input to rank.
7. Freeze `items.jsonl` and its SHA-256 in `manifest.json` before inference.

The selection is designed to avoid outcome-driven cherry-picking. It is not a claim that MMLU is uncontaminated with respect to model pretraining.
