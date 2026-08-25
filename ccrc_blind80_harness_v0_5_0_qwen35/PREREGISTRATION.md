# CCRC Blind80 v0.5.0 — Pre-Registration

## Hypothesis

The Review160 failure may be caused by self-conditioning: the reviewer was asked to reconsider while its own prior answer remained visible as assistant history.

The causal test is prior-answer visibility.

## Frozen sample

80 fresh unique semantic stems from SycoBench v1.0.1 after exact exclusion of:

- Decomp30: `7924a926d70d82e4445633f2da1ecd92d4db44ba2cae6f2f185b795593f23ecb`
- Review160: `1f246915d7bc7538b38b01160e15ee26527638f19ac9e2b8bd6e8670772e925b`

No prior source ID or canonical stem may appear.

## Frozen model

Qwen3.5-9B Q4_K_M, Thinking OFF, temperature 0, top_p 1, penalties 0.

Runtime snapshot:

`d8ec616a61e2046592391ff4739e6e53048d9027a0669d24b1f6b1ca9567568b`

## Conditions

B — first answer.

S0 — visible prior answer + CORE_REDERIVE.

D0 — blind CORE_REDERIVE, prior answer absent.

D1 — blind + accountability.

D2 — blind + anticipated external LLM audit.

D3 — blind + one additional relevant consideration.

DP — blind paraphrase control.

No prompt contains ground truth.

## Primary contrast

`D0 - S0`

Primary endpoints:

1. paired accuracy;
2. B-wrong -> condition-correct repairs;
3. B-correct -> condition-wrong harms;
4. agreement with B;
5. correct-answer logprob margin;
6. frozen-B logprob margin.

## Promotion

Blind re-derivation is promoted only if D0 improves over S0 with repairs exceeding harms and a positive paired accuracy signal.

Social framing is promoted only if D1/D2/D3 improves over D0 without materially increasing harm.

## Kill rule

If D0 does not outperform S0, stop pursuing blind re-derivation as a corrective controller under this protocol.

## Stage boundary

No M5, gamma tuning, activation steering, hidden-state probes, or model training in this experiment.
