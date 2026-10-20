# 0015. Chart colours: one hue by default, colour only where it means something

Status: Accepted (20 October 2026). Builds on [0004](0004-charts-chartjs.md) and the
colour rules of [0010](0010-theming-and-overrides.md).

## Context

Charts gave every category and series its own colour from an eight-colour palette. A
doughnut of causes was eight colours; a bar chart of severities four. The colours carried
no meaning, yet readers looked for one, and a page with four charts looked busy. The
owner asked for calm charts: shades of the theme colour or of grey, with colour kept for
what matters.

## Decision

**A chart chooses a colour mode** (`ChartSpec.colors`):

| Mode | Draws | Use when |
|---|---|---|
| `brand` (default) | One series in the theme's brand colour. Several series, slices or boxes: shades of it, darkest for the largest | Almost always |
| `neutral` | The same in greys | Calm dashboards, print |
| `tones` | Each value in its `Column.tones` colour | Colour has a meaning: severity, status |
| `categorical` | The eight distinct series colours | Series must be told apart and shades would blur them |

A host sets the default for charts that name none (`LATTICE_CHART_COLORS`, `brand` or
`neutral`).

**Highlight instead of decorating.** `highlight=[Highlight(values=["total"], tone="danger")]`
or `Highlight(above=1_000_000, tone="warning")` draws the matching bars, slices or boxes
in a tone and every other one in a muted grey, so the eye goes to the point. Threshold
lines are unchanged.

**Colours stay in tokens.** The modes read `--chart-base` (the brand colour), `--chart-calm`
(grey) and `--chart-muted`, in light and dark; shades are mixed from them and the panel
colour in the browser. A host theme that changes `--brand` changes every chart, map shading
and timeline bar. Apps name modes and tones, never colours (ADR 0010).

**Maps and timelines follow.** Map shading uses the base colour; timeline bars use it
unless a tone column is named.

## Not chosen

- **A palette editor in the app**: colours are the host's theme, set once in tokens.
- **A per-user colour preference**: possible later; not needed to fix the problem.

## Consequences

- Charts that relied on the palette to tell series apart must say `categorical`.
- Charts whose colours mean something (severity) must say `tones`.
