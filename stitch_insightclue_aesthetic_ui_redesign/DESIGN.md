---
name: Obsidian Kinetic
colors:
  surface: '#121316'
  surface-dim: '#121316'
  surface-bright: '#38393c'
  surface-container-lowest: '#0d0e11'
  surface-container-low: '#1b1b1f'
  surface-container: '#1f1f23'
  surface-container-high: '#292a2d'
  surface-container-highest: '#343538'
  on-surface: '#e3e2e6'
  on-surface-variant: '#c4c9ac'
  inverse-surface: '#e3e2e6'
  inverse-on-surface: '#303034'
  outline: '#8e9379'
  outline-variant: '#444933'
  surface-tint: '#abd600'
  primary: '#ffffff'
  on-primary: '#283500'
  primary-container: '#c3f400'
  on-primary-container: '#556d00'
  inverse-primary: '#506600'
  secondary: '#c0d82f'
  on-secondary: '#2d3400'
  secondary-container: '#a5bb02'
  on-secondary-container: '#3e4800'
  tertiary: '#ffffff'
  on-tertiary: '#2d3038'
  tertiary-container: '#e0e2eb'
  on-tertiary-container: '#62646c'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#c3f400'
  primary-fixed-dim: '#abd600'
  on-primary-fixed: '#161e00'
  on-primary-fixed-variant: '#3c4d00'
  secondary-fixed: '#d6ef46'
  secondary-fixed-dim: '#bad228'
  on-secondary-fixed: '#191e00'
  on-secondary-fixed-variant: '#424b00'
  tertiary-fixed: '#e0e2eb'
  tertiary-fixed-dim: '#c4c6cf'
  on-tertiary-fixed: '#191c22'
  on-tertiary-fixed-variant: '#44474e'
  background: '#121316'
  on-background: '#e3e2e6'
  surface-variant: '#343538'
typography:
  display-hero:
    fontFamily: Plus Jakarta Sans
    fontSize: 56px
    fontWeight: '800'
    lineHeight: 64px
    letterSpacing: -0.04em
  display-hero-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '800'
    lineHeight: 44px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.03em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 28px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
  metric-display:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '800'
    lineHeight: 32px
    letterSpacing: -0.03em
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.06em
  label-caps:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.08em
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  gutter: 1.25rem
  gutter-desktop: 1.75rem
  margin: 1rem
  margin-tablet: 2rem
  margin-desktop: 3rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system targets high-performance operators, data-intensive fintech analysts, and modern product teams demanding precision, luxury, and hyper-legibility. The aesthetic merges **sleek luxury dark mode** with **technical neo-brutalism** and high-velocity telemetry: precision-engineered charcoal and deep obsidian surfaces, crystalline glass surfaces with crisp hairline borders, and high-voltage electric chartreuse accents.

### Core Visual Principles
- **Monochrome Foundation, Laser Precision:** Deep, warm-charcoal matte substrates punctuated by electric lime (`#CCFF00`). The accent color is deployed exclusively for telemetry highlights, critical conversion actions, confidence indicators, and primary visual anchors—never as decorative fill.
- **Micro-Metric Density:** Every component emphasizes quantifiable data: radial match rings, precision pill segmented switchers, delta variance chips, and high-frequency stat indicators.
- **Architectural Layering:** Surface hierarchy relies on strict tonal steps (`#0B0C0E` base to `#1E2025` elevated glass panels) bounded by razor-sharp `rgba(255, 255, 255, 0.08)` borders and soft ambient occlusion rather than diffuse drop shadows.
- **Zero Generic FinTech Tropes:** Complete exclusion of corporate royal blues, flat slate fills, and generic rounded material cards.

## Colors

The palette is engineered specifically for deep-contrast, non-fatiguing dark mode environments.

### Palette Architecture
- **Primary (`#CCFF00` - Electric Chartreuse):** The hero signal color. Used for high-emphasis callouts, primary action buttons, active tab fills, match rings, and sparkline vertex points.
- **Secondary (`#E6FF55` - High-Voltage Tint):** Used for hover states on primary elements, focused outer rings, and secondary glowing apexes.
- **Tertiary (`#25282F` - Muted Gunmetal):** Serves as elevated container backdrops, segmented filter tracks, pill badge backgrounds, and inactive radial track lines.
- **Neutral Canvas (`#0D0E11` - Obsidian Base):** The master viewport substrate. Layered with `#131418` (middle tier card) and `#1C1E23` (top tier interactive floating surface).
- **Text & Foreground:**
  - `High Contrast Text`: `#FFFFFF` (100% white for bold headlines and primary numeric values)
  - `Muted Telemetry Label`: `#8C909B` (crisp neutral for secondary metadata, dimensional units, and subtitles)
  - `Border Hairline`: `rgba(255, 255, 255, 0.08)` baseline, scaling to `rgba(204, 255, 0, 0.35)` on focused or active states.

## Typography

The typographic hierarchy pairs the sleek geometric architecture of **Plus Jakarta Sans** with the ultra-technical precision of **JetBrains Mono**.

- **Display & Headings:** Formed with tight letter tracking (`-0.03em` to `-0.04em`) and heavyweight cuts (700/800) to replicate the bespoke editorial presence of modern high-end studio dashboards.
- **Body & Paragraphs:** Retains high legibility at 14px and 16px with crisp glyph definition on charcoal backgrounds.
- **Telemetry & Labels:** JetBrains Mono is assigned to raw quantitative data points, statistical deviations (e.g., `Z <= -2.5σ`), currency ranges, status chips, and radial percentage tags to evoke high-precision laboratory engineering.

## Layout & Spacing

The layout is built upon an adaptable 12-column modular fluid grid, calibrated for multi-layered data consoles and executive dashboards.

### Responsive Breakpoints & Margin Architecture
- **Mobile (<768px):** 4 columns, `margin: 1rem`, `gutter: 1rem`. Dashboard cards collapse into a unified vertical stack; telemetry rings resize to 64px diameter. Segmented pill bars transform into horizontally scrollable rail carousels.
- **Tablet (768px - 1199px):** 8 columns, `margin-tablet: 2rem`, `gutter: 1.25rem`. Split views accommodate two metric panels abreast with sticky header telemetry chips.
- **Desktop (1200px+):** 12 columns, `margin-desktop: 3rem`, `gutter-desktop: 1.75rem`. Full layout with fixed persistent sidebar rail, expansive hero visual topography stage (spanning 7-8 columns), and modular floating metric tiles (spanning 4-5 columns).

### Spacing Density
Internal component padding adheres strictly to a compact, high-density rhythm (`space-sm` for inline capsule badges, `space-md` for input/selector cavities, and `space-lg` to `space-xl` for outer card chassis padding).

## Elevation & Depth

Visual depth is achieved through an interplay of physical surface shading, frosted backdrops, and selective neon illumination rather than standard multi-directional drop shadows.

### Elevation Hierarchy
1. **Canvas Substrate (Level 0):** Pure matte dark canvas (`#0D0E11`), non-reflective, setting infinite baseline depth.
2. **Structural Panels (Level 1):** Solid matte charcoal (`#131418`) with an ultra-thin 1px top border of `rgba(255, 255, 255, 0.07)` and side/bottom borders of `rgba(255, 255, 255, 0.03)`.
3. **Floating Glassmorphic Cards (Level 2):** Translucent frosted layer (`background: rgba(25, 27, 32, 0.72); backdrop-filter: blur(20px)`), edged with `1px solid rgba(255, 255, 255, 0.08)`. Subtle ambient occlusion shadow: `0 20px 40px -15px rgba(0, 0, 0, 0.6)`.
4. **Active Hero & Telemetry Elements (Level 3):** Radial dials, active pill capsules, and hero modals receive a localized inner rim light (`inset 0 1px 1px rgba(255, 255, 255, 0.15)`) coupled with an electric chartreuse volumetric aura (`box-shadow: 0 0 30px -8px rgba(204, 255, 0, 0.22)`).

## Shapes

The design system uses a pill-forward and capsule-dominant shape language balanced against broad, curved dashboard cards.

- **Capsules & Full Pills (`rounded-full` / 9999px):** Applied to all interactive controls—filter chips, status pills, segmented switcher items, search capsules, action buttons, and numeric badges.
- **Cards & Primary Modules (`rounded-xl` / 1.5rem to 2rem):** Outer card containers and analytical tiles feature expansive, softened corners that offset technical data tables and rigid grid charts.
- **Dial Apertures & Avatars (`rounded-full`):** Strict concentric circles for match rate dials, mini sparkline hubs, and telemetry indicators.

## Components

### Buttons
- **Primary Hero Button:** Pill-shaped (`rounded-full`), solid electric chartreuse fill (`#CCFF00`), jet black text (`#0D0E11`, `font-weight: 700`), subtle glow on hover (`0 0 24px rgba(204, 255, 0, 0.35)`).
- **Secondary Glass Button:** Translucent charcoal backdrop (`rgba(255, 255, 255, 0.05)`), hairline border (`rgba(255, 255, 255, 0.12)`), white text (`#FFFFFF`). On hover, border transitions to `#CCFF00` with text remaining white.
- **Ghost Action Icon Button:** Full circular glass container with centered SVG icon; active states produce an electric ring accent.

### Pill Badges & Match Rings
- **Radial Match Dial:** Concentric circular gauge with an SVG circle stroke. Background track in `rgba(255, 255, 255, 0.08)`, dynamic fill stroke in `#CCFF00` (`stroke-linecap: round`). Centered metric displays numerical value in bold white with a miniature percentage sign.
- **Status Chips:** Pill capsules featuring a pulsing 6px status bead (e.g., `#CCFF00` for active/optimal, `#FF4D4D` for critical risk) set against a charcoal container (`#1E2025`).

### Segmented Filter Switchers
- Housed within an elongated capsule track (`#141518`) with an inner 1px border. 
- Active selection is represented by a solid contrast pill (`#CCFF00` with dark text, or `#25282F` elevated pill with crisp white text and electric indicator tick).
- Filter items (e.g., '90-Day Slice', 'Corporate Card', 'Z <= -2.5σ') maintain single-line typography with mono-spaced symbols.

### Form Inputs & Capsule Search
- **Search Capsule:** High-radius pill shape (`rounded-full`) with charcoal fill (`#16171B`), interior hairline outline (`rgba(255, 255, 255, 0.08)`), left-aligned mono icon, and muted placeholder text (`#606470`). On focus, outline glows with a razor-thin `#CCFF00` stroke.

### Cards & Telemetry Tiles
- **Glass Console Tile:** Dual-layered composition featuring a frosted charcoal base, 1px perimeter border, top-right diagonal telemetry arrow icon, prominent numeric metric (`display-metric`), and sparkline or radial progress sub-element.
- **Topography/Mesh Hero Tile:** Houses the 3D green/chartreuse organic vector terrain or telemetry chart, shaded with ambient vignette gradients fading into `#0D0E11` at card perimeters.