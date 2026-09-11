# Validation report

Generated 2026-09-11T21:39:49.836395+00:00 · 6 independently generated cases (achieved count, not planned)

All results below are on synthetic data. Synthetic ranking accuracy is not a measurement of real-world attribution accuracy, and no real matched incident has been scored here.

## Attribution — per case

| Case | Family | Vessels | Candidates | Expected | Method | Correct | Naive baseline | Naive correct | Top IoU | Lead retained | Smallest flip |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| case_0001 | decoy | 6 | 3 | named_candidate | `419336692` | yes | `419824090` | no | 0.688 | 100% | none |
| case_0002 | moving_discharge | 6 | 4 | named_candidate | `419858938` | yes | `419453172` | no | 0.627 | 100% | none |
| case_0003 | absent_source | 5 | 2 | unknown_source | `unknown_source` | yes | `419769953` | no | 0.088 | 70% | 0.5 |
| case_0004 | crowded | 11 | 5 | named_candidate | `419255379` | yes | `419369344` | no | 0.677 | 94% | 0.5 |
| case_0005 | decoy | 6 | 3 | named_candidate | `419184924` | yes | `419958088` | no | 0.694 | 100% | none |
| case_0006 | absent_source | 5 | 3 | unknown_source | `unknown_source` | yes | `419738652` | no | 0.043 | 51% | 0.5 |

## Attribution — aggregates

| Measure | Result |
| --- | --- |
| Source-present cases | 4 |
| Forward-replay Top-1 | 4/4 = 100% [95% CI 51–100%] |
| Forward-replay Top-3 | 4/4 = 100% [95% CI 51–100%] |
| Naive proximity Top-1 | 0/4 = 0% [95% CI 0–49%] |
| Top-1 gain over naive proximity | +100 percentage points |
| Source-absent cases | 2 |
| Correct abstentions | 2/2 = 100% [95% CI 34–100%] |
| False named attribution | 0/2 = 0% [95% CI 0–66%] |

> The intervals matter more than the point estimates at this sample size. A perfect score over a handful of cases still admits a wide true rate, and the interval is the honest statement of that. The planned benchmark (120 development / 40 validation / 40 source-present / 60 source-absent locked test cases) is not what was achieved; the achieved count is in the header.

> The naive baseline has no abstention mechanism: on source-absent cases it always names its nearest vessel. That is scored as incorrect because it is the operationally relevant failure — a confident name where no observable source exists.

## Detection — classical baseline vs learned model

| Split | Model | IoU on true oil | Recall | Precision | FP rate (look-alike) | FP rate (clean) | n |
| --- | --- | --- | --- | --- | --- | --- | --- |
| val | classical baseline | 0.676 | 0.682 | 0.993 | 0.000 | 0.000 | 15/8/8 |
| test (locked) | classical baseline | 0.688 | 0.696 | 0.891 | 0.000 | 0.000 | 20/12/12 |
| — | trained U-Net | **not evaluated** | — | — | — | — | — |

> Recall and precision are pixel-level on oil scenes; the two FP rates are per scene on scenes with no oil in them. Pixel accuracy is not reported, because on scenes that are mostly background it is high regardless of whether the slick was found.

> **The recall target of 0.85 (masterplan p.15) is not met by the classical baseline: val 0.682; test 0.696.** IoU clears its 0.65 target and the false-positive rates are 0.000, so the baseline is conservative rather than inaccurate — it rejects patchy regions, which buys precision and costs recall. That trade-off is the concrete case for the learned model: the number to beat is recall, not IoU. Reported as a miss rather than omitted.

> The U-Net is implemented and trainable but has not been trained and evaluated here, so the defensible detection claim is the baseline number alone. An architected-but-untrained model is a design, not a result. Running `scripts/train_unet.py` writes `data/detection/unet_eval.json` and this table picks it up automatically.

## Ask Slick Trace — frozen question suite

| Measure | Result |
| --- | --- |
| Total questions | 40 |
| Overall pass | 40/40 = 100% [95% CI 91–100%] |
| Supported questions interpreted correctly | 29/29 = 100% [95% CI 88–100%] |
| Unsupported / ambiguous refused correctly | 11/11 = 100% [95% CI 74–100%] |
| Supported answers carrying citations | 29/29 = 100% [95% CI 88–100%] |

| Category | Passed |
| --- | --- |
| candidate_list | 2/2 |
| comparison | 3/3 |
| coverage | 3/3 |
| forecast | 3/3 |
| next_observation | 2/2 |
| provenance | 2/2 |
| rank_stability | 4/4 |
| refusal_not_implemented | 2/2 |
| refusal_out_of_domain | 5/5 |
| refusal_underspecified | 4/4 |
| time_window | 3/3 |
| time_window_midnight | 1/1 |
| top_candidate | 3/3 |
| vessel_history | 3/3 |

> Refusals are scored as passes. A system that answers everything has not been tested for grounding, so the out-of-domain and under-specified questions are part of the suite rather than excluded from it.

## Coverage-aware matching — hidden-AIS experiment

| Case | Condition | Hidden-AIS recovery | False unmatched-alert | Mistaken promotion |
| --- | --- | --- | --- | --- |
| case_0001 | selective | 0.8209 (55/67) | 0.2927 (36/123) | 0.3 (12/40) |
| case_0001 | coverage_failure | 0.875 (42/48) | 0.31 (31/100) | 0.0 (0/34) |
| case_0002 | selective | 0.825 (66/80) | 0.2886 (43/149) | 0.35 (14/40) |
| case_0002 | coverage_failure | 0.85 (85/100) | 0.2378 (39/164) | 0.3 (12/40) |
| case_0003 | selective | 0.8 (64/80) | 0.25 (32/128) | None (0/0) |
| case_0003 | coverage_failure | 0.8286 (58/70) | 0.2683 (33/123) | None (0/0) |
| case_0004 | selective | 0.8108 (90/111) | 0.3317 (68/205) | 0.225 (9/40) |
| case_0004 | coverage_failure | 0.8556 (77/90) | 0.3704 (70/189) | 0.0 (0/35) |
| case_0005 | selective | 0.8333 (60/72) | 0.2602 (32/123) | 0.2 (8/40) |
| case_0005 | coverage_failure | 0.8788 (58/66) | 0.2821 (33/117) | 0.0 (0/34) |
| case_0006 | selective | 0.8 (64/80) | 0.252 (32/127) | None (0/0) |
| case_0006 | coverage_failure | 0.8302 (88/106) | 0.1724 (25/145) | None (0/0) |

> Operating point: match gate 0.02°, contact position noise 0.012°, detector miss rate 0.15, false detection rate 0.15. A rate without its operating point is not a comparable measurement.

## Next-observation advisor — held-out check

| Case | Recommended | Least informative | Separation at recommended | Separation at least informative | Helped |
| --- | --- | --- | --- | --- | --- |
| case_0001 | +3h | +12h | 0.2456 | 0.0001 | yes |
| case_0002 | +3h | +24h | 0.5712 | 0.2527 | yes |
| case_0004 | +24h | +6h | 0.0429 | 0.079 | no |
| case_0005 | +3h | +24h | 0.5909 | 0.2971 | yes |

> One synthetic held-out observation per case is a weak test, so results are reported per case rather than averaged into a headline figure.

## Runtime

Measured on Linux 6.18.44-fc-v24 / x86_64, 1 logical CPUs, Python 3.12.3, CPU (no GPU, no torch in the served path). A runtime figure without the hardware it was measured on is not a claim anyone can check.

| Measure | Result | Target (p.15) |
| --- | --- | --- |
| Slowest single case, all stages | 7.7 s (case_0004) | ≤ 5 min |
| Mean per case | 5.1 s | — |
| Full run, 6 cases | 30.8 s | — |
| Template query, cold — fresh KB + lookup intent | 1.1 ms | < 2 s |
| Template query, warm — lookup intent (median of 20) | 0.01 ms | < 2 s |
| Time-window query, cold — fresh KB + envelope build | 4.0 ms | < 2 s |
| Time-window query, warm — envelope cached (median of 20) | 1.1 ms | < 2 s |

Dominant stages across the run: fragility 16.9 s, attribution 13.3 s, next_observation 0.4 s. Cold and warm query times are reported separately because the backward envelope is cached after its first computation, and quoting only the warm number would overstate what a reviewer sees on first load.

> This run regenerated every case from its seed before timing, so the figures include generation rather than assuming warm artifacts on disk.

## Required ablations

| Stage | Status |
| --- | --- |
| Nearest-at-image vessel | run (naive baseline, full unfiltered vessel list) |
| Historical proximity | run (same baseline, reported per case above) |
| Hindcast intersection | run (candidate/excluded/unassessed filtering) |
| Forward reconstruction | run (shared-ensemble replay ranking) |
| Uncertainty / abstention | run (absolute fit gate, source-absent cases) |
| NLP lookup-only templates before semantic search | run — no semantic search enabled |
| Radar matching with intentionally hidden AIS | run (hidden-AIS experiment) |
