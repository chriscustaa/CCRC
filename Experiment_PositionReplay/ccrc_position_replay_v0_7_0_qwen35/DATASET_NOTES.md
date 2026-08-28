# Dataset notes

The frozen replay contains 71 MMLU four-choice items selected by the audited I5-1000 verifier-routing policy. It also contains the 1,000-item I5 backbone needed to preserve provenance and reconstruct the controller. No new item is selected after seeing replay outcomes.

MMLU is used here as a fixed candidate-space mechanism test, not as a clean measure of frontier model knowledge. The benchmark may have appeared in model training data. The identifying comparison is within item: the same question and choices are shown with the correct answer in every display slot under two crossed replicate streams.

The I5-1000 source manifest records:

- dataset: `cais/mmlu`;
- configuration: `all`;
- split: `test`;
- revision: `b1bdbcba68d4f5c88d91a8f2685124f148fd1fd0`;
- selected items: 1,000 across 57 subjects.

Fifty-eight I5 items exactly overlap consensus600. The primary policy analysis excludes them. The full 1,000-item analysis is secondary. Replay collection still covers the frozen 71-item verifier union because the within-item slot analysis is descriptive/identifying and because pre-outcome removal would change the frozen call population.

The file `frozen/all_evidence_stems.jsonl` contains only canonical fingerprints and provenance references for the 1,812 unique MCQs in the five-bundle evidence lineage. A future confirmatory sample must exclude this union.

