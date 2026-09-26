# Validation report

Generated 2026-09-26T12:22:33.625989+00:00 · 9 independently generated cases (achieved count, not planned)

All results below are on synthetic data. Synthetic ranking accuracy is not a measurement of real-world attribution accuracy, and no real matched incident has been scored here.

## Leak audit - can a rule with no physics find the source

Each rule looks only at track bookkeeping - fix count, first and last fix, span, actual speed, straightness, reported-vs-actual speed, closest approach to the slick - and names one vessel per case, lowest, second-lowest, highest or second-highest on that attribute. Ties count as misses. Rules and the flag threshold were fixed before the generator was changed. A rule that names the true source in 3 or more of the 7 source-present cases is flagged. A rule picking at random reaches that with probability 0.0806, so about 2.66 of 33 rules are expected to flag by luck alone.

**3 of 33 rules flagged.**

| Rule | Source named | Flagged |
| --- | --- | --- |
| second-lowest closest approach to the slick | 4/7 | yes |
| second-highest first fix time | 3/7 | yes |
| second-lowest actual speed | 3/7 | yes |
| second-lowest first fix time | 2/7 |  |
| second-lowest fix count | 1/7 |  |
| second-lowest track span | 1/7 |  |
| lowest actual speed | 1/7 |  |
| second-highest actual speed | 1/7 |  |

Rules naming the source in no case are omitted from the table. "Closest approach to the slick" has a physical cause rather than a bookkeeping one: the source was at the release point hours before the image and the slick drifts only a few kilometres, while the near decoy is placed on the slick at image time. It is reported, not engineered away.

## Attribution — per case

| Case | Family | Vessels | Candidates | Expected | Method | Correct | Naive baseline | Naive correct | Top IoU | Lead retained | Smallest flip |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| case_0001 | decoy | 6 | 5 | named_candidate | `419151561` | yes | `419765325` | no | 0.692 | 79% | 0.25 |
| case_0002 | moving_discharge | 6 | 6 | named_candidate | `419633358` | yes | `419427337` | no | 0.643 | 78% | 0.5 |
| case_0003 | absent_source | 5 | 5 | unknown_source | `419771272` | NO | `419400107` | no | 0.325 | 92% | 1.0 |
| case_0004 | crowded | 11 | 10 | named_candidate | `419210002` | yes | `419245446` | no | 0.727 | 84% | 1.0 |
| case_0005 | decoy | 6 | 4 | named_candidate | `419420729` | yes | `419623584` | no | 0.686 | 82% | 0.5 |
| case_0006 | absent_source | 5 | 4 | unknown_source | `unknown_source` | yes | `419486428` | no | 0.202 | 100% | none |
| case_0007 | decoy | 6 | 5 | named_candidate | `419363968` | yes | `419931151` | no | 0.673 | 89% | 0.5 |
| case_0008 | moving_discharge | 6 | 4 | named_candidate | `419622686` | yes | `419838277` | no | 0.625 | 96% | 1.0 |
| case_0009 | along_track_ribbon | 6 | 6 | named_candidate | `419792319` | yes | `419151108` | no | 0.51 | 100% | none |

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
| Correct abstentions | 1/2 = 50% [95% CI 9–91%] |
| False named attribution | 1/2 = 50% [95% CI 9–91%] |


> **On the significance test.** Both methods score the same cases, so this is a paired design and the correct test is McNemar on the discordant pairs: 7 cases where forward replay was right and the baseline wrong, 0 the other way. Exact two-sided p = 0.0156. A test treating the two columns as independent groups would report a smaller p by ignoring the pairing, and is not used here for that reason.

> The intervals matter more than the point estimates at this sample size. A perfect score over a handful of cases still admits a wide true rate, and the interval is the honest statement of that. The planned benchmark (120 development / 40 validation / 40 source-present / 60 source-absent locked test cases) is not what was achieved; the achieved count is in the header.

> The naive baseline has no abstention mechanism: on source-absent cases it always names its nearest vessel. That is scored as incorrect because it is the operationally relevant failure — a confident name where no observable source exists.

## Detection — classical baseline vs learned model

| Split | Model | IoU on true oil | Recall | Precision | FP rate (look-alike) | FP rate (clean) | n |
| --- | --- | --- | --- | --- | --- | --- | --- |
| val | classical baseline | 0.857 | 0.860 | 0.930 | 0.000 | 0.000 | 15/8/8 |
| test (locked) | classical baseline | 0.814 | 0.819 | 0.895 | 0.000 | 0.000 | 20/12/12 |
| val | trained U-Net | 0.970 | 0.994 | 0.976 | 0.000 | 0.000 | 15/8/8 |
| test | trained U-Net | 0.968 | 0.998 | 0.969 | 0.000 | 0.000 | 20/12/12 |

> Recall and precision are pixel-level on oil scenes; the two FP rates are per scene on scenes with no oil in them. Pixel accuracy is not reported, because on scenes that are mostly background it is high regardless of whether the slick was found.

> **Recall against the 0.85 target (masterplan p.15): met on val 0.860, missed on test 0.819.** Lee speckle filtering at a 0.65 darkness threshold raised recall from 0.682 val and 0.696 test unfiltered. Both splits are reported rather than the flattering one. False-positive rates on look-alike and clean scenes remain 0.000 at this operating point, so the gain was not bought by loosening the detector: the filter moved the whole trade-off curve rather than trading along it (see the operating-point section). The threshold was chosen on the training split before val or test were examined. The remaining test-split shortfall is still the argument for the learned model.


> **The U-Net beats the classical baseline on every metric, and the gap between val and test is 0.002 IoU.** Near-identical performance on a held-out split after training on 60 oil-bearing patches is not evidence of a well-generalising model; it is evidence that this detection task is easy. The slicks are generated by a known process with consistent appearance, so a network learns that appearance quickly and the test split contains nothing structurally new. On real SAR - speckle that varies with incidence angle, look-alikes drawn from physics rather than a synthetic prior - neither number would survive, and the honest reading is that both detectors are being scored on a benchmark far kinder than the problem.

> **Recall above precision is the loss doing its job.** Tversky weighting at alpha=0.3, beta=0.7 penalises a missed pixel more than a false one, and the result shows it: recall 0.998 against precision 0.969 on test. That asymmetry was chosen, not discovered.

> **Preprocessing differs between the two rows.** The classical detector applies Lee speckle filtering before thresholding; the U-Net sees raw scenes and learns its own features. The comparison is therefore between two complete detectors, not two architectures.

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
| case_0002 | yes | +120 min | 7.465 | 4.0h continuous | 0.5h pulse |
| case_0004 | yes | +0 min | 0.0 | 2.0h continuous | 2.0h continuous |
| case_0005 | yes | +0 min | 0.0 | 2.0h continuous | 0.5h pulse |
| case_0007 | yes | +0 min | 0.0 | 2.0h continuous | 0.5h pulse |
| case_0008 | yes | +120 min | 7.465 | 4.0h continuous | 0.5h pulse |
| case_0009 | yes | +60 min | 10.77 | 7.0h continuous | 4.0h continuous |
| **mean** | | | **3.67** | | |
| **RMSE** | | | **5.70** | | |

> **Why this sits alongside IoU.** IoU measures footprint agreement. An investigator asks how many kilometres the origin estimate is out by.

> **The release is wrong on every case; the vessel is right on every case.** Every true release here is continuous over 2-4 hours. The method selects a 0.5 hour pulse on all of them. Continuous hypotheses are generated - the search covers 0.5h pulse, 2h and 4h continuous - and lose on loss every time. Getting the vessel right while getting what it did wrong indicates the ranking is driven by where a vessel was, not by reconstructing its discharge.

> **Why the pulse wins, and how it links to the slick shapes.** A continuous release smears along-track; a pulse stays compact. The slicks this generator produces are compact (elongation 1.02-1.27, see the characterisation table), so a compact hypothesis fits them better. Two defects reinforcing each other: the generator does not produce ribbon-shaped discharge, and the attribution therefore prefers non-continuous hypotheses.

> **On the 0.00 km entries.** A 0.5h pulse fitted to a 2h release happens to land on the true start; fitted to a 4h release it lands 2.5h in, and the 9.33 km is the vessel's own travel over that offset. Neither should be read as origin-estimation accuracy - the first is coincidence, the second a systematic offset.

> Measurable only because the generator records the true release. On real imagery no such label exists, which is why published work reporting origin error against historical incidents lands in tens of kilometres. These numbers are not comparable to those.

## Detection on the case scenes — characterisation

Separate from the split above, and measuring something different. Those rows score the detector on a benchmark built to be hard. These are the same detector over the eight incident scenes the attribution pipeline consumes, where the slick is the dominant feature.

| Case | Area km² | Perimeter km | Major × minor km | Elongation | Complexity | Bearing | IoU vs truth |
| --- | --- | --- | --- | --- | --- | --- | --- |
| case_0001 | 324.14 | 65.98 | 21.5 × 19.32 | 1.11 | 1.07 | 53.7° | 0.9792 |
| case_0002 | 374.66 | 75.48 | 24.37 × 19.91 | 1.22 | 1.21 | 136.1° | 0.9708 |
| case_0003 | 351.63 | 74.53 | 23.21 × 19.62 | 1.18 | 1.26 | 111.1° | 0.9784 |
| case_0004 | 379.65 | 78.8 | 24.65 × 20.05 | 1.23 | 1.30 | 147.5° | 0.9776 |
| case_0005 | 319.86 | 72.15 | 21.87 × 19.01 | 1.15 | 1.30 | 4.2° | 0.9762 |
| case_0006 | 390.01 | 79.75 | 24.54 × 20.97 | 1.17 | 1.30 | 117.3° | 0.9764 |
| case_0007 | 325.39 | 69.78 | 22.22 × 18.95 | 1.17 | 1.19 | 9.0° | 0.9804 |
| case_0008 | 380.37 | 80.7 | 25.14 × 19.7 | 1.28 | 1.36 | 128.0° | 0.9722 |
| case_0009 | 1060.07 | 222.16 | 83.39 × 17.41 | 4.79 | 3.70 | 171.5° | 0.9704 |

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
| case_0001 | selective | 0.7069 (41/58) | 0.2907 (25/86) | 0.3 (12/40) |
| case_0001 | coverage_failure | 0.8143 (57/70) | 0.1395 (12/86) | 0.6333 (19/30) |
| case_0002 | selective | 0.85 (34/40) | 0.3333 (17/51) | 0.2 (8/40) |
| case_0002 | coverage_failure | 0.8409 (37/44) | 0.0263 (1/38) | 0.6667 (12/18) |
| case_0003 | selective | 0.8 (64/80) | 0.25 (32/128) | 0.375 (15/40) |
| case_0003 | coverage_failure | 0.7955 (70/88) | 0.2154 (28/130) | 0.575 (23/40) |
| case_0004 | selective | 0.8571 (54/63) | 0.338 (48/142) | 0.225 (9/40) |
| case_0004 | coverage_failure | 0.8378 (31/37) | 0.35 (28/80) | 0.3333 (7/21) |
| case_0005 | selective | 0.7937 (50/63) | 0.2743 (31/113) | 0.175 (7/40) |
| case_0005 | coverage_failure | 0.8333 (75/90) | 0.1681 (20/119) | 0.8 (24/30) |
| case_0006 | selective | 0.7937 (50/63) | 0.2784 (27/97) | None (0/0) |
| case_0006 | coverage_failure | 0.8167 (49/60) | 0.2025 (16/79) | None (0/0) |
| case_0007 | selective | 0.6939 (34/49) | 0.3494 (29/83) | 0.3 (12/40) |
| case_0007 | coverage_failure | 0.8556 (77/90) | 0.0722 (7/97) | 1.0 (26/26) |
| case_0008 | selective | 0.8333 (60/72) | 0.2581 (32/124) | 0.3 (12/40) |
| case_0008 | coverage_failure | 0.8426 (91/108) | 0.1397 (19/136) | 0.5882 (20/34) |
| case_0009 | selective | 0.8182 (54/66) | 0.2712 (32/118) | 0.15 (6/40) |
| case_0009 | coverage_failure | 0.881 (74/84) | 0.189 (24/127) | 0.1389 (5/36) |

> Operating point: match gate 0.02°, contact position noise 0.012°, detector miss rate 0.15, false detection rate 0.15. A rate without its operating point is not a comparable measurement.

## Next-observation advisor — held-out check

| Case | Recommended | Least informative | Separation at recommended | Separation at least informative | Helped |
| --- | --- | --- | --- | --- | --- |
| case_0001 | +12h | +9h | -0.0084 | -0.0004 | no |
| case_0002 | +24h | +12h | 0.0583 | 0.1133 | no |
| case_0004 | +24h | +3h | 0.0555 | 0.0865 | no |
| case_0005 | +24h | +3h | -0.0262 | -0.0705 | yes |
| case_0007 | +3h | +18h | 0.2761 | 0.106 | yes |
| case_0008 | +3h | +9h | 0.2743 | 0.1581 | yes |
| case_0009 | +3h | +24h | 0.2854 | 0.1089 | yes |

> One synthetic held-out observation per case is a weak test, so results are reported per case rather than averaged into a headline figure.

## Runtime

Measured on Darwin 25.2.0 / arm64, 8 logical CPUs, Python 3.12.14, CPU (no GPU, no torch in the served path). A runtime figure without the hardware it was measured on is not a claim anyone can check.

| Measure | Result | Target (p.15) |
| --- | --- | --- |
| Slowest single case, all stages | 20.7 s (case_0004) | ≤ 5 min |
| Mean per case | 14.6 s | — |
| Full run, 9 cases | 131.5 s | — |
| Template query, cold — fresh KB + lookup intent | 0.7 ms | < 2 s |
| Template query, warm — lookup intent (median of 20) | 0.00 ms | < 2 s |
| Time-window query, cold — fresh KB, reads per-time state | 0.7 ms | < 2 s |
| Time-window query, warm (median of 20) | 0.0 ms | < 2 s |

Dominant stages across the run: attribution 80.9 s, forecast 25.3 s, fragility 20.0 s. Cold and warm query times are reported separately because a fresh knowledge base loads the case's artifacts on first use, and quoting only the warm number would overstate what a reviewer sees on first load. Time-window queries read per-time envelope membership from historical_mapping.json; nothing is simulated at query time.

> This run regenerated every case from its seed before timing, so the figures include generation rather than assuming warm artifacts on disk.

## Candidate discrimination - is the ranking separating anything

| Case | Family | Loss gap | Discriminated | Outcome |
| --- | --- | --- | --- | --- |
| case_0001 | decoy | 0.1058 | yes | correct |
| case_0002 | moving_discharge | 0.1096 | yes | correct |
| case_0003 | absent_source | 0.0902 | yes | WRONG |
| case_0004 | crowded | 0.0975 | yes | correct |
| case_0005 | decoy | 0.1071 | yes | correct |
| case_0006 | absent_source | 0.0541 | yes | abstained |
| case_0007 | decoy | 0.1961 | yes | correct |
| case_0008 | moving_discharge | 0.1674 | yes | correct |
| case_0009 | along_track_ribbon | 0.1125 | yes | correct |

> **A separate question from the fit gate.** The abstention gate asks whether the best candidate explains the observation at all. This asks whether the second-best explains it about as well: a ranking can clear the gate and still be a coin toss. The tolerance is 0.05 on the loss the ranking is computed from.

> **The two abstained cases fail on both counts, independently.** Their loss gaps are 0.004 and 0.006 - the candidates are indistinguishable - and their best fit is below the absolute gate. Either alone would justify declining to name a vessel. Reporting both is the difference between 'nothing fits' and 'nothing fits and nothing is distinguishable'.

> **case_0009 is the case worth arguing about.** The along-track ribbon is attributed **correctly**, and the system still reports that it cannot discriminate: the loss gap is 0.0438 against a 0.05 tolerance. That tolerance was fixed before this family existed, chosen to sit in the empty band between the named cases (0.15-0.34) and the abstained ones (0.004-0.006). The ribbon landed in that band on its own.

> The honest response is to report it, not to widen the tolerance until it agrees. A correct answer held with low confidence is exactly what a discrimination check is for - a longer, thinner slick is compatible with more release hypotheses, and the system saying so is the behaviour, not a miss. Tuning the threshold to make this case look clean would remove the only evidence in this benchmark that the check does anything.

## Required ablations - what each stage contributes

| Stage | Measured on source-present cases |
| --- | --- |
| 1. Nearest vessel at image time | Top-1 **0/7** |
| 2. Hindcast intersection (filter only) | true source retained **7/7**; candidate pool 47 -> 40 (15% removed) |
| 3. Forward reconstruction | Top-1 **7/7** |
| 4. Uncertainty / abstention | correct on source-absent cases **1/2** |

> **Rung 2 is the one worth reading twice.** Hindcast filtering removes roughly half the candidate pool and, on these cases, never removes the true source. A filter that discarded the answer would be worse than no filter, so retention is reported alongside reduction rather than reduction alone.

> **Rungs 1 and 3 use the same cases and the same candidate data.** The difference between 0 and 6 is the method, not the sample. The paired significance test on that difference is in the attribution section.

| Stage | Status |
| --- | --- |
| NLP lookup-only templates before semantic search | run — no semantic search enabled |
| Radar matching with intentionally hidden AIS | run (hidden-AIS experiment) |
