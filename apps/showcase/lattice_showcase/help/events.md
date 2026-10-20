---
title: Events
summary: Catastrophes the carrier is responding to: footprints, exposure and the loss estimate.
order: 10
keywords: catastrophe cat hurricane hail wildfire freeze footprint advisory exposure declare pcs
---

An **event** is a catastrophe the carrier responds to. The showcase has four:
a Texas freeze and a Dallas–Fort Worth hailstorm (closed), the Glass Fire in
Napa and Sonoma (in recovery), and **Hurricane Delta**, which is live.

## The list

The **timeline** above the list shows the year's events: the watch before
landfall, then the response, and a diamond when the event closed. Delta's
response is still going, so its bar runs to the dashed "now" line. Drag across
it to zoom; click a bar to open the event.

- **Tabs**: Active, Closed and All.
- **Next stage** moves an event along: Watch → Landfall → Response → Recovery →
  Closed.
- Click a row to open the event.

## The event page

- **Stage**: where the event is in its lifecycle.
- **At a glance**: exposed value, claims, open claims and the estimated loss.
- **Exposure inside the footprint**: a map of the insured value by county,
  with the footprint drawn over it.
- **Claims as they arrived**: per day, on a calendar, and from intake channel
  to status.
- **Footprint versions**: each forecast advisory or perimeter update, with the
  exposure it covered. For Delta, the exposed value falls as the forecast
  moves east, away from Houston.
- **Comments**: notes for the team.
- **Attachments**: files kept with the event, such as advisories or a
  perimeter map. See [Attachments and folders](/help/lattice/user-guide/attachments).

## Declare an event

**Declare event** asks for the peril's own details: category and wind for a
hurricane, hail size, acres burned, or the lowest temperature. Then it asks for
the affected area, as one of:

- the **counties** under a warning, by name;
- a **GeoJSON file**, such as a perimeter from a fire agency;
- an **area saved** on the [Locations](locations.md) map.

The exposure runs in the background as soon as the event is saved.

## Exposure

The event's **Exposure** page lists the insured locations inside the latest
footprint, with the map (by county, as hexagons, or each location) and charts
by line, construction, county and location quality.

- **Draw** a polygon, rectangle or circle on the map to narrow the list,
  totals and charts to it.
- **New footprint version** adds an advisory or perimeter update; the exposure
  runs again, and **Exposure runs** shows its progress.

**Location quality** says how precisely a location is known: rooftop, parcel,
street, zip centroid or county centroid. A location known only to its zip code
may be inside or outside a footprint, so treat those counts with care.

## Loss estimate

The **Loss estimate** simulates 1,000 storms like the forecast, some stronger,
some weaker, some further along the cone, and adds up the damage to every
exposed location in each. It shows:

- the **average** loss;
- the **1-in-100** loss: one storm in a hundred costs more than this;
- the **1-in-250** loss;
- how often each loss came up, and the chance the loss is more than any amount.

**Run estimate** runs a new one against the current footprint. Every assumption
is on the page.

> [!WARNING]
> The loss estimate is illustrative: simple curves, chosen to show how such an
> analysis looks and runs. Real estimates come from licensed catastrophe models.
