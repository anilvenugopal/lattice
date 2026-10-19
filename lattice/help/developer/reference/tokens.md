---
title: Design tokens
summary: Every CSS token with its light and dark value, and which a host theme may change.
order: 70
keywords: css variables colours colors theme dark light brand
---

> [!NOTE]
> Generated from `lattice/static/css/1-settings/tokens.css` by `lattice docs build`. Change the code, not this page.

Components style themselves with these tokens (`var(--text-2)`, `var(--sp-3)`), never with colour values. The dark theme changes the semantic tokens and nothing else, so anything built from tokens works in both themes.

**Host theme** marks the tokens a host's `static/theme.css` may set (ADR 0010). Primitive tokens (`--p-*`) are private to `tokens.css` and not listed.

| Token | Light | Dark | Host theme |
|---|---|---|---|
| `--font-ui` | `"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif` | same | yes |
| `--font-mono` | `"IBM Plex Mono", ui-monospace, "Cascadia Code", Consolas, monospace` | same | yes |
| `--fs-2xs` | `10px` | same |  |
| `--fs-xs` | `11px` | same |  |
| `--fs-sm` | `12px` | same |  |
| `--fs-md` | `13px` | same |  |
| `--fs-base` | `14px` | same |  |
| `--fs-lg` | `16px` | same |  |
| `--fs-xl` | `20px` | same |  |
| `--fs-2xl` | `24px` | same |  |
| `--fs-display` | `40px` | same |  |
| `--fw-regular` | `400` | same |  |
| `--fw-medium` | `500` | same |  |
| `--fw-semibold` | `600` | same |  |
| `--lh-tight` | `1.25` | same |  |
| `--lh-base` | `1.45` | same |  |
| `--lh-loose` | `1.6` | same |  |
| `--sp-1` | `4px` | same |  |
| `--sp-2` | `8px` | same |  |
| `--sp-3` | `12px` | same |  |
| `--sp-4` | `16px` | same |  |
| `--sp-5` | `20px` | same |  |
| `--sp-6` | `24px` | same |  |
| `--sp-8` | `32px` | same |  |
| `--sp-10` | `40px` | same |  |
| `--r-sm` | `4px` | same |  |
| `--r-md` | `6px` | same |  |
| `--r-lg` | `8px` | same |  |
| `--r-xl` | `12px` | same |  |
| `--r-pill` | `999px` | same |  |
| `--dur` | `140ms` | same |  |
| `--z-menu` | `40` | same |  |
| `--z-tooltip` | `60` | same |  |
| `--z-overlay` | `80` | same |  |
| `--z-toast` | `100` | same |  |
| `--surface-page` | `#F7F8FA` | `#0E1320` | yes |
| `--surface-panel` | `#FFFFFF` | `#151B2B` | yes |
| `--surface-recessed` | `#F0F2F5` | `#1B2234` | yes |
| `--surface-hover` | `#F0F2F5` | `#1B2234` | yes |
| `--surface-selected` | `#EEF3FC` | `#1D2A47` | yes |
| `--surface-selected-strong` | `#D8E5F8` | `#243560` | yes |
| `--surface-nav` | `#FFFFFF` | `#151B2B` | yes |
| `--surface-rail` | `#1C2333` | `#0A0E18` | yes |
| `--surface-rail-hover` | `#2A3348` | `#1B2234` | yes |
| `--surface-rail-active` | `#33405C` | `#232B3F` | yes |
| `--surface-statusbar` | `#1A3461` | `#13213F` | yes |
| `--surface-inverse` | `#151B2B` | `#313A50` | yes |
| `--surface-input` | `#FFFFFF` | `#1B2234` | yes |
| `--surface-overlay` | `rgba(15, 22, 41, 0.45)` | `rgba(0, 0, 0, 0.6)` | yes |
| `--border` | `#DCE0E8` | `#232B3F` |  |
| `--border-strong` | `#C3CAD6` | `#313A50` |  |
| `--border-faint` | `#E7EAF0` | `#1B2234` |  |
| `--text` | `#151B2B` | `#E6EAF2` | yes |
| `--text-2` | `#4B5569` | `#AAB4C6` | yes |
| `--text-3` | `#64748B` | `#8591A6` | yes |
| `--text-disabled` | `#94A3B8` | `#5A657A` | yes |
| `--text-inverse` | `#FFFFFF` | same | yes |
| `--text-on-brand` | `#FFFFFF` | same | yes |
| `--text-on-rail` | `#A9B3C7` | same | yes |
| `--text-on-rail-strong` | `#FFFFFF` | same | yes |
| `--text-on-statusbar` | `rgba(255, 255, 255, 0.85)` | same | yes |
| `--link` | `#2E57A8` | `#8FAADC` | yes |
| `--brand` | `#2E57A8` | `#4C74C4` | yes |
| `--brand-hover` | `#234484` | `#5D84D2` | yes |
| `--brand-alt` | `#5B3BA8` | same | yes |
| `--accent` | `#D4820F` | same | yes |
| `--text-on-accent` | `#1A1200` | same | yes |
| `--danger` | `#BE2D44` | `#D9475E` |  |
| `--danger-hover` | `#9B1F33` | `#E8657A` |  |
| `--success` | `#2E8F5E` | same |  |
| `--warning` | `#D4820F` | same |  |
| `--info` | `#8FAADC` | same |  |
| `--highlight` | `#D4820F` | same |  |
| `--wash-on-dark` | `rgba(255, 255, 255, 0.15)` | same |  |
| `--tone-neutral-bg` | `#F0F2F5` | `#222A3C` |  |
| `--tone-neutral-fg` | `#4B5569` | `#B4BDCD` |  |
| `--tone-neutral-bd` | `#DCE0E8` | `#2E374C` |  |
| `--tone-info-bg` | `#EEF3FC` | `#18264A` |  |
| `--tone-info-fg` | `#234484` | `#9DB8EC` |  |
| `--tone-info-bd` | `#B8CCF0` | `#263A6A` |  |
| `--tone-success-bg` | `#E8F7EF` | `#12301F` |  |
| `--tone-success-fg` | `#1E6B45` | `#7FD1A3` |  |
| `--tone-success-bd` | `#A8D9BE` | `#1D4A31` |  |
| `--tone-warning-bg` | `#FDF8EE` | `#33250C` |  |
| `--tone-warning-fg` | `#8A5208` | `#EBBE6A` |  |
| `--tone-warning-bd` | `#F5D89A` | `#4D3812` |  |
| `--tone-danger-bg` | `#FCEEF0` | `#3A151C` |  |
| `--tone-danger-fg` | `#9B1F33` | `#F09AA8` |  |
| `--tone-danger-bd` | `#F0B8C0` | `#5A1F2A` |  |
| `--tone-accent-bg` | `#F3EFFC` | `#261C42` |  |
| `--tone-accent-fg` | `#5B3BA8` | `#BFAAF0` |  |
| `--tone-accent-bd` | `#D5C8F2` | `#3A2B66` |  |
| `--chart-1` | `#2E57A8` | `#8FAADC` |  |
| `--chart-2` | `#D4820F` | `#EDB45A` |  |
| `--chart-3` | `#1F8A8A` | `#5CC2C2` |  |
| `--chart-4` | `#8E4BA8` | `#C08AD6` |  |
| `--chart-5` | `#C2547A` | `#E58DAD` |  |
| `--chart-6` | `#7A8A2E` | `#B5C46A` |  |
| `--chart-7` | `#2F8FD0` | `#79BCEB` |  |
| `--chart-8` | `#7A5CC8` | `#A993E6` |  |
| `--chart-neutral` | `#94A3B8` | `#64748B` |  |
| `--chart-info` | `#4C74C4` | `#8FAADC` |  |
| `--chart-success` | `#2E8F5E` | `#6CC495` |  |
| `--chart-warning` | `#D4820F` | `#EDB45A` |  |
| `--chart-danger` | `#BE2D44` | `#E8657A` |  |
| `--chart-accent` | `#7A5CC8` | `#A993E6` |  |
| `--chart-grid` | `#E7EAF0` | `#232B3F` |  |
| `--focus-ring` | `0 0 0 3px rgba(46, 87, 168, 0.28)` | `0 0 0 3px rgba(143, 170, 220, 0.35)` |  |
| `--shadow-sm` | `0 1px 2px rgba(15, 22, 41, 0.06)` | `0 1px 2px rgba(0, 0, 0, 0.4)` |  |
| `--shadow-md` | `0 4px 12px rgba(15, 22, 41, 0.10), 0 1px 3px rgba(15, 22, 41, 0.06)` | `0 4px 14px rgba(0, 0, 0, 0.45)` |  |
| `--shadow-lg` | `0 16px 40px rgba(15, 22, 41, 0.18), 0 2px 6px rgba(15, 22, 41, 0.08)` | `0 18px 44px rgba(0, 0, 0, 0.6)` |  |
| `--rail-w` | `56px` | same |  |
| `--sidebar-w` | `220px` | same |  |
| `--topbar-h` | `48px` | same |  |
| `--statusbar-h` | `24px` | same |  |
| `--control-h` | `28px` | same |  |
| `--control-h-sm` | `28px` | same |  |
| `--row-pad-y` | `4px` | same |  |
| `--panel-w` | `420px` | same |  |
| `--palette-w` | `1080px` | same |  |
| `--palette-nav-w` | `190px` | same |  |
| `--palette-preview-w` | `400px` | same |  |
| `--help-nav-w` | `240px` | same |  |
| `--help-toc-w` | `200px` | same |  |
| `--help-content-w` | `780px` | same |  |
| `--avatar-gradient` | `linear-gradient(135deg, var(--brand), var(--brand-alt))` | same |  |
| `--tooltip-bg` | `var(--surface-inverse)` | same |  |
| `--tooltip-fg` | `var(--text-inverse)` | same |  |
| `--toast-bg` | `var(--surface-inverse)` | same |  |
| `--toast-fg` | `var(--text-inverse)` | same |  |
| `--brand-logo-h` | `26px` | same |  |
