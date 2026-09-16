# DESIGN.md — Dashboard design tokens & states

This is not the Best UI track submission — the dashboard exists to make the
demo video legible, not to win on design. Keep it clean and legible over
decorated. One page, no routing.

## Layout
```
┌─────────────────────────────────────────────┐
│  AWS Cost Guardrail          [env: prod ▾]   │
├─────────────────────────────────────────────┤
│  Incident feed (newest first)                │
│  ┌───────────────────────────────────────┐   │
│  │ 🔴 RUNAWAY   14:32:05   guardrail-api  │   │
│  │ "3 callers, identical payload, no      │   │
│  │  deploy event — stuck retry loop"      │   │
│  │ [PENDING APPROVAL]  [Approve] [Reject] │   │
│  ├───────────────────────────────────────┤   │
│  │ 🟢 NORMAL    14:28:10   guardrail-api  │   │
│  │ "1,200 unique callers, matches load    │   │
│  │  test deploy 3 min ago — legitimate"   │   │
│  │ [NO ACTION TAKEN]                      │   │
│  └───────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Color tokens
| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#0f1117` | page background (dark, reads well on recorded video) |
| `--color-surface` | `#181b24` | incident card background |
| `--color-border` | `#2a2e3a` | card border |
| `--color-text-primary` | `#f5f6f8` | headings, primary text |
| `--color-text-secondary` | `#9aa0ad` | timestamps, metadata |
| `--color-runaway` | `#ef4444` | RUNAWAY classification, red |
| `--color-normal` | `#22c55e` | NORMAL classification, green |
| `--color-pending` | `#f59e0b` | PENDING_APPROVAL, amber |
| `--color-accent` | `#3b82f6` | buttons, links |

## Typography
- Font: system stack (`-apple-system, Segoe UI, Roboto, sans-serif`) — no
  webfont loading dependency for a hackathon demo
- Headings: 20px / 600 weight
- Body: 14px / 400 weight
- Monospace (for the raw payload snippets shown in an incident): `ui-monospace, Menlo, monospace`, 13px

## Component states
**Incident card**
- `NORMAL` → green left border, no action buttons, collapsed by default
- `RUNAWAY` + `AUTO_THROTTLED` → red left border, "Auto-throttled" badge,
  no buttons (already resolved)
- `RUNAWAY` + `PENDING_APPROVAL` → amber left border, pulsing dot, Approve /
  Reject buttons visible
- `RUNAWAY` + `APPROVED_AND_THROTTLED` → red left border, "Approved by
  {resolved_by}" badge

**Approve button**
- Default: solid `--color-accent`
- Loading (mid-request): spinner, disabled
- After click: card transitions to resolved state, buttons disappear

## What NOT to build
- No auth/login UI — a name field on approve is enough for the demo
- No charts/graphs — a chronological list is more legible on a recorded
  video than a live-updating graph would be
- No dark/light mode toggle — pick dark, ship it
