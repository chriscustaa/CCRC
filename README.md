# CCRC — Causal Contrastive Reasoning Control

CCRC is a measurement-first research program studying when language-model decisions become fragile under context and whether runtime signals can route only the fragile cases to additional cognition.

**Status:** active, early-stage research. CCRC is not a production safety system, a general hallucination fix, or evidence of generalization beyond the tested finite-choice settings.

The repository publishes the full research path: frozen designs, runnable harnesses, raw outputs, hash manifests, independent audit certificates, negative results, and narrowed hypotheses. The objective is evidence that can be inspected and replicated—not a polished story built only from positive outcomes.

## Research question

Can a model remain stable when context is misleading, remain updateable when evidence is valid, and receive extra computation only when the expected repair value exceeds the risk of harm and added inference cost?

CCRC currently separates three functions:

1. **Sense:** measure decision fragility using the top-two A/B/C/D answer-logprob gap.
2. **Allocate:** route only low-margin items to an additional, stateless pass.
3. **Decide:** release, verify, or abstain under a frozen policy.

The gap is treated as a routing signal, never as proof that the leading answer is correct.

## Evidence ledger

Results are specific to the recorded model, quantization, prompts, benchmark slices, and runtime. Different rows are not necessarily direct head-to-head comparisons.

| Experiment | Design | Main result | Disposition |
|---|---|---|---|
| [Syco30](./Experiment_Syco30/Syco30_Qwen2.5_PostRun_Analysis_v1.md) | 30 SycoBench items; Qwen2.5-7B | Misleading context produced large answer movement; baseline margin predicted later susceptibility. | Sensor hypothesis opened; no control claim. |
| [Cross-model Syco30](./Experiment_Syco30/Syco30_Qwen35_CrossModel_Analysis_v1_1_CORRECTED.md) | Same items; Qwen3.5-9B | Susceptibility and the margin relationship replicated with attenuation. | Advance to causal decomposition. |
| [Decomp30](./Experiment_Decomp30/CCRC_Decomp30_Gate_Analysis_v1.md) | 30 questions × 3 prompt families × 6 conditions | A wrong directional verdict drove the dominant shift; authority alone mainly flattened confidence. | Broad authority-bias claim rejected. |
| [Review160](./Experiment_Review160/CCRC_Review160_HeldOut_Gate_Analysis_v1.md) | 160 held-out items; 1,280 runs | Visible self-review repaired 0/48 initial errors; candidate M5 produced a net +1/160 with uncertainty spanning zero. | Visible review and M5 promotion rejected. |
| [Blind80](./Experiment_Blind80/CCRC_Blind80_Gate_Analysis_v1.md) | 80 fresh stems; 560 runs | Hiding the prior answer produced 4 repairs and 2 harms. | Blind re-derivation retained only as a possible actuator. |
| [Consensus600](./Experiment_Concensus600/CCRC_Consensus600_Independent_Gate_Analysis_v1.md) | 600 fresh MMLU items | At the frozen `g < .20` gate, direct D0 produced 7 repairs/2 harms; verifier counts were small and position-confounded. | Favorable exploratory evidence; replication required. |
| [I5-Gated1000](./Experiment_I5Gated1000/CCRC_I5Gated1000_Audit_Certificate_v1.md) | 1,000 MMLU items; 2×2 prompt/controller design | I5 was nonbeneficial; 58 prior-sample duplicates prevented confirmatory interpretation. | Conditional exploratory pass only. |
| [PositionReplay](./Experiment_PositionReplay/CCRC_Position_Replay_Final_Audit_Certificate_v1.md) | 71 items × 4 placements × 2 replicates | Strong within-item representation sensitivity; the verifier topology retained positive expected net after balancing. | Topology survived diagnostic replay; efficacy still unconfirmed. |
| [Trajectory100](./Experiment_Trajectory100/CCRC_Trajectory100_Final_Audit_Certificate_v1.md) | Five stateless measurements on 100 items | The frozen selector produced 5 repairs/4 harms on the primary cohort and failed its net/safety gates. | Five-stage selector retired. |
| [Syco120](./Experiment_Syco120/CCRC_FullLogit_Sycophancy120_Final_Audit_Certificate_v1.md) | 120-item paired full-logit mechanism pilot | Wrong suggestions shifted target odds and caused harm; correct suggestions were not favored over wrong ones. | Target-following supported; truth-selective updating not supported. |

The concise authoritative checkpoint is [RESEARCH_STATE.md](./RESEARCH_STATE.md). Primary artifacts and audit certificates override summaries if they conflict.

## What the evidence supports

- Context can cause large, repeatable movement in finite-choice decisions and answer-token logits.
- Low answer margin identifies behavioral fragility, but mixes recoverable errors with correct-but-fragile answers.
- Showing a model its prior answer can create strong self-conditioning, including when that answer is wrong.
- Blind re-derivation can repair and harm; extra inference is not intrinsically corrective.
- Option representation and display position can materially change answers even when repeated calls at a fixed representation are highly stable.
- Explicit suggestions can move the output distribution regardless of whether the suggestion is true.

## What the evidence does not support

- A universal authority, sycophancy, or truth direction.
- Confidence or logprob margin as a truth score.
- Production promotion of M5, the consensus controller, or the retired trajectory selector.
- A general alignment, hallucination, or safety solution.
- Generalization to open-ended generation or untested model families and runtimes.

## Repository map

Each `Experiment_*` directory is a self-contained research stage. Most contain:

| Artifact | Purpose |
|---|---|
| `CCRC_*_Analysis_*.md` or `*_Audit_Certificate_*.md` | Human-readable result and gate decision |
| `PREREGISTRATION.md` | Frozen hypotheses, endpoints, and kill criteria |
| `harness/` and `tests/` | Executable experiment code and offline tests |
| `experiment_*/` | Finalized raw outputs and derived summaries |
| `hashes.sha256`, `FINALIZED.json`, `PACKAGE_SHA256.txt` | Integrity and finalization records |
| `*.zip` | Archived package or result snapshot retained for provenance |

`Experiment_Concensus600` retains a legacy spelling in its path to avoid breaking existing links. The experiment and report use the correct name, Consensus600.

## Reproducing an experiment

Use Python 3.10 or newer. Each harness pins its own dependencies and exact runbook; there is intentionally no repository-wide environment that silently changes historical packages.

```bash
git clone https://github.com/chriscustaa/CCRC.git
cd CCRC/Experiment_PositionReplay/ccrc_position_replay_v0_7_0_qwen35

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
pytest -q
```

Experiments that call a model were designed for local inference through LM Studio. Before executing one:

1. Read its `PREREGISTRATION.md` and harness-level `README.md`.
2. Copy `config.example.json` to a local config only when the runbook directs it.
3. Match the recorded model, quantization, runtime snapshot, decoding settings, and reasoning state.
4. Run the harness doctor/transport checks before the first experimental cell.
5. Preserve raw rows and manifests; never tune a frozen threshold or endpoint after observing results.

Changing the model, prompts, dataset revision, selection procedure, thresholds, parser, or runtime creates a new replication—not an exact reproduction. Assign a new experiment version and freeze its design before inspecting outcomes.

## Contributing

Independent audits and preregistered replications are welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the minimum evidence expected with a contribution.

## Citation

Citation metadata is provided in [CITATION.cff](./CITATION.cff). When citing a result, also identify the exact experiment report, model, quantization, and repository commit.

## License

Software is licensed under [BSD-3-Clause-Clear](./LICENSE). Original research content is licensed under [CC BY 4.0](./LICENSE-CONTENT.md). Upstream datasets, model weights, runtimes, and third-party material retain their own terms. Neither repository license grants patent rights.
