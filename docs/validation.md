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

## Software tests (`pytest backend/tests`, 31 tests)
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
- blob storage against a fake SDK, including the listing used to check files exist
- int16 dB layer round-trip (0.01 dB precision)

All test rasters are synthetic and are never shown in the app.

## What would strengthen it
- Field observations or Bangladesh FFWC water-level records for the same dates.
- High-resolution optical flood maps.
- A full NISAR time series (every 12 days, Jun–Nov) validated against every clear DSWx-HLS date.

## Additional evidence (added after the first validation round)

### NASA/CNES SWOT lake water levels: a different instrument and quantity
- **Product:** SWOT `SWOT_L2_HR_LakeSP_prior_D` lakes in the basin. Kept: quality good or suspect, not partial, seen on ≥ 60% of a pass's dates.
- **Pairing:** each lake's water-surface elevation is compared between the SWOT dates closest (within ±7 days) to the two NISAR passes.

| SWOT pass | Dates | Lakes | Median change | IQR | Lakes that fell |
|---|---|---|---|---|---|
| 467 | 15 Jun → 18 Oct | 11 | **−1.38 m** | −1.52 to −1.28 m | 100% |
| 536 | 17 Jun → 20 Oct | 9 | **−1.25 m** | −1.50 to −1.11 m | 100% |

Median measurement uncertainty is 3–5 cm.

**Per-lake area, NISAR vs SWOT** (20 lakes; Prior Lake Database outlines widened by 250 m, chosen by matching earlier-date total area: NISAR 36.5 km², SWOT 33.1 km²):
- Earlier-date area: r = 0.85.
- Area change: r = 0.59. Rank ρ = 0.27, so a few large lakes dominate r.
- Same direction of change for 90% of lakes.

### Change pattern
- **Same-orbit pairs.** Water change is compared against same-orbit DSWx-S1 pairs, removing orbit-geometry differences: orbits 41, 77, 114 and 150, each within 7 days of both NISAR dates.
  - Net change has the same sign for all four.
  - "Water receded" F1 is 0.09–0.25 at the pixel level.
  - The correlation of water-fraction change in 100 m cells is r −0.08 to 0.18.
- **Reference ceiling.** The C-band reference agrees with itself across orbits (same dates) only at F1 0.37–0.60. So it cannot validate the change pattern.
- **Error-propagation estimate.** Adding independent errors at NISAR's measured per-date rates (vs optical: false-positive rate 0.25, false-negative rate 0.03) gives an expected change F1 of about 0.68. NISAR's change pattern therefore genuinely differs from C-band's, beyond the reference's noise.
- **Optical pair.** No cloud-free optical pair brackets the monsoon. The one optical pair (17 Oct → 27 Oct) spans only 12 days of very small change, so it cannot discriminate.

**Conclusion:**
- **Water extent on each date** is validated (optical F1 0.85–0.90).
- **That the wetlands drained** is confirmed independently by SWOT water levels and per-lake areas.
- **Where exactly, pixel by pixel,** the water receded is not independently confirmed.

### Radiometric stability
- **Method:** median ΔB over ESA WorldCover built-up and tree-cover pixels that are land on both dates.
- **Case study:** 0.00 dB (IQR −0.76 to +0.81 dB), so the frames are consistent.
- **Mixed product versions:** the 16 Oct → 9 Nov pair (1.0.11 / 1.0.20) shows −0.72 dB. That exceeds the 0.5 dB tolerance and is flagged in the app.
