# WiFi Vision Lab — Signal Atlas Design System

Status: approved design direction, implementation in progress  
Scope: local-first network observation and Wi-Fi intelligence desktop web UI  
Primary platform: Windows 11 laptop, Streamlit application  
Theme: light only

## 1. Product design intent

WiFi Vision Lab is an evidence-first network observability workspace, not a generic admin template. The interface must help an operator answer, in order:

1. What is happening in my local network?
2. What changed since the previous observation?
3. Which devices or relationships need attention?
4. What evidence supports this conclusion?
5. What action or deeper investigation is available?

The visual language is **Signal Atlas**: calm, technical, precise, and readable over long sessions. Avoid decorative gradients, oversized empty cards, neon accents, excessive color, ornamental charts, and dashboard clutter.

## 2. Design review team (discipline model)

Every design decision is reviewed through these roles:

- Product design lead: information architecture, task flows, terminology, consistency.
- Observability UX designer: signal hierarchy, event investigation, topology and time-series semantics.
- Windows desktop UI designer: typography, density, keyboard behavior, responsive desktop layout.
- Accessibility specialist: WCAG contrast, focus visibility, keyboard access, non-color status cues.
- Frontend performance engineer: Streamlit reruns, chart rendering cost, data table size, refresh policy.

These are review perspectives, not claims that external people or a separate human team were engaged.

## 3. Visual foundation

### Color tokens

| Token | Value | Usage |
|---|---|---|
| Background | #F2F5F3 | App canvas |
| Surface | #FFFFFF | Cards, tables, dialogs |
| Soft surface | #F7F9F8 | Subtle grouping and code surfaces |
| Border | #DCE5E1 | Dividers and component boundaries |
| Text | #182B2A | Primary text |
| Muted | #617370 | Secondary text and metadata |
| Accent | #087F78 | Primary action and active navigation |
| Accent strong | #066A65 | Hover and high-emphasis accent |
| Accent soft | #E4F3F0 | Selected states |
| Success | #167A55 | Confirmed healthy/success state |
| Warning | #A96B16 | Needs attention |
| Danger | #B84040 | Critical/error |
| Info | #426C8C | Informational state |

Color is never the only carrier of status. Pair it with a label, icon, value, or shape. Do not imply a device is healthy merely because data is missing; unknown remains unknown.

### Typography

- Primary stack: Segoe UI Variable, Segoe UI, Inter, system sans-serif.
- UI body: 14 px / 20–22 px.
- Secondary labels: 12–13 px / 16–18 px; never use tiny text for essential values.
- Page title: 26–30 px, semibold.
- Section title: 18–21 px, semibold.
- KPI value: 24–26 px, semibold, tabular numerals.
- Technical identifiers, IPs, MACs, counters: tabular numerals; monospace only when copy/paste or exact character alignment matters.
- Use sentence case in Turkish; avoid all-caps content labels except short navigation group captions.

### Spacing, shape, and elevation

- 4 px base grid, 8 px primary rhythm.
- Controls: 7 px radius; cards: 10 px; large panels/dialogs: 14 px.
- Use borders and spacing for hierarchy; shadows remain extremely subtle.
- Keep cards aligned to a consistent grid. Avoid a card for every single text block.

## 4. Navigation and shell

Persistent left rail, approximately 258 px wide on desktop. The brand lockup sits at the top, followed by grouped navigation:

- Overview: Dashboard
- Device management: Devices, Device history, Device detail
- Network intelligence: Network events, Behavior analysis, Network topology, Live monitoring, Wi-Fi signal, Spatial intelligence, Network infrastructure
- System: Reports

Navigation rules:
- One selected page, with a tinted background and clear text/icon contrast.
- Consistent monochrome line-symbol family; symbols are secondary to labels.
- Keep scan scope and scan action in a distinct utility area, not mixed with page links.
- Sidebar scrolls independently on short displays.
- On narrow screens, preserve all navigation functions; never silently hide destinations.

## 5. Page architecture

### Dashboard — “Network control center”
The landing page is an operational briefing, not a miniature copy of every page.

Recommended hierarchy:
1. Header: title, one-line purpose, local observation freshness.
2. Network state strip: scan state, last successful observation, data freshness.
3. Four primary KPIs: known devices, responding devices, recent changes, open findings. Only show metrics with valid source data.
4. “Needs attention” list: highest-severity findings with evidence and a direct drill-down.
5. Device and event trends: compact time series / distribution only when history supports them.
6. Recent observations: short table with time, device identity, event and source.
7. Primary action: start a scan; secondary action: open inventory.

No fabricated percentages, confidence scores, latency, or health statuses. Empty history means “not enough observations”, not “zero incidents”.

### Device inventory
- Search first, then compact filter row (status, type, vendor, source).
- Table-first for scanning; card mode only when visual comparison adds value.
- Pin identity columns (name, IP, MAC) where practical.
- Row action opens a detail dialog or page; do not force a large card per device.
- Preserve unknown/missing fields rather than guessing.

### Device history and detail
- Timeline/table with consistent timestamp formatting and filters.
- Device detail is organized into identity, network configuration, classification evidence, observed changes, and related AP associations.
- Distinguish observed, inferred, and verified values explicitly.

### Network events and live monitoring
- One event vocabulary across pages.
- Severity, event type, subject identity, time, source, and before/after values are visible.
- Use a compact event timeline plus a filterable table.
- Live monitor should distinguish ping reachability changes from scan-to-scan presence changes.
- MAC identity is preferred where known; IP fallback must be labeled as such.

### Network topology and infrastructure
- Topology is a spatial/relational view, not a decorative node cloud.
- Only verified edges are drawn as verified connections.
- Inferred/context/unverified relationships use separate lists or explicit visual encodings.
- Node selection opens a details panel with evidence source, timestamp, and confidence category.
- Router, gateway, AP, repeater/mesh, switch, controller and client roles need consistent icon semantics.
- Avoid force-directed motion or automatic layout changes that make comparisons difficult.

### Wi-Fi signal and spatial intelligence
- Signal percentage and RSSI (dBm) must be labeled as different measurements.
- Time-series axes show units and observation time.
- Nearby AP comparisons require a clear sort/filter and show staleness.
- Never translate RSSI into physical distance without validated calibration and uncertainty.
- Spatial estimates must be labeled experimental and show evidence/coverage limitations.

### Reports
- Start with a short executive summary: scope, period, data freshness, key findings.
- Separate confirmed facts from inferred observations.
- Use a report index with export actions (CSV/JSON initially; PDF only after reliable layout support).
- Every chart has a title, unit, period and plain-language takeaway.
- Every chart has an accessible table or downloadable data alternative.

## 6. Chart grammar

Choose a chart based on the question, not decoration:

- Time series: signal/RSSI or event counts over time; preserve gaps and show time range.
- Horizontal bars: category comparison such as device status or vendor counts.
- Stacked bars: only when components are meaningful and totals remain interpretable.
- Donut: only for a small number of mutually exclusive categories; always show values and a legend.
- Topology graph: relationships only, with evidence semantics.
- Tables: exact identifiers, detailed records, auditability and exports.

Rules:
- Always label units and time windows.
- Avoid 3D, decorative gauges, unexplained dual axes, and truncated misleading scales.
- Do not stack unrelated signals.
- Use consistent status colors and line styles across every page.
- Include a table or textual summary for important visual findings.
- Do not render an empty chart frame when data is absent; show a useful empty state and next step.

## 7. Interaction and content patterns

- Search and filters appear in the same order across similar pages.
- Filters show active state and a clear reset action.
- Destructive or broad-scope actions require explicit confirmation.
- Loading states explain what is being read or computed.
- Empty states explain why there is no data and the safest next action.
- Errors explain what failed, what was preserved, and what the user can do next.
- Dialogs preserve keyboard focus and have clear close/cancel behavior.
- Copy/export actions must be visible and predictable.
- Use Turkish as the primary product language; technical acronyms remain standard and are explained on first use.

## 8. Accessibility and responsive behavior

- Target WCAG 2.1 AA contrast: 4.5:1 for normal text and 3:1 for large text and essential non-text UI.
- Never use color alone for status or chart categories.
- Keyboard focus is visible and follows visual order.
- Controls have descriptive labels; icon-only controls require accessible names.
- Respect reduced-motion preferences.
- Layout must remain usable at common laptop widths and browser zoom. Tables may scroll horizontally where identifiers cannot safely wrap.
- Do not rely on hover as the only way to reveal evidence or actions.

## 9. Performance rules

- No unnecessary one-second refresh loops on pages that do not need them.
- Do not re-run network scans on navigation or ordinary reruns.
- Cache only deterministic local reads with a clear invalidation strategy.
- Limit initial table rows and provide pagination/filters for large datasets.
- Avoid plotting every raw row; aggregate by a documented interval when appropriate.
- Keep charts lazy or page-scoped where possible.
- Use explicit user actions for expensive analysis and report generation.
- Keep all data local; never add telemetry or external font/image dependencies.

## 10. Implementation phases and acceptance gates

1. Foundation: tokens, typography, navigation shell, consistent page headers. (Current PR)
2. Dashboard: operational briefing, useful empty states, source-aware KPIs.
3. Shared data components: filter bars, compact tables, detail panels, severity chips.
4. Events/live monitoring: common event grammar and drill-downs.
5. Topology/infrastructure: evidence-aware graph and device role visual language.
6. Wi-Fi/spatial pages: chart grammar, freshness and uncertainty communication.
7. Reports: executive summary, consistent exports and accessible alternatives.
8. Performance/accessibility audit: keyboard, contrast, viewport, render time, large datasets.

A phase is not “done” because the CSS looks plausible. It must pass automated tests, Windows compatibility checks, and a manual visual review at desktop and narrow widths. Visual perfection cannot be honestly certified from source code alone; final acceptance requires screenshots and real interaction testing in the running app.
