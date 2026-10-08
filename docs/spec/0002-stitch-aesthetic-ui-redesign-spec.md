<!-- triage-label: ready-for-agent -->
# Specification: Obsidian Kinetic Aesthetic UI Redesign (Google Stitch)

## Problem Statement

The existing InsightClue frontend dashboard uses a functional, generic dark-mode interface with basic styling. While it serves core investigative workflows, it lacks the visual authority, micro-metric density, high-contrast laser focus, and bespoke luxury aesthetic demanded by modern FinTech analysts, data detectives, and incident commanders. Users need a high-velocity, immersive cockpit (Obsidian Kinetic) that pairs ultra-dark obsidian substrates (`#0D0E11`) with high-voltage electric chartreuse highlights (`#CCFF00`), interactive match dials, high-density telemetry tiles, and responsive multi-agent squad visualization.

## Solution

Re-architect and modernize the InsightClue frontend interface according to the **Obsidian Kinetic** design system extracted from Google Stitch:
1. **Typography & Foundations**: Introduce Plus Jakarta Sans for high-impact display/metric headers paired with JetBrains Mono for telemetry codes, statistical deviations ($Z \le -2.5\sigma$), latency metrics, and SQL logs.
2. **Color & Elevation Architecture**: Implement deep obsidian canvas substrates (`#0D0E11`, `#131418`, `#1C1E23`), crystalline glassmorphic floating panels with hairline borders (`rgba(255, 255, 255, 0.08)`), and electric chartreuse signal accents (`#CCFF00`) for visual anchors, primary triggers, and radial match rings.
3. **Cockpit Layout & Telemetry Deck**: Construct an adaptable 12-column console layout featuring a persistent navigation rail/header, dynamic dataset switcher, quick-filter segmented capsule pills, dual-card telemetry metric hubs (Spend Variance, Failure Spikes, Dispute Volumes), and interactive anomaly selection feeds.
4. **Interactive Multi-Agent Detective Hub**: Redesign the 4-stage investigation ribbon, real-time Server-Sent Events (SSE) investigation console, hypothesis deliberation log, AST-validated SQL query viewer, and markdown RCA report synthesizer with high-contrast neo-brutalist cards and copyable evidence chips.
5. **Universal Dynamic Dataset Integration**: Seamlessly connect the redesigned UI with the multi-format upload and partition switching capabilities (`DynamicIngestionEngine` & `/api/datasets`).

## User Stories

1. As an incident commander, I want an obsidian-black, high-contrast dashboard, so that I can monitor telemetry and anomalies for hours without visual fatigue.
2. As a FinTech analyst, I want electric chartreuse visual signals on critical anomalous metrics, so that severe anomalies instantly draw my attention.
3. As an investigator, I want circular match dials with dynamic SVG progress strokes, so that I can immediately assess confidence scores for flagged incidents.
4. As a user, I want segmented capsule filter switchers (e.g., Time Range, Gateways, Anomaly Severity), so that I can slice anomaly feeds with single-click precision.
5. As an analyst, I want high-density metric summary tiles displaying current values, historical baselines, and delta percentages, so that I can evaluate the scale of an incident at a glance.
6. As an investigator, I want an interactive anomaly feed with status beads and severity tags, so that I can review and select incidents for multi-agent root cause analysis.
7. As a user, I want a 4-step guided investigation ribbon with animated state transitions, so that I can track investigation progress from anomaly detection to report synthesis.
8. As a user watching an AI investigation, I want live Server-Sent Events (SSE) streaming updates displayed in agent message cards, so that I can observe the Lead Detective, SQL Analyst, and Vector Support agents collaborating in real time.
9. As a data engineer, I want the SQL Analyst agent's executed queries to render with syntax highlighting and copy-to-clipboard buttons, so that I can audit and verify the quantitative proof.
10. As a customer support manager, I want the Vector Support agent's retrieved complaint citations to render with similarity badges and verbatim quotes, so that I can verify customer sentiment trends.
11. As an executive, I want synthesized Root Cause Analysis reports rendered in crisp Markdown with actionable recommendations, so that I can distribute findings immediately to engineering and operations teams.
12. As a user, I want a dataset selector dropdown and modal in the header, so that I can switch between pre-seeded telemetry and newly ingested custom datasets.
13. As a user, I want a drag-and-drop dataset upload modal with automatic schema preview, so that I can ingest CSV, JSON, SQLite, or Parquet datasets without leaving the cockpit.
14. As an operator running the app without Docker, I want a non-intrusive offline diagnostic banner with a copyable `docker-compose up -d` command, so that I know how to restore database connectivity without confusion.
15. As a mobile or tablet user, I want the cockpit to adapt gracefully to 4-column and 8-column responsive viewports, so that I can monitor active incidents on any device.

## Implementation Decisions

1. **Vanilla CSS & Design Token System**:
   - Express all tokens (Obsidian Kinetic color palette, Plus Jakarta Sans / JetBrains Mono typography, border radii, hairline border variables) as CSS Custom Properties (`--bg-base`, `--surface-panel`, `--accent-lime`, `--border-subtle`, etc.) in `style.css`.
   - Maintain clean, dependency-free vanilla CSS architecture with modular utility classes and glassmorphic card patterns.

2. **Semantic Component Hierarchy**:
   - **Header / Navigation Bar**: Brand identity with live system status badge, dataset partition switcher, and primary action buttons (Scan Detect, Upload Dataset, Swagger API).
   - **Metrics & Topography Deck**: Key telemetry tiles (Failure Rate %, Chargeback Delta, Latency Spikes, Active Anomalies) with mini sparklines and delta variance badges.
   - **Incident Investigation Workspace (Split Pane / Grid)**:
     - Left pane: Anomaly Feed & Filter Rails with radial match gauges and severity badges.
     - Right pane: Active Incident Inspector & Multi-Agent Investigation Cockpit with real-time SSE event timeline, SQL sandbox output, RAG citations, and synthesized Markdown report.
   - **Universal Dataset Ingestion Drawer / Modal**: File drag-and-drop zone, schema inference preview table, column mapping confirm button, and progress indicator.

3. **Client-Side Reactive Controller**:
   - Refactor `app.js` into modular state controllers (`TelemetryController`, `AnomalyFeedController`, `InvestigationStreamController`, `DatasetUploadController`).
   - Preserve all existing backend API contract hooks:
     - `GET /api/health`
     - `GET /api/datasets` & `POST /api/datasets/upload` & `POST /api/datasets/confirm-ingestion`
     - `POST /api/anomalies/detect` & `GET /api/anomalies`
     - `POST /api/investigations/start` & `GET /api/investigations/stream/{id}`
     - `GET /api/metrics/summary` & `GET /api/metrics/telemetry`

4. **Micro-Interactions & Transitions**:
   - Add hover states with subtle neon glow (`box-shadow: 0 0 20px rgba(204, 255, 0, 0.25)`).
   - Radial SVG progress animation on anomaly selection.
   - Smooth badge pulse animations for active streaming agents.

## Testing Decisions

- **Good Test Philosophy**: Test external behavior and interface contract correctness, ensuring UI controllers properly dispatch API requests, handle SSE streams, render Markdown, and update DOM components under nominal and error conditions.
- **Modules Tested**:
  - `src/static/app.js` and `src/static/index.html` via browser interaction subagents and frontend contract validation tests.
  - Integration with FastAPI backend endpoints (`tests/test_api_endpoints.py`).
- **Prior Art**: Existing backend test suite in `tests/` (`test_api_endpoints.py`, `test_dynamic_ingestion.py`, `test_telemetry_store.py`).

## Out of Scope

- Modifying backend LangGraph agent graph definitions or database schemas (UI only connects to existing API seams).
- Heavy external frontend framework migrations (remains clean, fast vanilla JS/HTML/CSS to ensure instant loading without node build steps).

## Further Notes

- Reference design files located in `stitch_insightclue_aesthetic_ui_redesign/`:
  - `DESIGN.md`: Full design tokens, elevation scale, typography, and component specifications.
  - `code.html`: Visual markup and structural template for all cards, dials, and controls.
  - `screen.png`: Visual design render.
