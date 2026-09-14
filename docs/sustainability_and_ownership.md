# Appendix C — Sustainability and post-submission ownership

What happens to this after 18 September.

---

## Why continued operation is cheap

**No always-on service is required.** The reference release is a container image
run on demand. There is no hosted endpoint, no standing compute and no
per-request cost between investigations.

**No external dependency at run time.** The application makes no outbound calls
during analysis — no model API, no tile server, no font CDN. This is verified
rather than asserted: a headless browser run against the built application
records zero requests outside the local origin, on both desktop and mobile
viewports, and the built CSS contains no `https://` references because fonts are
packaged via `@fontsource`. The application therefore cannot break because a
third-party service changed or a key expired.

**Pinned dependencies.** `requirements.lock` pins all 34 Python packages (nine direct, the rest transitive)
exactly, and `frontend/package-lock.json` locks the JS tree. A rebuild later
reproduces the same environment, subject only to base-image availability. Every
number in `docs/validation_report.md` was produced under the pinned versions.

**Deterministic regeneration.** `scripts/run_pipeline.py --regenerate` rebuilds
every case from its seed and recomputes every artifact. Verified: a full
regeneration produces byte-identical analysis artifacts across all eight cases and eight
artifact types. Nothing shown to a reviewer depends on a file that cannot be
regenerated, which means there is no state to preserve and no archive to
maintain.

**Measured cost of a full run:** 20 s wall clock for eight cases on one CPU core,
no GPU. Runtime figures with hardware are in `docs/runtime.json` and the
validation report.

The dominant recurring cost, if this went further, is data refresh — not software
operation.

---

## Data-refresh cadence

| Layer | Cadence | Note |
| --- | --- | --- |
| AIS history | Per investigation | Fetched for the incident window; no standing mirror needed for a case-by-case workflow |
| Forcing fields | Per investigation | Reanalysis for retrospective work; operational forecasting would need fields available at issuance |
| Detector weights | On material change | Retrain when a new labelled corpus or a region transfer justifies it — not on a calendar |
| Benchmark cases | Versioned | `CASE_PLAN` seeds are in source; new families added as versions, old ones retained for comparability |

---

## Ownership after submission

Stating a position rather than leaving it open:

Slick Trace retains the repository and the released benchmark under the stated open
licence (`LICENSE`, MIT). The evaluating body is offered a **no-obligation
handover** — code, manifests, assumptions register, licence appendix and
validation report — if it wishes to take the work further. No support commitment
is implied and none is offered; an explicit modest answer is stronger than
silence.

**Maintainer.** Shaurya Chopra — shauryachopra@zohomail.in —
[github.com/shauryach0pra](https://github.com/shauryach0pra). Slick Trace was
built and is maintained by one person; the handover offer above is made on that
basis and is not contingent on a wider group remaining available.

---

## Released artefacts

**The adversarial benchmark.** Generator configuration and case parameters
(`slicktrace_core/synth_generator.py`, `CASE_PLAN` with its seeds and four families).
Note: `slicktrace_core` is the technical module name; the project is called Slick Trace.
This is the piece most reusable by others: it lets another team measure false
attribution under decoy, moving-discharge, absent-source and crowded conditions
without rebuilding the harness. Released after evaluation.

**The hidden-AIS recovery protocol.** The definition and procedure in
`slicktrace_core/coverage.py`, with its three rates — recovery, false
unmatched-alert, mistaken-promotion — and the operating point they are measured
at. Naming and defining the measure is itself part of the contribution: it lets
another team reproduce the stress test rather than take a qualitative claim on
trust.

**The assumptions register and validation report.** Shipped with the code in
`docs/`, not only in the deck.

**The invariant suite.** 172 tests, several of which encode masterplan
constraints directly — no ground truth in the manifest, dispersion scaling with
drift time, ensemble sharing, the smallest flip actually being the smallest.
These are the properties that would otherwise regress silently.

---

## Post-submission roadmap

Maintained separately from the pitch deck, carrying the same gating discipline
used during the build:

1. **Train and evaluate the U-Net** against the classical baseline on the
   identical split. The concrete target is recall: the baseline reaches 0.68 on
   val and 0.70 on test against a 0.85 target, while holding precision near 0.99
   and a 0.000 false-positive rate. That gap is the specific thing a learned
   model has to close, and it is a sharper objective than an IoU figure.
2. **Real-region validation for Indian waters** with matched AIS and
   monsoon-season forcing. A new feed alone does not establish transfer accuracy.
3. **Wire the remaining evidence surfaces** — coverage, forecast and
   next-observation results are computed and served but not yet on the
   dashboard.
4. **DuckDB/Parquet query layer**, replacing the bounded Python resolvers once
   real AIS volumes make indexed filters necessary.
5. **Cross-scene hypothesis update and multi-slick source assignment** (both P2).
6. **Calibration of evidence scores against held-out outcomes** — the step that
   would let the system speak in probabilities rather than evidence scores. Until
   then the distinction is maintained everywhere in the interface and the report.

---

## The one thing that cannot be self-certified

Everything above is within the team's control. External validation is not.

An informal expression of interest from a marine-pollution watch desk, port
authority or coastal environmental agency — even a conversation, recorded
honestly as a conversation — is worth more to the credibility of the impact and
continuity claims than any additional self-assessment. Pursue one before the
18th if a route exists. If none does, claim reach and plausibility, not adoption.
