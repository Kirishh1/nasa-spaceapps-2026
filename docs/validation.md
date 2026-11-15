# Validation

## Independent references (NASA OPERA)
NISAR open-water maps are compared pixel by pixel with NASA JPL OPERA Dynamic Surface Water Extent products:
- **DSWx-HLS** (optical: Harmonized Landsat/Sentinel-2). A completely different sensor type. Used only on days at least 50% cloud-free.
- **DSWx-S1** (C-band radar: Sentinel-1). Classes: 0 not water, 1 open water, 3 inundated vegetation, 250/251 masked, 255 no data.

These are independent satellite products with their own errors, **not ground truth**.

## Results: case study, 18 Jun → 16 Oct 2026 (stored result `sylhet_monsoon`)

| NISAR date | Reference | Offset | Precision | Recall | F1 | IoU | κ |
|---|---|---|---|---|---|---|---|
| 16 Oct | DSWx-HLS, Landsat-9, 17 Oct (100% clear) | 1 d | 0.83 | 0.97 | **0.90** | **0.81** | 0.74 |
| 16 Oct | DSWx-S1, Sentinel-1 orbit 114, 17 Oct | 1 d | 0.59 | 1.00 | 0.74 | 0.59 | 0.47 |
| 18 Jun | DSWx-S1, Sentinel-1 orbit 41, 19 Jun | 1 d | 0.58 | 0.99 | 0.73 | 0.57 | 0.36 |

**Additional check** (stored result `sylhet_demo`): 28 Oct NISAR vs DSWx-HLS (Sentinel-2B, 27 Oct, 82% clear): F1 0.85, IoU 0.74.

**Threshold sensitivity.** Against the 17 Oct optical map, F1 stays between 0.84 and 0.91 for thresholds from −15 to −9 dB (±3 dB around the automatic −12.0 dB).

**Change agreement.** The "water receded" class agrees with the change between the two DSWx-S1 maps with F1 0.26.
- This is weak.
- The two reference dates come from different Sentinel-1 orbits.
- DSWx-S1 itself swings between 22% and 45% basin water from one orbit to the next within days (see the season chart), so it is a noisy reference for change.

## Interpretation
- NISAR's water maps agree closely with the optical reference and contain the C-band reference almost completely (recall ≥ 0.99).
- NISAR maps more water than DSWx-S1. Optical, a third sensor, sides with NISAR.
- That is consistent with C-band underestimating shallow, vegetated or wind-roughened water. It is not proof.

## Software tests (`pytest backend/tests`, 29 tests)
- dB conversion, the sign of ΔB, classification and nodata handling
- speckle filters
- inundation rules
- statistics against the raster transform
- incompatible-pair rejection
- the API flow
- strict JSON output
- multilooking
- the noise reference
- confusion-matrix metrics with known values
- Otsu thresholding, including the separability fallback on a scene with no water
- water-change classes
- an end-to-end validation run against a synthetic DSWx-style reference
- blob storage against a fake SDK

All test rasters are synthetic and are never shown in the app.

## What would strengthen it
- Field observations or Bangladesh FFWC water-level records for the same dates.
- High-resolution optical flood maps.
- A full NISAR time series (every 12 days, Jun–Nov) validated against every clear DSWx-HLS date.
