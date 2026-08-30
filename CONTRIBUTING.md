# Contributing to CCRC

CCRC welcomes independent audits, replications, and narrowly scoped fixes. The standard is reproducibility, not agreement with the current hypothesis.

## Before opening a pull request

- Keep completed experiment artifacts immutable. Corrections belong in a clearly versioned report or audit addendum.
- Separate preregistered endpoints from exploratory analysis.
- Do not reuse exposed items in a claimed fresh or confirmatory sample.
- Report repairs, harms, abstentions, coverage, actual model calls, and paired uncertainty—not accuracy alone.
- Record the model identifier, quantization, runtime identity, prompts, decoding settings, seeds, parser, dataset revision, and selection procedure.
- Use repository-relative provenance paths; do not publish workstation usernames or absolute local paths in new manifests.
- Include raw machine-readable results, validation output, and a SHA-256 manifest when contributing a completed experiment.
- Run the harness-level test suite and document any environment-dependent tests you could not execute.

## Suggested experiment layout

```text
Experiment_Name/
├── CCRC_Name_Analysis_v1.md
└── ccrc_name_harness_vX_Y_Z/
    ├── README.md
    ├── PREREGISTRATION.md
    ├── config.example.json
    ├── pyproject.toml
    ├── harness/
    ├── tests/
    └── experiment_name/
```

Archived ZIPs may be retained when they provide a hash-pinned release snapshot. Do not add compiled Python files, virtual environments, credentials, or transient runtime logs.

## Scope and licensing

Small pull requests are easier to audit. Avoid repository-wide refactors that alter historical harness behavior unless the change is necessary to correct a demonstrated defect.

By submitting an intentional contribution, you agree that accepted software is licensed under BSD-3-Clause-Clear and accepted research content under CC BY 4.0, as described in [LICENSE-CONTENT.md](./LICENSE-CONTENT.md).
