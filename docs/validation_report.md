# Validation report

Generated 2026-09-14T05:44:28.947861+00:00 · 9 independently generated cases (achieved count, not planned)

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
| case_0007 | decoy | 6 | 4 | named_candidate | `419240128` | yes | `419991981` | no | 0.676 | 100% | none |
| case_0008 | moving_discharge | 6 | 3 | named_candidate | `419125223` | yes | `419847031` | no | 0.599 | 100% | none |
| case_0009 | along_track_ribbon | 6 | 4 | named_candidate | `419630599` | yes | `419711487` | no | 0.334 | 90% | 1.0 |

## Attribution — aggregates

| Measure | Result |
| --- | --- |
| Source-present cases | 7 |
| Forward-replay Top-1 | 7/7 = 100% [95% CI 65–100%] |
| Forward-replay Top-3 | 7/7 = 100% [95% CI 65–100%] |
| Naive proximity Top-1 | 0/7 = 0% [95% CI 0–35%] |
| Top-1 gain over naive proximity | +100 percentage points |
| Paired comparison (exact McNemar) | p = 0.0156 — significant at 0.05 |
| Source-absent cases | 2 |
| Correct abstentions | 2/2 = 100% [95% CI 34–100%] |
| False named attribution | 0/2 = 0% [95% CI 0–66%] |


> **On the significance test.** Both methods score the same cases, so this is a paired design and the correct test is McNemar on the discordant pairs: 7 cases where forward replay was right and the baseline wrong, 0 the other way. Exact two-sided p = 0.0156. A test treating the two columns as independent groups would report a smaller p by ignoring the pairing, and is not used here for that reason.

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

## Detection operating point - why recall is where it is

| Darkness threshold | IoU | Recall | False positives on look-alikes |
| --- | --- | --- | --- |
| 0.75 x scene median  **(in use)** | 0.5759 | 0.5811 | 0.000 |
| 0.80 x scene median | 0.6439 | 0.6507 | 0.067 |
| 0.85 x scene median | 0.7012 | 0.7103 | 0.367 |
| 0.90 x scene median | 0.7570 | 0.7689 | 0.567 |

> **Swept on the training split only.** Sweeping on the split a result is reported against would be choosing the answer rather than measuring it.

> **The recall shortfall is a purchase, not a defect.** Raising the threshold does raise recall - but the false-positive rate on look-alike scenes rises far faster, from zero to over a third by 0.85. The detector is set conservatively on purpose: a missed slick is re-detectable on the next pass, while a false detection routed to an analyst as a candidate spill costs their time and their trust. Reported as a curve so the choice is visible and a reader can disagree with it.

> **Otsu was tried and rejected, with a measurement.** Adaptive thresholding assumes a roughly bimodal histogram with comparable class sizes. A slick occupies about 2.6% of these scenes, so Otsu places the threshold far above the true separation and admits background speckle: IoU on the case scenes falls from 0.92 to 0.19-0.28. A fixed fraction of the scene median is the better estimator for a small dark minority against a stable background.

## Origin error — how far off is the release point

| Case | Correct vessel | Release start error | Origin error km | True release | Estimated release |
| --- | --- | --- | --- | --- | --- |
| case_0001 | yes | +0 min | 0.0 | 2.0h continuous | 0.5h pulse |
| case_0002 | yes | +150 min | 9.332 | 4.0h continuous | 0.5h pulse |
| case_0004 | yes | +0 min | 0.0 | 2.0h continuous | 0.5h pulse |
| case_0005 | yes | +0 min | 0.0 | 2.0h continuous | 0.5h pulse |
| case_0007 | yes | +0 min | 0.0 | 2.0h continuous | 0.5h pulse |
| case_0008 | yes | +150 min | 9.332 | 4.0h continuous | 0.5h pulse |
| case_0009 | yes | +210 min | 39.264 | 7.0h continuous | 2.0h continuous |
| **mean** | | | **8.28** | | |
| **RMSE** | | | **15.66** | | |

> **Why this sits alongside IoU.** IoU measures footprint agreement. An investigator asks how many kilometres the origin estimate is out by.

> **The release is wrong on every case; the vessel is right on every case.** Every true release here is continuous over 2-4 hours. The method selects a 0.5 hour pulse on all of them. Continuous hypotheses are generated - the search covers 0.5h pulse, 2h and 4h continuous - and lose on loss every time. Getting the vessel right while getting what it did wrong indicates the ranking is driven by where a vessel was, not by reconstructing its discharge.

> **Why the pulse wins, and how it links to the slick shapes.** A continuous release smears along-track; a pulse stays compact. The slicks this generator produces are compact (elongation 1.02-1.27, see the characterisation table), so a compact hypothesis fits them better. Two defects reinforcing each other: the generator does not produce ribbon-shaped discharge, and the attribution therefore prefers non-continuous hypotheses.

> **On the 0.00 km entries.** A 0.5h pulse fitted to a 2h release happens to land on the true start; fitted to a 4h release it lands 2.5h in, and the 9.33 km is the vessel's own travel over that offset. Neither should be read as origin-estimation accuracy - the first is coincidence, the second a systematic offset.

> Measurable only because the generator records the true release. On real imagery no such label exists, which is why published work reporting origin error against historical incidents lands in tens of kilometres. These numbers are not comparable to those.

## Detection on the case scenes — characterisation

Separate from the split above, and measuring something different. Those rows score the detector on a benchmark built to be hard. These are the same detector over the eight incident scenes the attribution pipeline consumes, where the slick is the dominant feature.

| Case | Area km² | Perimeter km | Major × minor km | Elongation | Complexity | Bearing | IoU vs truth |
| --- | --- | --- | --- | --- | --- | --- | --- |
| case_0001 | 300.76 | 68.83 | 21.45 × 19.3 | 1.11 | 1.25 | 62.3° | 0.9186 |
| case_0002 | 350.2 | 82.12 | 24.02 × 19.92 | 1.21 | 1.53 | 134.3° | 0.9153 |
| case_0003 | 297.55 | 72.63 | 20.47 × 20.08 | 1.02 | 1.41 | 23.5° | 0.9199 |
| case_0004 | 274.88 | 66.93 | 20.5 × 18.14 | 1.13 | 1.30 | 5.1° | 0.9232 |
| case_0005 | 293.8 | 77.85 | 21.1 × 19.34 | 1.09 | 1.64 | 2.3° | 0.9078 |
| case_0006 | 322.18 | 73.1 | 21.32 × 20.79 | 1.03 | 1.32 | 76.7° | 0.9222 |
| case_0007 | 311.83 | 76.43 | 22.39 × 18.99 | 1.18 | 1.49 | 6.3° | 0.9199 |
| case_0008 | 360.56 | 93.52 | 25.28 × 19.89 | 1.27 | 1.93 | 130.3° | 0.9191 |
| case_0009 | 641.15 | 222.16 | 68.53 × 15.79 | 4.34 | 6.13 | 111.4° | 0.9172 |

> **These IoU figures are not comparable to the split above and neither supersedes the other.** The split is the detector on a task designed to trap it; these are the same detector on the incident scenes. Quoting only the higher number would misrepresent the detector.

> **Complexity** is the isoperimetric ratio P²/4πA — 1.0 for a circle, rising with raggedness. It is bounded below by 1.0 for any closed shape, which is the check that caught a perimeter defect: interior speckle holes were each contributing a closed boundary, inflating perimeter 3.15x and driving the ratio to 8.0. Holes are now filled for the outline measurement only, and the boundary-count correction is calibrated against a digitised disc (0.89x) rather than assumed.

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
| case_0007 | selective | 0.8209 (55/67) | 0.2927 (36/123) | 0.3 (12/40) |
| case_0007 | coverage_failure | 0.8871 (55/62) | 0.2636 (29/110) | 0.0 (0/34) |
| case_0008 | selective | 0.825 (66/80) | 0.2886 (43/149) | 0.35 (14/40) |
| case_0008 | coverage_failure | 0.8485 (56/66) | 0.3287 (47/143) | 0.25 (10/40) |
| case_0009 | selective | 0.825 (66/80) | 0.2886 (43/149) | 0.425 (17/40) |
| case_0009 | coverage_failure | 0.8906 (57/64) | 0.3121 (44/141) | 0.15 (6/40) |

> Operating point: match gate 0.02°, contact position noise 0.012°, detector miss rate 0.15, false detection rate 0.15. A rate without its operating point is not a comparable measurement.

## Next-observation advisor — held-out check

| Case | Recommended | Least informative | Separation at recommended | Separation at least informative | Helped |
| --- | --- | --- | --- | --- | --- |
| case_0001 | +3h | +12h | 0.2456 | 0.0001 | yes |
| case_0002 | +3h | +24h | 0.5712 | 0.2527 | yes |
| case_0004 | +24h | +6h | 0.0429 | 0.079 | no |
| case_0005 | +3h | +24h | 0.5909 | 0.2971 | yes |
| case_0007 | +3h | +24h | 0.5914 | 0.3052 | yes |
| case_0008 | +3h | +18h | 0.583 | 0.3387 | yes |
| case_0009 | +3h | +24h | 0.1966 | 0.3972 | no |

> One synthetic held-out observation per case is a weak test, so results are reported per case rather than averaged into a headline figure.

## Runtime

Measured on Darwin 25.2.0 / arm64, 8 logical CPUs, Python 3.12.14, CPU (no GPU, no torch in the served path). A runtime figure without the hardware it was measured on is not a claim anyone can check.

| Measure | Result | Target (p.15) |
| --- | --- | --- |
| Slowest single case, all stages | 3.2 s (case_0004) | ≤ 5 min |
| Mean per case | 2.3 s | — |
| Full run, 9 cases | 20.6 s | — |
| Template query, cold — fresh KB + lookup intent | 0.7 ms | < 2 s |
| Template query, warm — lookup intent (median of 20) | 0.00 ms | < 2 s |
| Time-window query, cold — fresh KB + envelope build | 1.7 ms | < 2 s |
| Time-window query, warm — envelope cached (median of 20) | 0.3 ms | < 2 s |

Dominant stages across the run: fragility 11.1 s, attribution 8.7 s, detection 0.4 s. Cold and warm query times are reported separately because the backward envelope is cached after its first computation, and quoting only the warm number would overstate what a reviewer sees on first load.

> This run regenerated every case from its seed before timing, so the figures include generation rather than assuming warm artifacts on disk.

## Required ablations - what each stage contributes

| Stage | Measured on source-present cases |
| --- | --- |
| 1. Nearest vessel at image time | Top-1 **0/7** |
| 2. Hindcast intersection (filter only) | true source retained **7/7**; candidate pool 47 -> 26 (45% removed) |
| 3. Forward reconstruction | Top-1 **7/7** |
| 4. Uncertainty / abstention | correct on source-absent cases **2/2** |

> **Rung 2 is the one worth reading twice.** Hindcast filtering removes roughly half the candidate pool and, on these cases, never removes the true source. A filter that discarded the answer would be worse than no filter, so retention is reported alongside reduction rather than reduction alone.

> **Rungs 1 and 3 use the same cases and the same candidate data.** The difference between 0 and 6 is the method, not the sample. The paired significance test on that difference is in the attribution section.

| Stage | Status |
| --- | --- |
| NLP lookup-only templates before semantic search | run — no semantic search enabled |
| Radar matching with intentionally hidden AIS | run (hidden-AIS experiment) |
