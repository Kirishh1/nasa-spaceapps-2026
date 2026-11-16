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

## Software tests (`pytest backend/tests`, 41 tests)

**36 tests use synthetic rasters** (never shown in the app); **5 tests use the real stored Sylhet analysis**
(`backend/tests/test_real_data.py`, skipped automatically when `data/` is absent). The real-data tests recompute the
headline areas from the stored rasters, check both frames share track and product version, check the land-cover table's
counts add up and its intervals bracket the estimate, and check that single-date water-map scores are never mixed up with
change scores.

Synthetic-raster tests cover:
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
- the diagnostics: stable-vs-change split of agreement, kappa (0 for independent maps, 1 for identical), block-bootstrap interval, edge-buffer exclusion

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
- **Optical pair.** No cloud-free optical pair brackets the monsoon (June is cloud-covered). A later optical pair, 15 Sep → 17 Oct, is used for `sylhet_recession` (below).

**Conclusion:**
- **Water extent on each date** is validated (optical F1 0.85–0.90).
- **That the wetlands drained** is confirmed independently by SWOT water levels and per-lake areas.
- **Where exactly, pixel by pixel,** the water receded is not independently confirmed.

### Radiometric stability
- **Method:** median ΔB over ESA WorldCover built-up and tree-cover pixels that are land on both dates.
- **Case study:** 0.00 dB (IQR −0.76 to +0.81 dB), so the frames are consistent.
- **Mixed product versions:** the 16 Oct → 9 Nov pair (1.0.11 / 1.0.20) shows −0.72 dB. That exceeds the 0.5 dB tolerance and is flagged in the app.

## Full NISAR season and optical before/after (third round)
- **Per-date validation.** Seven NISAR frames (18 Jun, 10 Sep, 22 Sep, 4 Oct, 16 Oct, 28 Oct, 9 Nov) were each mapped with the same method and scored against the nearest optical map. Optical maps were matched within ±5 days, because clear days are rare in the monsoon; the offset is shown.

  | NISAR | Optical reference | F1 |
  |---|---|---|
  | 10 Sep | 15 Sep | 0.93 |
  | 22 Sep | 27 Sep | 0.95 |
  | 4 Oct | 4 Oct (same day) | 0.98 |
  | 16 Oct | 17 Oct | 0.90 |
  | 28 Oct | 27 Oct | 0.85 |
- **Optical before/after (10 Sep → 16 Oct, `sylhet_recession`).** The "water receded" map agrees with optical on the *direction* of change in 93% of the 500 m cells that changed. At 100 m that drops to 54%, and pixel F1 is 0.30.
- **No noise-based tuning.** Requiring a margin of 0.5–2 dB around the threshold before counting a change did not raise precision (≈ 0.35), so the method was left unchanged.
- **Interpretation:** NISAR identifies the right neighbourhoods, with fuzzier edges.
- **ICESat-2 ATL13 was checked as a second altimeter.** Only 28 Jul and 26 Aug had in-basin water returns, on different ground tracks, so no before/after comparison was possible.


## Diagnostics (final round): what the weak change score means

Computed by `scripts/validation_diagnostics.py` from the stored layers and reference files; served at
`GET /api/analysis/sylhet_monsoon/diagnostics` and shown in the app under *Validation & confidence → diagnostics*.
Nothing here changes a threshold or the analysis.

**Single-date water maps and change maps are scored separately.** The optical F1 values (0.85–0.98) describe the
water map on one date. Change agreement ("water receded") is a different, lower number and is never presented as
the accuracy of the change map.

### 1. The C-band change reference is weak itself
| Sentinel-1 date (orbit) | Optical date | S1 open water | Optical open water | F1 |
|---|---|---|---|---|
| 2026-09-13 (150) | 2026-09-15 | 47% | 71% | 0.79 |
| 2026-09-25 (150) | 2026-09-27 | 28% | 75% | 0.54 |
| 2026-10-05 (114) | 2026-10-04 | 53% | 73% | 0.84 |
| 2026-10-02 (77) | 2026-10-04 | 44% | 69% | 0.77 |
| 2026-10-17 (114) | 2026-10-17 | 40% | 59% | 0.81 |
| 2026-10-19 (150) | 2026-10-17 | 22% | 56% | 0.56 |

- DSWx-S1 finds 15–47 percentage points less water than optical on the same days, and how much less depends on the orbit.
- In June (no optical available) the four orbits, within 7 days, map 687–1356 km² of open water; NISAR maps 1684–1764 km² over the same pixels.
- Its change maps agree with each other across orbits only at F1 0.37–0.60.

### 2. Where the disagreement sits
| Orbit | Dates | Offset (d) | F1 "receded" | NISAR receded | S1 receded | F1 excl. 60 m of edges |
|---|---|---|---|---|---|---|
| 77 | 2026-06-21 → 2026-10-14 | 5 | 0.25 | 280 km² | 458 km² | 0.26 |
| 41 | 2026-06-19 → 2026-10-12 | 5 | 0.21 | 306 km² | 646 km² | 0.09 |
| 150 | 2026-06-14 → 2026-10-19 | 7 | 0.15 | 302 km² | 440 km² | 0.04 |
| 114 | 2026-06-12 → 2026-10-17 | 7 | 0.09 | 266 km² | 358 km² | 0.01 |

- **Not edge jitter:** excluding pixels near any water/land edge does not raise F1 (it falls for three orbits), so the disagreement lies inside water bodies.
- **Not mainly timing:** every pair is within 5–7 days; the two 5-day pairs (orbits 77, 41) score 0.25 and 0.21, the 7-day pairs 0.15 and 0.09, but orbit-to-orbit differences in the reference itself are larger than this.
- **Inundated vegetation class:** counting DSWx-S1 class 3 as water changes F1 by < 0.01, so the class definition is not the cause.
- **Error budget:** each date's water map differs from its reference over 753 km² (DSWX_S1 2026-06-19), 559 km² (DSWX_S1 2026-10-17), 279 km² (DSWX_HLS 2026-10-17), comparable to or larger than the 308 km² change. A change map is the difference of two maps, so its pixel pattern is much less certain than either map.
- **Conclusion:** the low score reflects (a) a reference that underestimates water and varies strongly by orbit, and (b) genuinely different behaviour of C-band over shallow vegetated water (section 3). It is not evidence that NISAR's per-date maps are wrong, but the exact pixel pattern of drainage remains unverified.

### 3. L-band vs C-band by land cover, examined
- **What is compared:** NISAR HH and Sentinel-1 VV (OPERA RTC-S1, orbit 41, 19 Jun → 12 Oct) backscatter-change classes (±3 dB), each from its own sensor, aggregated to 100 m cells (a change class wins a cell if it covers ≥ 30% of valid pixels). Cells need ≥ 50% valid pixels in both maps; nodata cells are excluded.
- **Land cover:** ESA WorldCover 2021 v200 (10 m) on the 20 m grid, dominant class per 100 m cell.
- **Agreement formula:** (both stable + both decrease + both increase) / compared cells. Kappa corrects for chance; the 95% interval is a bootstrap over 5 km blocks (≈ 99 blocks), which respects spatial autocorrelation.

| Land cover | Cells | Agreement (95% CI) | of which both stable | both changed alike | C-band only | κ |
|---|---|---|---|---|---|---|
| Tree cover | 20,480 | 90.8% (89.6–91.8) | 88.9% | 1.9% | 2.5% | 0.269 |
| Cropland | 118,942 | 47.2% (43.9–50.6) | 18.9% | 28.3% | 26.9% | 0.195 |
| Permanent water | 15,621 | 31.5% (26.9–36.8) | 20.5% | 11.0% | 56.6% | 0.052 |
| Herbaceous wetland | 66,628 | 32.5% (27.4–38.3) | 16.2% | 16.3% | 62.1% | 0.046 |

- **Tree cover's 91% is mostly agreement that nothing changed** (88.9% both stable, 1.9% both changed; κ 0.269). Across cell sizes (100/200 m) and aggregation rules (20/30/50%) it ranges 75.5–98.6%, so it is *not* a robust headline.
- **The herbaceous-wetland result is robust:** agreement 31.4–34.1% across those variants and 32.5–34.0% for ΔB thresholds of 2/3/4 dB, with C-band-only change on 60.6–64.0% of cells and κ ≈ 0.03–0.06 (near chance).
- **Across study areas** (featured pair of each; C-band pair from the nearest same-orbit Sentinel-1 dates):

  | Site | Herbaceous wetland: agree / C-only / L-only | Permanent water: agree / C-only / L-only |
  |---|---|---|
  | Sylhet (draining) | 32.5% / 62.1% / 4.3% (κ 0.05) | 31.5% / 56.6% / 6.9% |
  | Okavango (drying) | 33.7% / 2.2% / **63.1%** (κ 0.04) | (< 1,000 cells) |
  | Tonlé Sap (flooding) | 96.0% / 3.0% / 0.8% (κ 0.45; 94% both darkened) | 39.6% / 58.1% / 1.0% |
  | Atchafalaya (little change) | 64.6% / 14.0% / 19.1% (κ 0.29; 2,923 cells) | 74.0% / 24.9% / 1.0% |

  The consistent cross-site signal is on **open water: C-band-only change at all three sites with that class (25–58%), L-band-only ≤ 7%**, as expected if C-band is more sensitive to wind roughening. In vegetated wetland the disagreement is large but **its direction is site-dependent** (C-only in Sylhet, L-only in the Okavango, agreement during Tonlé Sap's flood), so it does not support a single mechanism. A plausible reading for the Okavango is L-band responding to water draining beneath reeds that C-band's canopy return does not show; this is untested.
- **Interpretation (not proven):** C-band (5.6 cm) is more sensitive than L-band (24 cm) to wind ripples and emergent vegetation on shallow water. The bands also differ in polarization (HH vs VV), incidence geometry and dates (up to 4 days), any of which can contribute.

### 4. Impact numbers: sensitivity
| Water threshold shift | Receded | Newly flooded | Cropland emerged |
|---|---|---|---|
| -1.0 dB | 327 km² | 11.5 km² | 294 km² |
| -0.5 dB | 317 km² | 11.0 km² | 288 km² |
| +0.0 dB | 308 km² | 10.9 km² | 282 km² |
| +0.5 dB | 299 km² | 11.0 km² | 275 km² |
| +1.0 dB | 289 km² | 11.7 km² | 268 km² |

- Drained area by land cover: Tree cover 3.7 km², Grassland 5.3 km², Cropland 281.5 km², Permanent water 8.0 km², Herbaceous wetland 8.6 km². WorldCover 2021 is a single-date map; seasonally flooded rice land can be labelled cropland or herbaceous wetland.
- Population (WorldPop R2025A, 100 m, constrained, resampled to 20 m preserving totals): 1,264,651 people in the area; within 200 m / 500 m / 1 km of drained land: 1,106,236 / 1,236,836 / 1,264,010. Because almost everyone lives near water in this basin, proximity does not single out an affected group and is presented as context, not harm. (WorldPop places 154,415 people on pixels that were water in June; this is an artefact of 100 m population cells straddling water edges, so it is not reported as a result.)
- Volume (≈ 2 km³) is order-of-magnitude only: mean area × median SWOT level change.
