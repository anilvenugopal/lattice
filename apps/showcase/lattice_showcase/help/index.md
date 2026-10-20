---
title: Showcase
summary: A carrier responding to catastrophes, built with every Lattice component.
---

The showcase is a **catastrophe response app** for a property and casualty
carrier. When a hurricane is forecast, the team needs to know which insured
locations are in its path and what it could cost. Once it lands, they need to
know how claims are arriving and who is handling them.

The app sits beside the systems of record. It reads policies and claims from
them, and keeps the response itself: events, footprints, exposure, estimates,
assignments, assessments and field reports.

| Page | Use it to |
|---|---|
| [Events](events.md) | See each catastrophe, declare a new one, follow its footprint and exposure |
| [Loss estimate](events.md#loss-estimate) | See what an event could cost, from a Monte Carlo simulation |
| [Claims](claims.md) | Work the claims across events: assign, prioritise, assess, report |
| [Locations](locations.md) | Search the insured locations on the map, and save an area |

## What is real and what is simulated

| Data | In production, from | In the showcase |
|---|---|---|
| Insured locations | Policy administration, as a nightly snapshot | 42,659 synthetic locations in real metro areas |
| Claims | The claims system, every few minutes | Seeded for past events; a labelled simulator for Hurricane Delta |
| Hurricane forecast | National Hurricane Center advisories | Three sample advisory cones |
| Loss estimate | A licensed catastrophe model | A simple Monte Carlo with stated assumptions |

Places, counties and coastlines are real; policies, people and claims are not.

> [!TIP]
> Press **F1** on any page to open the help for that page, and **Ctrl J** to
> search pages, events, claims, commands and help from anywhere.
