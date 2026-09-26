# CHANGELOG

Everything that changed, so you can diff this against whatever you have locally
rather than guessing.

---

## 25 September 2026

**Historical filtering: partial coverage no longer counts as exclusion.**
`slicktrace_core/hindcast.py` marked a vessel `excluded` if it had a position at
any one of the 25 queried times and was never inside the envelope, and the
reason string then claimed track data "present throughout window". Every one of
the 26 vessels excluded across the nine cases had data at 11 of 25 queried
times: generated tracks cover the last ten hours of a 24-hour window. Membership
is now decided per queried time (`inside`, `outside`, `no_data`, persisted as
`hourly_state` with `hours_with_data` and `data_intervals_hours_before`) and
only then summarised; `excluded` requires data at every queried time, as A7
always defined it. The 26 vessels are now `unassessed`, with the span their data
covers stated. Candidate sets, rankings, fragility and the headline are
unchanged (7/7 against 0/7, exact McNemar p = 0.0156), because neither state is
replayed. No vessel in the benchmark now qualifies as excluded: that needs
tracks spanning the window the manifest declares, a generator change not made
here. The NLP suite's "filtered out before ranking" question now draws on
excluded or unassessed vessels, so it resolves to the same two vessels as
before. Two invariant tests added; 199 pass.

**Canonical Case contract.** `slicktrace_core/case_contract.py` defines one
validated object per incident, assembled verbatim from the committed artifacts
(manifest, historical mapping, detection, baseline, attribution, fragility,
coverage, forecast, next observation) and never from the truth sidecar.
Unknown fields are rejected, so artifact drift fails the suite. The family label
is checked against `CASE_PLAN`: nine cases across five families (decoy x3,
moving_discharge x2, absent_source x2, crowded, along_track_ribbon). Not yet
served or read by the interface. Thirteen tests added; 212 pass.

**Case served.** `GET /api/incidents/{id}/case` returns the contract for one
incident; each section equals what its per-stage endpoint already serves, a
missing stage is an actionable 404, and a contract mismatch is a 500 naming it.
Nothing in the interface reads it yet. Three tests added; 215 pass.

**Time-slider replay served from an artifact, not computed per request.**
`/api/incidents/{id}/envelope` rebuilt the backward simulation, re-ran the
density contours and re-tested every vessel on each request, with its own copy
of the 0.045° inclusion radius; the query console did the same for time-window
questions with a third copy. None of it was covered by the determinism check.
The historical-mapping stage now also writes `envelope_timeline.json` (25 hourly
frames: particles, 50/75/90% contours, every vessel's position and membership)
from the same snapshots and per-time pass it summarises. `/envelope` serves the
nearest frame, `/envelope-timeline` serves all 25, and time-window questions
read `hourly_state` from `historical_mapping.json`. The served API no longer
reads the ground-truth mask at request time; the pipeline still seeds the
hindcast from it. Measured: every frame's per-vessel state equals the historical
mapping's in all nine cases; the old and new `/envelope` agree on every field
for all 25 hours of all nine cases, contours to the 5-decimal rounding the
artifact applies; the NLP suite returns the same 40 answers. CI now diffs the
new artifact. Two tests added; 217 pass.

**README brought in line with the repository.** (mirror)
and validation reports 7/7 against 0/7, exact McNemar p = 0.0156.

**Interface: three displays that showed values nothing computed.** (mirror)
already states the finding. `api.js` no longer defines `detection` twice.

**Display geometry computed in the pipeline.** The attribution stage now also
writes `replay_footprints.json`: for every ranked candidate, the footprint its
best hypothesis produces under the nominal forcing member, rasterised exactly as
scored and traced to lon/lat. The forecast stage writes `forecast_contours.json`:
50/75/90% contours over the particles behind each horizon's figures. Both are
served (`/replay-footprints`, `/forecast-contours`) and carried in the Case
contract, now schema 2; `attribution_result.json` and `forecast_result.json` are
unchanged. Fixed on the way: since matplotlib 3.8 a contour level returns all of
its loops in one path, and `density_contours` took it whole, so 4 of 675 rings
across the nine envelope timelines joined two lobes into one polygon with a false
edge between them. Levels are now split at each loop; the single-loop rings are
unchanged. Six tests added; 223 pass.

**Track display: gap windows, rendering-only paths, no invented vessel type.**
A new pipeline stage writes `track_display.json`. Per vessel it records every
window inside the declared AIS window with no usable position report (leading,
internal, trailing), counting sentinel positions as missing and wording them as
no position reported rather than as an outage; a test holds the leading and
trailing windows to exactly the hours the hindcast marks `no_data`. It adds a
centripetal Catmull-Rom path through the fixes for drawing, never across a gap,
with its largest departure from the straight segments stated; every analysis
still uses the original fixes. Vessel type is `null` with the reason: an MMSI
does not encode ship type and the source carries no AIS static data. Served at
`/track-display` and carried in the Case contract, schema 3.
`scripts/track_summary.py` prints the per-case table. Seven tests added; 230 pass.

**Interface: a native macOS design system and shell.** Tokens for light and dark
(system colours, vibrancy materials, separators, labels) with the legacy variable
names aliased onto them, so every panel follows the theme unedited; an
appearance control (System, Light, Dark) applied before first paint. System
fonts replace the web fonts. The shell is a translucent toolbar, a vibrant
sidebar whose single selection slides between rows, sections divided by
hairlines with sticky translucent headers instead of boxed cards, and a
translucent inspector. Hover and press use a lightly damped spring; reduced
motion and reduced transparency are honoured. Shell rules moved out of
`dashboard.css`, whose translucent white fills now use a token so dark mode
holds. No data, request or case logic changed.

**Conclusion graph rebuilt from real fields.** The graph removed on 25 September
for reading fields no artifact has returns as the same side-scrolling chain, in
pipeline order:
detection, historical filtering, forward replay beside the proximity baseline,
rank fragility, finding. Each value is an artifact field (status_counts,
discrimination, lead_retained_fraction, smallest_flip, abstention gate); a stage
whose artifact has not loaded says so. It now shows what the old one hid: on
case_0009 the top two candidates are not separated.

**Interface: generic, schema-driven cards.** Every panel is rebuilt from shared
primitives (Card, Stat, BarList, Badge, CaptionList, EmptyState) and reads the Case
contract from `/case`, plus `/report` for status counts and checksums and `/tracks`
for the map; a response for a case no longer selected is dropped. Every non-obvious
number carries a plain-language caption, visible by default, each checked against
the code that computes it. Fixed on the way: the finding said "tested N release
hypotheses" where N was candidate vessels; "Top Pick Right/Wrong" needed ground
truth the interface does not have and now says how the baseline relates to forward
replay; red and green verdict colours are gone; the next-observation card reads the
artifact's recommended window instead of recomputing it; a null shoreline fraction
reads "not modelled"; the scene card carries the note that downstream stages are
seeded from the generator mask; card state resets on case switch. Recharts is
replaced by native bars (bundle 619 KB to 271 KB).

**Scene map: MapLibre GL JS basemap, framed on real coordinates.** A Scene Map
card shows the selected case's extent (`meta.bbox`, EPSG:4326) on Esri World
Imagery when `VITE_ARCGIS_API_KEY` is set in `frontend/.env.local` (gitignored),
and on the real coastline over a plain sea when it is not. If imagery tiles fail
(key rejected, referrer not allowed, offline) the map falls back and says so.
Basemap only: no case data is drawn on it yet. Esri attribution is shown as its
terms require.

**Benchmark: real geography and no leaked answers.** A leak audit - rules that
use only track bookkeeping, fixed before the generator was changed - found the
old generator handed over the answer: 10 of 33 rules named the true source at or
above the flag threshold, four of them in 7 of 7 cases, because the source's track
length, start time and speed were unlike any other vessel's, it stopped reporting
before the image, and no other traffic came near the slick. Every vessel now draws
those from the same distributions; reported speed and course are its actual
motion; half of background traffic passes the slick as closely as a polluter does;
and innocent vessels are kept physically identifiable (none within 8 km of the
source while it releases). The audit runs in every validation: 2 of 33 rules flag,
about 2.7 expected by chance, none above 5 of 7 (A21).

One real coastline everywhere (`slicktrace_core/geography.py`, A22): manifests,
the detector's land rejection and the forecast use the Natural Earth coast, which
an invented coastline about 19 km east of it stood in for. Vessels steer clear of
land, the truth slick is sea only, the fishing ground is at sea, the mangrove
fringe straddles the shore, the radar scene renders land, and forecast oil strands
on the coast, checked hourly (forecasts that never touch land are unchanged).

The fairer benchmark has an honest cost. Forward replay held at 7/7; the naive
baseline now names the source once (1/7, was 0/7) and McNemar p is 0.0312 (was
0.0156); correct abstentions are 1/2 (was 2/2): in case_0003 a passer-by fits at
IoU 0.49, above the 0.3 gate, and is named (A10). Two case_0001 claims were retired
from tests and documents because they are no longer true: that the naive baseline
falls for the decoy, and that the runner-up fits at 0.30 or below. 294 tests pass
(67 added, 3 retired); all 135 case artifacts regenerate byte-identically.

**Replay map: the case on a real map, 24 h either side of the image.** A MapLibre
map with a time bar from -24 h to +24 h (play, pause, step, 1x/2x) replaces the
SVG map and the basemap preview. Before the image it draws the backward origin
envelope and, for a named vessel only, its scored release replayed hour by hour -
oil leaving the ship; at the image, the detected slick with the replayed footprint;
after it, the forecast drift, stranding on the real coast. Ships move along their
tracks, trails stop at the selected hour and AIS gaps are dashed. Every frame is
labelled observed or modelled. Two artifacts feed it: replay_timeline.json (the
nominal member attribution scored, evaluated each hour; the last frame rasterises
to the scored footprint pixel for pixel) and forecast_timeline.json (the forecast's
own particle paths each hour; identical to forecast_contours.json at 6, 12 and 24 h).
Existing artifacts are unchanged. 329 tests pass (35 added).

**Replay map, finished: motion, ships and the image moment.** Playback glides
between computed hours: every oil particle moves from its position at one hour to
the next (replay frames now list all 250 particles in a fixed order, with a
released flag), ships glide, and the origin envelope cross-fades; a paused frame is
always the computed one. Ships are top-down hull symbols with a wake scaled by
reported speed, sized by zoom and marked not to scale (no vessel dimensions are
known, and at scene zoom a pixel is ~200 m); a ping marks where each vessel's AIS
signal begins. The envelope glows with 50% and 90% labels; arriving at the image
plays a scan across its footprint. Fixed on the way: the forcing probe read the
current in m/s as degrees per hour and showed 9.03 kn for a 0.31 kn current; a case
switch after zooming could crash the page; the scan first redrew the whole map
each frame and slowed every case load. 330 tests pass (1 added).

**Replay map on a continuous clock.** The map now renders at any fractional hour:
ships move along their smooth display paths with heading from the path's curve,
trails grow with them, oil particles and the envelope move between computed hours,
and a paused frame is exactly a computed hour. After the image, where there is no
AIS, ships are projected from their last reported course and speed, drawn as
outlined hulls on dashed tracks, labelled projected and held at the coast. The
release plays a burst at the ship and the oil emerges from its position; at the
image the replayed oil fades into the forecast instead of jumping. Ships are
readable at the default view (20 px). Fixed: every ship marker was displaced by the
height of the markers before it (a CSS position rule overrode MapLibre's own), which
is why the leading ship appeared away from its oil and trails did not reach ships;
each frame re-sent every map layer, starving the renderer during playback.

**Realistic AIS, exact stranding, and a finer release search.** Every vessel is now
tracked over the whole 24 h AIS window and published as an AIS query for the scene
returns it, so ships enter and leave through the frame edges instead of appearing in
open water; 15% of vessels, of any role, switch their transponder off for 1-3 h.
That exposed a limit in forward replay: it tried three release start times per
vessel, which full-day tracks spaced 12 h apart, so a release 6 h before the image
was never tried. Starts are now tried every hour (A23), and case_0001's best
hypothesis starts at the true release time. Forecast oil that reaches the coast is
held where it crosses the shoreline (bisected), not up to an hour's drift inland.
On the map, sensitive areas appear after the image, labelled, and light up from the
hour the forecast first reaches them; the envelope is captioned; a layer toggle.
Re-earned: 7/7 against naive 0/7, McNemar p = 0.0156, abstentions 1/2; leak audit
3 of 33 flagged (about 2.7 by chance).

**Oil drawn as oil.** Modelled oil on the replay map is now a dark brown-black film
with a thin iridescent sheen where it thins at the edges, as oil looks on water; the
orange heat-map glow it replaced is not what oil looks like. Stranded oil is dark
droplets with a gold rim. A sensitive area the oil reaches keeps its own colour and
gains a red-orange hazard outline and a pulsing badge, instead of turning the oil's
colour. Projected ships after the image have a solid dark hull with a bright dashed
outline, so they stay visible over the oil.

**Vessels by type.** Each vessel now carries synthetic AIS static data (message 5)
with a ship type drawn from its behaviour - loitering vessels mostly fishing boats,
tugs and ships at anchor; vessels under way mostly cargo ships, tankers and passenger
ships - never from its role, and from a separate random stream, so no track, slick
or analysis result changed (A24). The map draws each type with its own original
top-down silhouette (tanker, cargo, passenger, fishing, tug; a generic hull when not
reported), also in the legend, tooltips and text table. Two rules were added to the
leak audit before it ran - the only vessel of its type, and the only tanker - and
both name the source in 0 of 7 cases. The case contract is schema 4. Fixed: legend
glyphs inherited the map markers' positioning and invisibly blocked clicks on the
card. 7/7 against naive 0/7 unchanged; 330 tests pass; verifier 38/38.

**Popovers, the observed slick, and AIS gaps on the map.** Clicking a vessel, or
focusing it and pressing Enter, opens a popover that follows it and updates with the
time bar: type (synthetic static data), position, reported speed and course, its
status at that hour, its historical-filtering status, its forward-replay and
proximity ranks, its recorded AIS gaps, and a link that scrolls to its ranking row.
The observed slick has a marching-ants edge and a light fill at every hour, and a
popover with the detection artifact's area and detector. Recorded internal AIS gaps
are dotted and faded, with a hover label - no position was reported, and those hours
count neither for nor against the vessel - and a last-seen ring while the
transponder is off. Only gaps recorded in track_display.json are drawn.

**Popovers float above the app.** The vessel, slick and gap popovers are no longer
clipped by the map's frame or covered by its label: like macOS popovers they float
above the whole window, anchored to their point, following it as the map moves, time
plays or the page scrolls, flipping below when there is no room above and staying
inside the window. A stranded share too small to show reads '<0.1%', not '0.0%'.

**Fixed: the slick popover opened at the window's corner.** A damaged line left its
placement call pointing at an undefined name, so the click threw and the popover was
never positioned. It now opens at the clicked point. The jump to a ranking row used
scrollIntoView, which could scroll the locked window itself and shift the whole app
sideways; it now scrolls only the evidence column. The frontend lint now fails on
any undefined name (no-undef, browser environment), which would have caught the
first bug before it shipped.

**Popover close button centred.** The close button's cross is now an SVG icon centred
by grid instead of a text glyph, which fonts set off-centre.

**Conclusion graph, rebuilt.** A vertical pipeline for the inspector column: a glowing
spine with a luminous node per stage, glass cards beside it, and particles flowing
down the path in the direction of the analysis. Stages come from the artifacts - no
fixed node count or positions; layout and edges are measured from the rendered cards
- and the proximity baseline branches off forward replay on a dashed curve. The
confirmed path glows blue and turns amber where the evidence weakens or stops.
Hovering or focusing a stage shows what it computes in plain language; clicking it
scrolls to its evidence card. Motion is off under reduced-motion settings.

**Conclusion graph as a sideways strip again,** keeping the glass cards and flowing
particle edges, with snapping and faded edges. Fixed: a stage's caption showed twice -
once unplaced, then above the card - because its entrance animation overrode the
transform that positioned it; the jump-to-evidence highlight hugged the card's edge
and was clipped, and is now a ring drawn outside the card, above its sticky header.

**Conclusion graph: level connectors, a cropped window, no hover caption.** Connectors
were measured while the cards' entrance animation still offset them, so they came out
slightly slanted; they are now measured from layout positions and are exactly level.
The graph window is cropped to the main row of cards and scrolls both ways - the
proximity baseline is scrolled down to rather than leaving empty space. The hover
caption is gone; each stage's description stays as its accessible label.

**Ask Slick Trace: curated questions, readable answers, a visible refusal.** Two
narrative questions were refused because no template covered them; two intents were
added - why the nearest vessel was or wasn't named (proximity baseline against forward
replay) and how confident the release time is (release_age) - and the top-candidate and
stability answers now read as short plain-language findings. Every answer is still
built from computed fields by a rule-based template and keeps its cites: line. The
card preloads the same five questions for every case, the last deliberately out of
scope ('Who is legally responsible for this spill?') to show a refusal, which now
says responsibility is a legal finding the system does not make. The NLP suite gains
seven questions (47/47, 12 refusals); the 40 existing ones kept their intents.

The out-of-scope question now looks like the other four; clicking it shows the refusal.

**Guided tour and a cross-fading case switcher.** A tour visits one exemplar of each of
the five case families, chosen from the case list's family field. At each stop it drives
the Replay Map through its own controls - no card logic changed - playing from -24 h and
freezing on the frame where the top-ranked candidate is inside the origin envelope nearest
the start of its best-fitting release, computed from the ranking and envelope data; where
no vessel is named it freezes on the image instead, and notes the family's wrongly named
case. Built on driver.js (MIT, loaded only when a tour starts) with a blurred, dimmed
scrim cut out around the spotlighted card, an animated gradient ring and a frosted
callout. Advance is manual: Space, the arrows, Next, or a click. Start Tour / Exit Tour is
always available. Switching case keeps the previous case on screen, dimmed, until the next
has loaded, then fades it in, instead of blanking and reloading.

**Pinned card headers: a scroll-edge effect instead of a translucent material.** The
sticky headers carried a permanent blurred material that smeared whatever scrolled
under it - map imagery especially - into a textured band. A header is now clear at
rest, and only while its card's content passes beneath it takes the pane's own solid
background, a hairline and a soft fade below, as macOS and iOS do.

**Naive vs forward replay, as one reveal.** The two ranking cards are one. It opens on the
naive answer - every vessel by distance to the slick at image time - and "Reveal
forward-replay result" shows what the pipeline already computed: rows re-sort into
forward-replay order, bars become fit (mean IoU) with the gate marked, the proximity pick
is struck through where replay names a different vessel, and the leader is highlighted.
Where the system abstains the ranking is muted below the gate and says so; nothing is
struck, because replay set no vessel aside. It never says right or wrong. The map
popover's ranking link and the graph's replay stage open the forward-replay view.

The jump-to-evidence ring around Case Finding now follows that card's own box - an even
margin on every side, corners parallel to the card's - like the ring around every other card.

**A distinct abstain state.** When the system names no vessel - keyed on its own output,
unknown_source, never on the case's family, so a wrongly named absent-source case still
shows as the failure it is - Case Finding says so as a decision: "The system abstains" on
an amber-rimmed surface, with a meter placing every replayed candidate's fit against the
gate so it is visible that none reaches it. Its note no longer claims declining was "the
correct output": the interface has no ground truth to know that.

**Mission control overview.** A new default view (#/overview) shows every case as a tile:
its outcome dot, its family, and its one-line finding - produced by the same rule as the
Case Finding card (findingText.js) from the fields a new /api/overview copies out of each
case's artifacts, so the two can never say different things. A tile opens its case
(#/case/<id>); Back and Forward move between them, and an Overview control in the sidebar
returns. A test checks the overview's fields against every case's artifacts.

**Family filter chips.** "All" plus one chip per family present in the case list, with its
count, above the sidebar list and the overview grid - one filter state for both, so they
always agree. Filtering only hides items; the case list and every case's data are
untouched. Fixed: the sidebar kept highlighting the last case on the overview, or when
the open case was filtered out of the list; it now shows no selection then.

The filter chips now appear only above the overview grid; the sidebar lists every case.

**Next Observation closes each case.** It is now the last card, after Provenance, framed
"What to check next"; it shows only its computed recommendation, unchanged.

**One provenance and confidence badge.** A single pill in the top bar for every open case -
"Lead · not proof" or "Abstains" - opens a popover with the fit-gate status from the
attribution result, the investigative-lead framing, and that the pipeline is grounded:
physics-based particle tracking and rule-based templates, no language model in the loop.
It links to the provenance card. The synthetic-case tag stays separate.

**Fragility: "What if conditions were slightly different?"** Where a tested change flips the
lead, the fragility card toggles between the ranking as tested and with the smallest such
change, animating the two vessels that swap, with their fits, tested ranks and loss, and
the margin. Every value is from fragility_result.json and attribution_result.json. Each
tested change stores only its leader and the tested leader's fit, so the rest of the
ranking under it is not shown, and the card says so.

**Forcing and the ensemble fan on the map.** A new artifact, ensemble_fan.json, replays every
ranked candidate's best release under the six forcing variants forward replay scores - the
same variants, seeds and scoring - so it reproduces each candidate's mean IoU and win count
in attribution_result.json exactly (tested), and its final oil rasterises to the scored
footprints. The map draws the top three candidates' six member drift paths as faint
bundles, the leader's in blue, with each member's variant and fit on hover; and the forcing
itself - one uniform current, the same everywhere, labelled so - as a subtle arrow field and
a small rose of the six variants. No wind is in the inputs, and the spatial variation the
generator applies is not shown. Both have Layers toggles. 357 tests pass.

**Cards that respond.** Every section of a case, and of the inspector, is now a card on a soft
pane, with its own surface, hairline edge and shadow. Cards and overview tiles lean away on the
side under the pointer - a little for large cards, more for small tiles - with a light that
follows it, and enter with a short stagger. The Replay Map card keeps the light but does not
rotate, so clicks on the map stay on target. Sticky headers keep their scroll-edge effect in
the card's colour. Motion is off under reduced-motion settings.

**Design step 1: Case Finding as one sentence and one picture.** The card leads with its
finding, then the comparison as a visual: the proximity pick, struck through where forward
replay disagrees, against forward replay's pick with a fit gauge that draws in to its mean
IoU (gate and runner-up marked) and pips for the forcing variants it won. Supporting facts are
chips; definitions fold into "How this is measured". Shared viz primitives (gauge, count-up,
disclosure) are added for the next steps. Fixed: the reveal's leader row no longer scales out
of line, and Ask shows each answer from its first line.

**Design step 2a: Observed Scene and Rank Fragility.** Observed Scene pairs the radar image
with a slick fingerprint: the shape drawn to its measured axes and bearing, north up, a
counting area, compact facts and an elongation bar. Rank Fragility shows every tested change
as one dot, smallest first - blue where the leader held, amber where it flipped, the smallest
flip ringed, each described on hover - beside the share that held. Notes fold into "How this
is measured" in both.

**Design step 2b: Forward Exposure and Next Observation as charts.** Forward Exposure shows the
modelled spread and each sensitive area's share (with the shoreline) as lines that draw in over
+6, +12 and +24 h, with chips for the earliest area reached and first shoreline contact, and the
forcing mode kept visible. Next Observation shows the recommended window large beside a bar
timeline of disagreement per window, the recommendation lit. Shared SVG charts are added.

**Design step 2c: the supporting cards, side by side.** Coverage-Aware Matching shows each rate
as paired bars (vessels hidden, area goes dark) marked with which direction is better. Traffic
Filtering and Provenance shows a funnel from every vessel in the scene to the one named - or
none, when the system abstains - with excluded and unassessed vessels as chips and the run's
provenance as a compact list. The two sit in one row, with the same card treatment and tilt.

**Design step 5: the Replay Map's text.** The caption is one line; the fifteen-entry legend is four
chips - Vessels, Oil, Areas, Model - each opening its entries in the map's own symbols; the reading
guide and the note for the current hour move into "How to read this map", and the vessel table
into its own disclosure.

**Design: the inspector and the reveal card.** The Conclusion Graph's footnote folds away. Ask
Slick Trace gets a one-line caption, suggestion chips that stay after the first answer, readable
questions instead of a terminal prompt, and a rounded field with a send button; the refusal still
declines. Naive vs Forward-Replay gets a short caption for each state, with its definitions folded.

**Design step 6: motion that plays when you arrive.** Every card's animations - lines drawing,
bars and funnels growing, the dot matrix, the fingerprint outline, pips - wait paused until the
card scrolls into view, and the card fades up as it arrives; counters and the fit gauge start
when they are seen. Previously everything played on load, unseen below the fold. Without
IntersectionObserver, or under reduced motion, everything is simply shown.

**The sidebar as a macOS source list.** Cases are grouped by family in collapsible sections, each
with a symbol and count. Every row shows the system's own outcome - a vessel named or an
abstention - the vessel it named and a mini ring of its fit, from the same overview fields as the
grid, so a wrongly named case still reads as named. The selection follows rows through collapsing
groups and hides when its group is closed; a small legend explains the symbols.

**Smoother case switching.** The leaving case softens into the background - dimmer, lightly
blurred, a hair smaller - and a thin progress sweep appears only if the next takes more than a
beat to load; the new case then rises into focus. The sidebar selection glides between rows on a
gentle spring with a soft glow. Reduced motion turns all of it off.

**The case switch no longer freezes.** Profiling showed the stall was the map, not the
transition: each switch tore down one WebGL map and compiled another in the same instant the
animation ran (React's render was ~2% of it). The new map is now created just after the new case
has risen into focus, and fades in; the old one is removed after the fade. The first map on load
is unchanged. Measured in a software-rendered browser, the switch settles in 0.9 s instead of
6.2 s, and the longest stalled frame fell from 1.6 s to 0.3 s.

**Sidebar alignment.** One symbol column and one text column run the length of the sidebar:
the Overview icon, family symbols and outcome symbols share a 17 px column, and every label
starts at the same x. The disclosure chevron moves to each group's trailing edge, shown on hover
and while collapsed, as in Finder.

**The overview, redesigned.** A header of benchmark figures served from the validation report
(/api/benchmark): sources named by forward replay against the proximity baseline, correct
abstentions with the wrongly named case stated, and cases named. Each tile says what its case
tests (the family's design, never which vessel), draws a radar-style thumbnail of the case's own
geometry - the detected slick, the best-fitting vessel's track to the image, the proximity pick -
from a new thumb block in /api/overview, and shows its fit gauge and outcome. Tests tie the
thumbnails and the benchmark figures to their source files. 359 tests pass.

**The overview tiles, as they were, with what each case is.** The previous tiles are restored,
each now leading with its scenario - what the case tests - and a line of facts: the image time,
vessels tracked and candidates replayed. The overview and benchmark endpoints stay available.

**A brief overview and a quieter sidebar.** Each overview tile now shows only the case, what it
tests and one sentence on what happened, built from its result, with the same outcome symbol as
the sidebar (one shared component). The sidebar drops its fit rings, and every count sits on one
right edge.

**Tile text tidied.** The scenario stays on one line (tiles widened so none truncate); the
outcome sentence may wrap to two lines; and it is always the same colour, including for
abstentions - an override that had picked it out in amber is removed. A leftover unused style
rule from an earlier design pass is deleted.

**One paragraph per case, three per row.** Each overview tile now reads as a single paragraph: what
the case tests, fully explained; that case's own facts - vessels tracked and replayed, the nearest
vessel at image time and how far away - and what forward replay concluded, with its fit and
variant wins. So no two cases read alike. The grid is fixed at three per row (nine cases make an
exact 3 x 3), dropping to two or one only on narrow windows.

**Batch 1 of the card redesign.** Case Finding is rebuilt: the named vessel beside its fit gauge,
three fact tiles (variants won, lead over the runner-up, time inside the origin area) and the
proximity pick set aside on its own row - with every text column free to wrap, so nothing leaves
the card (checked in all nine cases). The reveal drops its closing sentence and glides: rows and
bars ease on a decelerating curve, staggered, and labels cross-fade. The Conclusion Graph loses
its stage-count badge. Ask behaves like a chat: a tapped or typed question appears at once, a
typing indicator follows, and the reply arrives below it; suggestions sit on one scrolling row.

**Batch 2 of the card redesign.** Observed Scene puts the scene's facts on the image as a
viewfinder HUD, with a radar sweep as it comes into view, and fills the fingerprint panel with the
shape, area and a grid of measurements. Rank Fragility draws the smallest flipping change on its
assumption's track of tested values, and explores by assumption tabs and tappable stops. Forward
Exposure is interactive: a +6/+12/+24 h control drives the counting spread figure, the chart's
highlighted hour and animated share bars for each sensitive area and the shoreline.

**Batch 3 of the card redesign.** Coverage-Aware Matching shows each rate as two concentric
activity rings (vessels hidden outside, area goes dark inside) with the better direction marked;
counts move to hovers and the disclosure. Traffic Filtering shows one dot per vessel, stage by
stage, down to the one named - or none - with its provenance as four compact chips. Next
Observation gains a time axis from the image, ghost tracks behind each window's disagreement and a
satellite over the recommended window, with the two vessels it would separate as chips.

**Case Finding as one designed object, and the cards in story order.** Case Finding is a single
hero in the manner of a macOS widget: the answer on the left, Fitness-style rings on the right -
the fit with the gate marked and the forcing variants won, or for an abstention the best fit
against the gate it needed - over a slowly drifting glow, blue or amber, with the proximity pick on
a slim strip below. Named and abstaining cases share the layout. The case's cards now run in the
order the story is told: the finding, the naive-versus-replay reveal, the replay map, rank
fragility, forward exposure, the observed scene, the next observation, then methodology.

---

## 13 September 2026

**Detect and characterise (PS part (a)) — new pipeline stage.**
`slicktrace_core/detection_geometry.py` runs the classical baseline detector over
each case scene, vectorises the retained region and measures area, perimeter,
principal axes, elongation and bearing. Served at
`/api/incidents/{id}/detection`, drawn as an outline over the scene in the
interface. IoU 0.91–0.92 against the generator truth mask across all six cases —
reported separately from the 0.676/0.688 benchmark-split figures, which measure
a deliberately harder task. Recorded as assumption A15: geometry is measured on
the pixel grid, not reprojected into the declared metric CRS.

**Interface — the finding now precedes the evidence.**
A verdict band states the outcome in plain language before any panel: the
proximity baseline's pick struck through, the forward-replay candidate beside
it, and on absent-source cases an explicit refusal to name anyone. A case
switcher exposes all six cases with their family and outcome, so the
cherry-picking objection can be checked rather than argued. Forecast, coverage,
next-observation and provenance panels surface results the API already served
but nothing displayed.

**Fresh-start rehearsal — two README defects found and fixed.**
Performed on a clean macOS account following the README literally. The Usage
section assumed an activated virtualenv and failed at its first command with
`ModuleNotFoundError`; the Docker section referenced a container name Compose
does not create. Both would have blocked a reviewer. Recorded in
`docs/evidence/fresh_start_rehearsal.md`.

**Docker — three executions recorded.**
Clean build, acceptance check online, and acceptance check with the container's
network disconnected, all 6/6. The build revealed that the Dockerfile still
copied `varuna_core/`, which the rename had removed — the image had never been
buildable. Logs in `docs/evidence/`.

**Dependencies pinned.** `requirements.lock` (34 packages) and
`requirements-dev.lock`. Case artifacts regenerate byte-identically under the
pinned set.

**Documentation.** Licence appendix now records four evaluated-but-unadopted
dependencies and their licence consequences — notably that OpenDrift is GPL v2
and would require relicensing this repository. README names the real-data
integration path per layer. Maintainer, licence holder and host matrix recorded.

---

## Before you merge: check which baseline you have

Two versions of this project have been in play.

**If your local repo has `slicktrace_core/fragility.py`**, you have the newer tree
and only the "Session changes" section below is new to you.

**If it does not**, your repo is the older build and the "Already present"
section is new to you as well — that is a much larger delta, and you should
treat this zip as the reference rather than cherry-picking from it.

Quick check:

```bash
ls slicktrace_core/fragility.py 2>/dev/null && echo "newer tree" || echo "older tree"
```

---

## Session changes — 12 files

### Fixed: release-acceptance check failed against its own tree

`scripts/smoke_test.py`

Hardcoded `V-TRUE-0001` and `V-DECOY-NEAR`, identifiers the generator no longer
produces. It failed 4/6 while the system underneath was entirely correct — a
broken test reporting a broken product.

Expected vessels now resolve from `truth.json` **by role** (`true_source`,
`near_decoy`) at run time, read from the local checkout and never from the API.
When the sidecar is unavailable — smoke-testing a remote host without the repo —
it falls back to structural checks and prints a note saying it is testing less,
rather than silently weakening.

**Both numeric tolerances are unchanged: `0.55` and `0.30`.** Loosening either
would have falsified the result rather than tested it. Verified 6/6 in both
modes, and 5/6 when the artifact is deliberately tampered with, which proves the
check can still fail.

### Fixed: Docker named volume shadowed baked-in cases

`Dockerfile`, `scripts/docker-entrypoint.sh`

A named volume is populated from the image only when first created. Cases were
copied straight to `/app/data`, the mount point, so every `build && up` after the
first would serve stale results while reporting a new image — silent, and exactly
the failure that bites during a rehearsal.

Cases now bake into `data_seed/`, the image carries a `.seed_id` content hash,
and the entrypoint syncs seed → volume when the ids differ, before the startup
check runs. Verified by executing the sync logic against a simulated volume
across three scenarios: fresh, restart, and rebuild-with-changed-cases. The
rebuild correctly served new data while a user-created extra case survived
untouched.

### Fixed: metric popovers were unreachable by tap

`frontend/src/MetricInfo.jsx`

`onMouseEnter` opened the popover and `onClick` toggled it, so the click
immediately closed what the hover had opened. Touch browsers synthesise
`mouseenter` before `click`, so on mobile the explanation never appeared. Hover
worked; tap silently did nothing — which is precisely the interaction the plan
asks for ("hover or tap").

Fixed with a separate `pinned` state distinguishing hover-open from
deliberate-open, plus `onBlur` for keyboard users.

### Wired up: the live slider, fragility control and metric help

`frontend/src/App.jsx`, `frontend/src/api.js`, `frontend/src/dashboard.css`

`TimeSliderMap.jsx`, `FragilityPanel.jsx` and `MetricInfo.jsx` existed but
`App.jsx` never imported them and `api.js` exposed no method for six endpoints.
They were tree-shaken out of the built bundle entirely.

This was more than an import. **None of the CSS these components needed
existed** — every class they referenced was undefined, which is presumably why
they were never wired. Added ~200 lines to `dashboard.css` using only existing
design tokens; no new colours.

Browser-verified on desktop and mobile: slider present and keyboard-operable
(6 × ArrowRight moves 04:30 → 22:30 UTC), `aria-valuetext` correct, 7-row
text-equivalent table, 4 fragility sweep steps, 2 metric popovers, zero console
errors, zero external requests.

Also fixed a header-wrap regression this introduced — the fourth topbar tag
squeezed the wordmark onto two lines at narrow widths.

### Added: recall and precision

`slicktrace_core/baseline_detector.py`, `scripts/run_validation.py`

The plan asks for recall ≥ 0.85 and precision alongside IoU. Neither was
measured.

**This surfaced a finding worth knowing before the deck is written: the
classical baseline reaches recall 0.68 on val and 0.70 on test, against a 0.85
target.** Precision is 0.89–0.99 and false-positive rates are 0.000, so the
detector is conservative rather than inaccurate — it rejects patchy regions,
which buys precision and costs recall.

The report states the miss in bold rather than reporting IoU alone and letting
the target go unmentioned. It is also a sharper argument for the U-Net than
existed before: the number to beat is recall, not IoU.

### Added: runtime reporting

`scripts/run_pipeline.py`, `scripts/run_validation.py`

Per-stage timings were already being measured and then discarded at exit, which
forfeited a feasibility claim the run had already earned. Now written to
`docs/runtime.json` with the hardware named, and surfaced in the validation
report.

Query latency is split four ways after a first version reported "0 ms" for both
cold and warm — the timer was starting after the knowledge base had already
loaded, and the cheapest intent finishes in microseconds. Now: 1.2 ms cold /
0.01 ms warm for a lookup intent, 3.9 ms cold / 1.0 ms warm for the
envelope-backed time-window query, against a 2-second target.

### Added: regression test for the frozen case

`tests/test_frozen_case.py` — 6 tests

Pins the demo invariant **by role** so it survives regeneration, and asserts no
vessel key contains "true", "decoy", "source" and similar. Reverting to
hardcoded identifiers now fails loudly instead of silently reintroducing the
ground-truth leak.

### Added: dependency pins

`requirements.txt`

All nine packages pinned exactly to the versions every number in the validation
report was produced under, verified programmatically against the installed
environment. torch remains deliberately absent from the served path.

### Added: LICENSE

MIT, which `manifest.provenance.license` already referenced but which did not
exist. Includes scope notes separating code from data.

**Two fields are yours to confirm:** the licence choice, and the copyright
holder line, currently "Slick Trace team (SIH26143)".

### Added: three appendices

- `docs/assumptions_register.md` — 13 entries, each with a verified `file:line`
  locator and its failure mode
- `docs/licence_and_data_rights.md` — what ships, under what terms, what a real
  source would need
- `docs/sustainability_and_ownership.md` — running costs, refresh cadence,
  handover position, roadmap

### Changed: `.dockerignore`

`truth.json` excluded from the image. This was blocked before, because
excluding it would have broken in-container smoke tests — the role-resolution
fix unblocked it. Also excluded `tests/` and `.pytest_cache/`.

### Rewritten: README

Was five steps out of date and still cited identifiers that no longer exist. Now
matches the tree, links the appendices, and lists known limitations including the
recall miss.

---

## Already present — only new to you if your repo lacks `fragility.py`

Five modules: `fragility.py`, `coverage.py`, `forecast.py`,
`next_observation.py`, `report.py`. Six independently seeded cases across four
families, replacing the single case. A locked detection test split. Neutral MMSI
identifiers with ground truth moved to a dev-only `truth.json` sidecar and a
`_strip_truth` guard on every API response. `tests/test_invariants.py`,
`tests/nlp_suite.py`, `tests/test_api_and_suite.py`. `scripts/run_pipeline.py`
and `scripts/run_validation.py`. Eleven new API endpoints. The three frontend
components this session wired up.

---

## Verification of this package

Run from a clean extraction of this zip:

```bash
pip install -r requirements.lock -r requirements-dev.lock
python3 scripts/run_pipeline.py --regenerate   # ~32 s, six cases
python3 scripts/run_validation.py
python3 -m pytest tests/ -q                    # 119 passed

cd frontend && npm ci && npm run build && cd ..
./run.sh &                                     # or: uvicorn backend.app:app --port 8000
python3 scripts/smoke_test.py                  # 6/6
```

`frontend/dist`, `node_modules`, `__pycache__`, `.pytest_cache` and `.venv` are
excluded from this archive — build artefacts, regenerated by the commands above.

---

## Not verified anywhere, still on you

**Docker has never been built or run.** No daemon was available. The plan names
three executions that must happen and be recorded: `docker build` from a clean
context, a network-disconnected acceptance run, and a fresh-user start by a
teammate who did not write the code following only the README. A written
Dockerfile proves nothing.

**The U-Net is untrained.** torch does not fit the sandbox disk quota. It stays
labelled implemented-but-unevaluated everywhere, which is the correct framing.

**No real data.** Zenodo, DMA, NOAA and Copernicus are unreachable. Every result
is synthetic and labelled as such.

**No git history.** There is no `.git` directory, so there is no tagged build —
and the plan requires video, deck and code to demonstrably match. Initialise a
repository before recording anything.

Plus: host matrix, SPOC confirmation of the official rubric, the demo video, the
presentation, a named maintainer in the README, and one outside conversation.
