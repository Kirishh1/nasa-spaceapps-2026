---
name: SAR-Pulse
description: The interpreter's light table for real NISAR backscatter change.
colors:
  housing-0: "#161819"
  housing-1: "#1d1f21"
  housing-2: "#25282b"
  housing-3: "#2f3236"
  rule: "#3a3e43"
  rule-soft: "#2c2f33"
  ink: "#e8e6e1"
  ink-2: "#b9b7b1"
  ink-3: "#8e8c86"
  opal: "#d9dcd6"
  marker: "#f3c53a"
  marker-ink: "#1d1a10"
  decrease: "#2f7fd8"
  increase: "#e8803a"
  limited: "#6b7280"
  water: "#22d3ee"
  vegetated: "#a3e635"
  error: "#ef6a5b"
  warn: "#e9b949"
typography:
  wordmark:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    letterSpacing: "-0.025em"
    fontVariation: "\"wdth\" 118"
  headline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 600
    lineHeight: 1.25
    fontVariation: "\"wdth\" 104"
  title:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    fontVariation: "\"wdth\" 108"
  reading:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.625
  body:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.625
  note:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "11.5px"
    fontWeight: 400
    lineHeight: 1.375
  label:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    letterSpacing: "0.04em"
    fontVariation: "\"wdth\" 112"
  num:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    letterSpacing: "0"
    fontFeature: "\"tnum\""
  strip:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "10.5px"
    fontWeight: 400
    letterSpacing: "0.06em"
    fontFeature: "\"tnum\""
rounded:
  hair: "1px"
  stamp: "2px"
  control: "3px"
  chrome: "4px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "6px"
  md: "10px"
  lg: "16px"
  xl: "20px"
  step: "24px"
components:
  button-run:
    backgroundColor: "{colors.marker}"
    textColor: "{colors.marker-ink}"
    typography: "{typography.title}"
    rounded: "{rounded.control}"
    padding: "10px 0"
  button-run-disabled:
    backgroundColor: "{colors.housing-3}"
    textColor: "{colors.ink-3}"
  button-tool:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.control}"
    padding: "6px 10px"
  button-tool-active:
    backgroundColor: "{colors.marker}"
    textColor: "{colors.marker-ink}"
  segment-on:
    backgroundColor: "{colors.housing-3}"
    textColor: "{colors.ink}"
    rounded: "{rounded.stamp}"
    padding: "4px 10px"
  segment-off:
    backgroundColor: "transparent"
    textColor: "{colors.ink-3}"
  input-field:
    backgroundColor: "{colors.housing-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "6px 10px"
  frame-row:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "6px 10px"
  frame-row-selected:
    backgroundColor: "rgba(243, 197, 58, 0.1)"
    textColor: "{colors.marker}"
  stamp:
    backgroundColor: "transparent"
    textColor: "{colors.ink-3}"
    rounded: "{rounded.stamp}"
    padding: "0 4px"
  step-marker:
    backgroundColor: "{colors.marker}"
    textColor: "{colors.marker-ink}"
    rounded: "{rounded.full}"
    size: "18px"
---

# Design System: SAR-Pulse

## Overview

**Creative North Star: "The Interpreter's Light Table"**

Two dated radar frames are laid on a backlit table and compared with a loupe and a china marker. The housing is graphite, nearly black and faintly cool; the map is the lit transparency at its centre, registered by aerial-film fiducials at its corners and graticule ticks on its edges. Everything around the transparency is the table's furniture: a tool tray on the left that walks the decision chain, an interpretation sheet on the right that reads the result back in sentences, and film-edge data strips printed along the map's top and bottom.

The system is dense and quiet. Chrome is hairline rules and graphite steps, not cards. There is exactly one hand-drawn colour, china-marker yellow, and it marks what the interpreter has chosen or must do next. Data colour belongs to the data: decrease blue and increase orange always travel with their words. State is carried by line form as well as hue, so the interface reads on a washed-out projector and for colour-blind viewers.

Measured values are printed, not designed: monospace with tabular figures for every number, and a tracked uppercase mono strip for frame metadata. One variable-width grotesque (Archivo) does everything else, using its width axis rather than extra weights for hierarchy.

**Key Characteristics:**
- Graphite housing in four tonal steps; no cards, no stat tiles.
- One accent (china marker) for selection, next action and focus.
- Solid / dashed / struck line form encodes live / pending / disabled.
- Every number in tabular mono; frame metadata in film-edge strips.
- Map registered by fiducials and graticule ticks, framed by a soft backlight glow.

## Colors

A graphite-and-opal neutral field with a single china-marker accent and a small, strictly labeled set of data inks.

### Primary
- **China Marker Yellow** (`marker`): the only accent. Selected frames, the done/next step markers, the Run button, active tools, the swipe loupe, the selected study-area outline, threshold lines on charts, the later-frame caption, focus outlines and text selection. Text on a marker fill is always **Marker Ink** (`marker-ink`), never white.

### Neutral
- **Housing Black** (`housing-0`): page background, the table itself.
- **Graphite** (`housing-1`): the transparency's mat ring and popup ground.
- **Graphite Raised** (`housing-2`): input fields, row hover.
- **Graphite Pressed** (`housing-3`): the "on" segment of segmented controls; disabled primary action fill.
- **Rule** (`rule`): hairline borders between tray, table and sheet; control outlines; section dividers.
- **Soft Rule** (`rule-soft`): dividers inside lists (layer plies, table rows) and dashed outlines of unusable rows.
- **Table Ink** (`ink`): primary text and values.
- **Pencil** (`ink-2`): secondary prose, data strips, inactive controls.
- **Graphite Ink** (`ink-3`): labels, hints, notes, pending/disabled outlines.
- **Opal Light** (`opal`): the backlight. Appears only as translucent glow and inner rim around the map transparency.

### Data inks
- **Decrease Blue** (`decrease`): significant backscatter decrease (ΔB below −threshold).
- **Increase Orange** (`increase`): significant backscatter increase.
- **Limited Grey** (`limited`): limited change.
- **Water Cyan** (`water`): open-water emergence candidates.
- **Vegetation Green** (`vegetated`): flooded-vegetation candidates.

### Status
- **Signal Red** (`error`): incompatible pairs and failed runs; used as text, a 60% border and a 10% wash.
- **Caution Amber** (`warn`): compatibility warnings and reference caveats, text only.

### Named Rules
**The One Marker Rule.** China-marker yellow is the only accent and means "chosen, next, or focused". It never decorates and never encodes data.

**The Labeled Ink Rule.** A data ink never appears without its words: a legend label, a row label, or the reading sentence that names the class. Colour is never the only carrier.

**The Data Stays On The Film Rule.** Data inks (decrease, increase, limited, water, vegetated) describe pixels. They are not used for UI status, buttons or decoration.

## Typography

**Display / Body Font:** Archivo, variable width axis (with system-ui, sans-serif)
**Mono Font:** JetBrains Mono (with ui-monospace, monospace)

**Character:** A single workhorse grotesque that gains authority by widening (wdth 104 to 118) rather than by getting bolder; a plain mono that prints measured data like a film rebate.

### Hierarchy
- **Wordmark** (700, 16px, wdth 118, tight tracking): SAR-Pulse in the header only.
- **Headline** (600, 19px, 1.25, wdth 104): the study-area name heading the interpretation sheet.
- **Title** (600, 13px, wdth 108): tool-tray step titles and sheet section titles. The Run button uses the same size at 700, wdth 110.
- **Reading** (400, 14px, 1.625): the interpretation sentence that states the result in words.
- **Body** (400, 12.5-13px, 1.625): descriptions, control text, select values.
- **Note** (400, 11-11.5px, 1.375): hints under controls, caveats, method notes.
- **Label** (600, 11px, 0.04em, wdth 112, sentence case): form and legend labels in Graphite Ink.
- **Num** (mono, tabular, 12-15px): every computed or measured value. A selected frame's date is 13px; a frame column date 15px.
- **Strip** (mono, 10.5px, 0.06em, uppercase, tabular): film-edge data strips, frame metadata, graticule coordinates, analysis IDs.

### Named Rules
**The Printed Number Rule.** Every number that came from processing is set in tabular mono. Prose words around it stay in Archivo.

**The Width Not Weight Rule.** Hierarchy steps by width axis and size; weights stop at 400, 600 and 700.

## Layout

A full-height three-column table on desktop (lg, 1024px and up): a 300px tool tray, the flexible light table, and a 372px interpretation sheet, separated by single hairline rules. The tray and sheet scroll independently; the page does not. A slim header (10px vertical padding) carries the wordmark, a one-line description and the backend status.

Below lg the columns stack with the map first (64vh, minimum 420px), then the tray, then the sheet.

Rhythm: 24px between tool-tray steps; sections on the sheet open with a rule and 16px above, 20px below; 10px between a title and its content; controls pad 6px by 10px; data rows sit 3px apart. The map column has 12px side padding with the film strips (28px tall) directly above and below the transparency.

**The Map Fills The Table Rule.** The transparency takes all remaining space; nothing floats over it except registration marks, the loupe and native map controls.

## Elevation & Depth

Flat by default. Depth comes from graphite tonal steps and hairline rules, not shadows. The one structural depth effect is the backlight: the map transparency sits in a 1px black edge, a 6px graphite mat, a diffuse opal glow and a faint opal inner rim, so it reads as lit from below. Soft blurred shadows appear only on things that sit on top of the film (the loupe and native map controls and popups).

### Shadow Vocabulary
- **Backlight** (`box-shadow: 0 0 0 1px #0b0c0d, 0 0 0 6px var(--housing-1), 0 0 48px 6px rgba(217,220,214,0.08), inset 0 0 0 1px rgba(217,220,214,0.18)`): the map transparency only.
- **Loupe lift** (`box-shadow: 0 4px 14px rgba(0,0,0,0.55)`): the swipe handle; the divider line gets `0 0 10px rgba(0,0,0,0.6)`.
- **Map chrome** (`box-shadow: 0 2px 8px rgba(0,0,0,0.35)`): zoom controls.
- **Popup** (`box-shadow: 0 8px 24px rgba(0,0,0,0.5)`): the pixel-reading popup.

### Named Rules
**The One Light Source Rule.** Only the transparency glows. Panels, sections and controls never get a shadow.

## Shapes

Nearly square. Controls take a 3px corner, inner segments and stamps 2px, swatches and ramps 1px, native map chrome 4px. Circles are reserved for step markers, the swipe loupe and the status dot. Borders are 1px hairlines; 1.5-2px appears only on the "next" step marker and the loupe ring.

Line form carries state and is part of the shape vocabulary: a **solid** outline is live or selected, a **dashed** outline is pending, unusable or unavailable, and a **struck** label is disabled. The no-data class uses a 135deg hatch of rule-coloured lines.

**The Line Form Rule.** Every stateful element changes its line (solid, dashed, struck) as well as its colour. Hue alone never signals state.

## Components

### Buttons
- **Run analysis (primary):** full-width marker fill, marker-ink text, 13px/700 wdth 110, 3px corner, 10px vertical padding. Disabled: graphite-pressed fill with graphite-ink text. A spinning loader icon accompanies "Processing frames…".
- **Tool button:** transparent with a rule outline and pencil text; hover lifts outline to graphite ink and text to table ink. Active (e.g. drawing): marker fill, marker-ink text.
- **Segmented control:** a rule-outlined 3px group with 2px padding; the on segment is graphite-pressed with table ink, off segments graphite ink. A disabled segment is struck through at 60% opacity.
- **Focus:** a 2px marker outline offset 2px on every focusable element.

### Chips (sensor selector)
- **Style:** three equal 3px-corner outlined buttons, 12px/600.
- **State:** selected is a marker outline with a 10% marker wash and marker text; unavailable is a dashed soft-rule outline with struck graphite-ink text and its reason shown below.

### Inputs / Fields
- **Style:** graphite-raised fill, rule outline, 3px corner, 13px table ink, graphite-ink placeholder.
- **Range sliders:** native, tinted with the marker; the current value is printed in mono beside the label.
- **Focus:** the global marker outline.

### Frame row (signature)
A selectable observation in the decision chain: date in 13px mono, then a strip with track, direction, frame and polarizations.
- **Live:** rule outline; hover raises to graphite-raised.
- **Selected:** marker outline, 10% marker wash, marker date.
- **Unusable:** dashed soft-rule outline, struck date, and an "Unusable" stamp followed by the reason. Incompatible rows stay visible.

### Stamp
A small uppercase bordered tag that states why something is absent or unproven: "Unusable", "Unavailable" (1px graphite-ink outline at 60%, graphite-ink text, 600), and "Not validated" (marker fill, marker-ink text, 700). 2px corner, 4px horizontal padding, always followed by its reason in plain text.

### Decision chain step
Each tray step is headed by an 18px circle numbered in mono: **done** is a solid marker disc, **next** a 1.5px marker ring, **waiting** a dashed graphite-ink ring with a graphite-ink title.

### Acetate plies (layer stack)
An ordered list, top sheet first, divided by soft rules. Each ply has a 24px visibility toggle (solid marker outline when shown, dashed graphite-ink when hidden), a title, up/down reorder arrows, and when shown an opacity slider with its percentage in mono, a colour ramp with mono end values and, for ΔB, the words Decrease and Increase under the ends, or a labeled swatch legend.

### Film-edge data strip
A 28px strip above and below the transparency in the Strip style: earlier frame on top, later frame below in marker. In swipe mode the top strip splits at the loupe so each side is captioned by its own frame.

### Light table map
The transparency with the Backlight treatment and a 2px corner; four fiducial marks (a 22px circle-and-cross in 75% table ink) at the corners; graticule ticks and strip-style coordinates on the top and right edges with a dark text shadow; the selected study area outlined in solid marker, a drawn sub-area in dashed marker over an 8% marker fill.

### Swipe loupe
A 2px marker divider with a 34px graphite disc ringed in 2px marker, holding a marker double-chevron. Draggable and keyboard-operable with the arrow keys.

### Interpretation sheet
Opens with the headline and a reading sentence that names each class in its own ink, then rule-separated sections of key/value rows: graphite-ink key on the left, right-aligned tabular value with a graphite-ink unit. Unavailable sections use a dashed rule-outlined box with a stamp, never an empty chart.

## Do's and Don'ts

### Do:
- **Do** use china-marker yellow only for selection, the next action, focus and the later frame.
- **Do** pair every data ink with its class name in text, in legends, rows and sentences.
- **Do** change line form with state: solid for live, dashed for pending or unavailable, struck for disabled.
- **Do** set every processed number in tabular mono, with units in graphite ink.
- **Do** keep incompatible frames visible, stamped and followed by their reason.
- **Do** show unavailable data as a dashed box with an "Unavailable" stamp and the reason.
- **Do** separate regions with 1px rules and graphite tonal steps.

### Don't:
- **Don't** introduce a second accent or use marker yellow decoratively.
- **Don't** use data inks for UI status, buttons or decoration.
- **Don't** put shadows on panels, sections or controls; only the transparency glows and only overlays on the film lift.
- **Don't** add stat cards or tiles; results are rows and sentences on the sheet.
- **Don't** signal state by colour alone.
- **Don't** round corners past 3px on controls or 4px on map chrome.
