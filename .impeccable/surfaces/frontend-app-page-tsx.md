---
version: 1
slug: "frontend-app-page-tsx"
primary_target: "frontend/app/page.tsx"
related_targets: []
---

# SAR-Pulse workspace (frontend/app/page.tsx)

Mode: Operate. Users: Space Apps judges (5-minute demo, projector) and SAR/hydrology researchers. Task: pick area → pick two real dated observations → run → inspect change, metadata, uncertainty. Build path: code-led (no image generation available).

## Direction contract
Seed: 41dce4e1 (assigned).

THESIS: The interpreter's light table. Two dated radar frames are laid on a backlit table and compared with a loupe and a china marker. This replaces the generic dark-dashboard-with-cards default; there are no stat cards and no neon.

OWN-WORLD:
- Graphite table housing (#1d1f21–#2a2c2f). The map sits as an opal-lit transparency with aerial-film fiducial marks at its corners and graticule ticks on its edges.
- Metadata is printed like a film-edge data strip: tabular figures, frame/date/track/pol.
- Layers are acetate plies, stacked in order.
- China-marker yellow (#f3c53a) is the only accent. Change classes are blue #2f7fd8 and orange #e8803a, always labeled.
- One workhorse grotesque, with mono only for measured data.

STORY: Read the frames (dates, sensor, geometry) → see what changed → see how sure to be.

FIRST VIEWPORT: The map fills the table. A left tool tray holds the decision chain (Area → Frames → Run). The right side is the interpretation sheet. Film data strips run along the map's top and bottom edges.

SIGNATURE: Two-frame swipe. A dividing loupe edge splits the earlier and later frames, and each side is captioned by its own data strip.

RAISES:
- State is shown by line form as well as hue: solid = live, dashed = pending, struck = disabled.
- Incompatible pairs stay visible, stamped with their reason.
- The decision chain shows the next decision first.
- Fiducials and graticule ticks register the map.
