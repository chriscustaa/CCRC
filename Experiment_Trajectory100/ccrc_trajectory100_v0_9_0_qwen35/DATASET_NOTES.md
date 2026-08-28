# Dataset and provenance notes

The frozen sample is reconstructed from two audited local experiment bundles:

- `experiment_consensus600.zip`
- `experiment_i5gated1000.zip`

All internal source hashes are reverified by `tools/build_frozen.py`. Fifty-eight I5 items overlapping consensus600 are removed before selection. The resulting pre-confirmatory pool contains 1,542 unique stems.

The 60-item low-gap core comprises 27 consensus600 rows and 33 fresh-only I5 rows. Historical construction labels are 43 wrong and 17 correct. The 40 controls balance the full pilot to 50 historical wrong and 50 historical correct.

Questions originate from the MMLU test split. This package includes only the 100 selected rows needed to reproduce the pilot. See `LICENSE_NOTES.md` for source licensing notes.
