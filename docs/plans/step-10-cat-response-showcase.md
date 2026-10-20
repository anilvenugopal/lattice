# Step 10 plan: the catastrophe response showcase

Status: **draft for approval** (19 October 2026). Builds on
[ADR 0013](../adr/0013-geoengine-and-maps.md), also for approval.

## Why

Today's showcase uses meaningless sample data, so its components look arbitrary:
a year squeezed into one calendar strip, trees of unrelated items, jobs that only
pretend. The audience is a P&C insurance group. The new showcase tells one story
they know: **a carrier responding to catastrophes**. Every Lattice component has a
natural job in it, and every simulated part says so on screen.

## The story

The app is a **command centre beside the systems of record**, not a policy or
claims system:

| Data | System of record (real life) | In the showcase |
|---|---|---|
| Insured locations | Policy administration and the exposure warehouse; a nightly snapshot | 40,000 synthetic locations across Texas, Louisiana, Florida and California, seeded |
| Claims | The claims system; new claims (FNOL) pulled every few minutes | Seeded for past events; **a simulator, labelled**, for the live one |
| Hurricane forecast | National Hurricane Center advisories | Bundled sample cone files, one per advisory |
| Events, footprints, exposure runs, assignments, assessments, field reports, notes | **This app** | Built here |

Each policy and claim shows its system-of-record number and an "Open in claims
system" link (to a placeholder page in the showcase).

## The four events

| Event | Peril | Status | Shows |
|---|---|---|---|
| Hailstorm, Dallas–Fort Worth (April) | Hail | Closed | A complete history: claims curve, cycle times, final totals |
| Winter freeze, Texas (February) | Freeze | Closed | Another peril, with its own assessment form |
| Wildfire, Northern California (August) | Wildfire | Recovery | A perimeter polygon; a long tail of claims; buffers ("within 2 km") |
| Hurricane Delta, Gulf Coast (now) | Hurricane | Live | Advisories, footprint versions, exposure runs, Monte Carlo, live intake |

## Pages

| Page | What it shows | Components |
|---|---|---|
| **Overview** | What the showcase is, the story, and the showcase-vs-production table above | — |
| **Events** | All events; tabs Active and Closed; **Declare event** | Grid, saved views |
| **Event page** | Header with lifecycle stepper (Watch → Landfall → Response → Recovery → Closed); key totals; map of exposure and claims; claims per day; footprint versions; Comments | Record page, stepper, map, charts, panels |
| **Declare event** | The event form, which changes by peril (hurricane: category, wind speed, PCS code; hail: hail size; wildfire: acres, containment; freeze: minimum temperature). Footprint by picking counties on a map, or uploading a GeoJSON file | JSON Schema form with variants, upload, map |
| **Exposure** (per event) | Locations inside the footprint: insured value by county (map), by line and construction (treemap), hexagon concentration, location quality tiers; **Run exposure** after a footprint change, with progress | Grid, map, charts, async action, live list |
| **Loss estimate** (per event) | **Monte Carlo, illustrative**: 1,000 simulated storms; histogram of losses; average; 1-in-100 and 1-in-250; exceedance curve; assumptions stated | Background job, charts |
| **Claims** | Claims across events: intake channel, severity, zone, adjuster; bulk **Assign zone**, **Raise priority**; map; one-month calendar around landfall; sankey channel → severity → status; event comparison (claims per day since landfall, one line per event) | Grid, bulk actions, charts, map |
| **Claim page** | Policy and location (with quality tier), the damage assessment, the claim's tree (claim → coverages → payments estimate), field reports, Comments, history | Record page, tree, panels, forms |
| **Damage assessment** | Form chosen by property type: home (roof, interior water), auto (flood line), commercial building (stock, business interruption) | JSON Schema forms |
| **Field reports** | Free-form reports surveyors send; the lead's reading pane | Split grid, free-form documents |
| **Deployment** | Teams → zones → claims as a graph; select a node to reassign or escalate | Graph with node actions |
| **Intake (live)** | The claims simulator for Hurricane Delta, labelled; start, pause, and a speed control so a presenter can make a spike | Polling grid, async actions |
| **Locations** | The exposure snapshot: search, tiers, hexagon map | Grid, map |

The Comments app stays: notes on claims and events, and the zone lead is told.

## The pieces to build

| # | Stage | Contents |
|---|---|---|
| 1 | **geoengine** | `packages/geoengine`: schema `geo` (layers, features), PostGIS, H3 in Python, quality tiers, GeoJSON and CSV loading, point-in-area and distance functions, contract with a test, the import rule. Database image `postgis/postgis:18-3.6` |
| 2 | **Lattice map component** | `MapSpec` with points, hexagons, regions (US states and counties) and areas; linked to grid filters; MapLibre vendored; tokens for colours, light and dark; the self-hosted basemap with `make maps`, falling back to outlines; a file upload field for forms |
| 3 | **Chart fixes** | The calendar as a single month grid (with month navigation); a histogram kind; an exceedance curve (line on sorted values) |
| 4 | **Data and events** | 40,000 locations with realistic counties, construction, occupancy, values and tiers; the four events with footprints; past claims with plausible curves; the sample hurricane advisories |
| 5 | **Pages, part 1** | Overview, Events, Event page, Declare event, Exposure, Locations |
| 6 | **Pages, part 2** | Claims, Claim page, Damage assessment, Field reports, Deployment, Intake (live) |
| 7 | **Monte Carlo** | The loss estimate job and page, with its assumptions page |
| 8 | **Docs and tests** | Help for every page in the audience's terms; developer help for geoengine and maps; the old showcase removed |

## The Monte Carlo loss estimate, plainly

For Hurricane Delta at its latest advisory:

1. **Storms.** 1,000 variations of the forecast: the track shifted sideways within
   the cone, and the peak wind stronger or weaker.
2. **Wind at each location.** Falls off with distance from the track.
3. **Damage.** A damage ratio from wind speed and construction (frame, masonry,
   steel) on a simple curve, with random variation.
4. **Loss.** Damage ratio × insured value, less the deductible, summed per storm.

Shown: the histogram, the average, the 1-in-100 and 1-in-250 losses, the exceedance
curve, and a page that states every assumption and says it is illustrative, not a
catastrophe model. It runs as a background job with progress; Taskline will run
jobs like it later. Computed with numpy in the showcase (a dependency of the
showcase only).

## Not in this step

- Pre-season re-underwriting across the whole book (accumulation tiers, PML): the
  same machinery, later.
- Real address geocoding; reading live NHC feeds; writing cat codes back to a
  claims system.
- Payments, policy administration, rating.

## Decisions taken

The owner's answers of 19 October 2026: geoengine as a separate package in the
workspace first; the self-hosted basemap; the four events; Monte Carlo in this
version; location quality tiers and hexagons in this version.

## Decisions for approval

1. **Downloads:** the basemap extract (a few hundred MB, plus fonts) from
   Protomaps' public build, and MapLibre, `pmtiles` and `h3-js` from npm. I will
   state each file and size before downloading.
2. **New Python dependencies:** `shapely` and `h3` (geoengine), `numpy` (showcase).
3. **Order:** stages 1 to 8 as listed, each committed on its own and reviewed at
   the end.
