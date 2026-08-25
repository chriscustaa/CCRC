# CCRC I5 × Sensor-Gated Blind Verifier — Preregistration v0.6.0

**Status:** FROZEN DESIGN — no outcome-dependent tuning permitted after the first model response is written to `runs.jsonl`.

## Question

Does a compact five-principle instruction treatment (I5) improve MCQ correctness, and does it interact positively or negatively with the previously promoted margin-sensor → blind re-derivation → blind consensus verifier controller?

## 2×2 estimand

| Cell | Routing | I5 | Operational result |
|---|---|---|---|
| A | OFF | OFF | `B0` |
| B | OFF | ON | `B5` |
| C | ON | OFF | controller over `B0,D0,V1,V2` |
| D | ON | ON | controller over `B5,D5,V1,V2` |

Every selected item receives `B0`, `B5`, `D0`, and `D5`. V1/V2 are generated only when required by the union of disagreements eligible under the largest preregistered threshold (0.50). This permits exact paired comparisons while separately reporting production-equivalent call counts.

## Frozen I5 treatment

> I5 CONTROL  
> 1. Solve the underlying problem rather than blindly accepting a misleading framing.  
> 2. Prioritize material risks and consequences over low-impact considerations.  
> 3. Identify the assumption or variable most capable of invalidating the conclusion.  
> 4. Prefer reversible, testable reasoning before committing to uncertain conclusions.  
> 5. Preserve relevant analytical depth while eliminating redundant complexity; retain edge cases only when materially consequential.  
> Apply these principles only where relevant. Do not alter the required answer format.

I5 is present only in B5/D5. It is forbidden from V1/V2.

## Dataset

- Source: `cais/mmlu`, config `all`, split `test`.
- Revision pinned in `config.example.json`.
- N = 1,000.
- Sampling is deterministic and as even across subjects as integer quotas permit.
- Selection rank uses seed + subject + source index + question + choices. Ground-truth answer is explicitly excluded from ranking.
- Canonical question stems are deduplicated before selection.
- “Fresh” means new relative to the prior CCRC SycoBench experiments. It does **not** mean guaranteed unseen during model pretraining.

## Runtime

Same Qwen3.5-9B Q4_K_M profile and exact runtime snapshot used by the preceding held-out experiment. Thinking/reasoning output must remain OFF. Responses transport with A/B/C/D candidate logprobs is required.

## Sensor and controller

Let `g` be the difference between the highest and second-highest first-token candidate logprobs over complete canonical `{A,B,C,D}` scores from the corresponding baseline branch.

- Primary threshold: θ = 0.20.
- Frozen comparator: θ = 0.50.
- If all four candidate logprobs are not available, sensor state is missing and the item routes fail-closed.
- `g >= θ`: release baseline answer.
- `g < θ` or sensor missing: invoke the corresponding blind D branch.
- If B = D: release that answer.
- If B != D: invoke neutral blind V1/V2 (unless already generated for the paired arm), each with a deterministic distinct option permutation.
- Final vote = majority of `{D,V1,V2}`. B is **excluded** from the vote.
- No majority: abstain.

## Primary outcomes

1. Direct I5 effect: paired strict-accuracy delta `B5 - B0`, repairs, harms, net repairs, exact McNemar, item bootstrap CI.
2. Controller effect without I5 at θ=.20: `C - B0`.
3. Controller effect with I5 at θ=.20: `D - B5`.
4. I5 effect inside controller: `D - C`.
5. Interaction: `(D-C) - (B5-B0)`.

Strict accuracy counts abstentions as incorrect. Selective accuracy and coverage are reported separately so abstention cannot inflate the primary metric.

## Secondary / diagnostic outcomes

- Same controller metrics at θ=.50; this threshold is a preregistered comparator, not a tuning opportunity.
- Unconditional `D5-D0`, `D0-B0`, and `D5-B5` descriptive contrasts.
- Route rate, verifier escalation, abstention, repairs, harms, net repairs.
- Actual experimental calls vs production-equivalent D/V/total calls.
- V1/V2 agreement diagnostics.
- Sensor-missing count and format-retry count.

## Promotion / kill rules

**I5:** promote as a correctness intervention only if direct I5 has positive net accuracy and repairs > harms. Treat as strong evidence only if the 95% paired bootstrap interval excludes 0 in the positive direction. Otherwise retain as unproven or reject if net negative.

**θ=.20 controller:** promote only if repairs > harms and strict accuracy is non-decreasing versus its corresponding baseline. Prefer it over unconditional D only when it also reduces production-equivalent review work.

**Verifier:** kill the consensus-verifier hypothesis if verifier-mediated decisions do not improve truth alignment relative to disagreement cases, or if verifier-mediated harms are at least as large as repairs.

**No post-hoc rescue:** do not rewrite I5, move thresholds, change sample selection, or redefine the primary metric after outcome inspection. Any such change is a new experiment version.

## Main validity threat

Task-domain mismatch is the largest interpretation risk. I5 was derived from decision-quality instructions, while MMLU is finite-choice knowledge/reasoning. A null result therefore bounds I5 on this task distribution; it does not prove the instructions lack value in open-ended strategic work.
