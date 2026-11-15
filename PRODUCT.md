# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
Next.js (App Router) + React + TypeScript + Tailwind CSS + MapLibre GL JS frontend; Python FastAPI backend (NumPy, rasterio/GDAL, h5py, rio-tiler). Runs locally for demos.

## Users
- NASA Space Apps judges evaluating a live demo in a few minutes, on a laptop or projector.
- Earth scientists / hydrologists exploring real NISAR backscatter change and judging whether the interpretation is credible.

## Product Purpose
SAR-Pulse is a research tool, not an imagery viewer. A user picks a study area and two real NISAR observations, runs a temporal change analysis, and can see where backscatter changed, what data and method produced the result, and how much to trust it. Success: a real study area investigated end to end, with every number traceable to processing.

## Positioning
It processes real NISAR L2 GCOV data (L-band) rather than simulated imagery. It also exposes metadata, compatibility checks, thresholds and uncertainty next to the result. It is designed for multi-wavelength comparison with RCM C-band once compatible data exists.

## Operating Context
- The demo study area is the Sylhet Haor Basin in Bangladesh, using NISAR track 69 ascending, frame 14, from 2026-10-28 to 2026-11-09.
- Data is discovered through NASA CMR and downloaded with an Earthdata login.
- Reference context comes from JRC Global Surface Water, ESA WorldCover and GPM IMERG.

## Capabilities and Constraints
- Change map: ΔB = B_later − B_earlier in dB, classified as significant decrease / significant increase / limited change / no data.
- Results are reported as "potential inundation-related change", never "confirmed flood".
- Incompatible observation pairs are rejected with stated reasons.
- RCM comparison is not available: no RCM data has been ingested. The UI must say so honestly.
- GPM is shown only when it was actually retrieved.

## Brand Commitments
The name is SAR-Pulse. The spec asks for a "professional satellite intelligence platform rather than a generic dashboard." No logo or palette is committed.

## Evidence on Hand
- Real NISAR GCOV granules are listed in data/reference/observations.json.
- Statistics are produced only by the backend.
- There are no testimonials, validation campaigns or ground truth. The UI must state that results are not independently validated.

## Product Principles
1. The map and the real data come first; chrome stays out of the way.
2. Every number on screen comes from processing. There are no placeholder statistics.
3. Uncertainty sits next to the result, not behind a link.
4. When data is unavailable or a pair is incompatible, the UI says why. It never hides the problem or fakes a result.
5. Readable by a judge in five minutes, defensible to a scientist in fifty.

## Accessibility & Inclusion
Must be legible on a projector: high contrast, never color alone for change classes (labels and legend text too), and keyboard-operable controls.
