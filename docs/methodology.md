# Methodology

## Research question
Where did L-band backscatter change between consecutive NISAR repeat passes over the Sylhet Haor Basin (Bangladesh) during post-monsoon drainage (28 Oct → 9 Nov 2026, track 69 ascending, frame 14), and which changes are consistent with surface-water change?

## Input
NISAR L2 **GCOV** (Geocoded Polarimetric Covariance), collection `NISAR_L2_GCOV_V1` (CMR `C3622241360-ASF`).
- The diagonal covariance terms (`HHHH`, `HVHV`, …) are radiometrically terrain-corrected backscatter in **linear power**, by default γ⁰. They are delivered on a map-projected grid (UTM) at `/science/LSAR/GCOV/grids/frequency{A,B}/`.
- Frequency A (20 MHz range bandwidth) is used by default.

## Processing chain
1. **Discovery.** NASA CMR is searched by bounding box. Granules are grouped by `STACK_ID` (track_direction_frame) and polarization.
2. **Ingestion** (`backend/ingestion/nisar.py`):
   - Metadata is read and any expected HDF5 paths that are missing are recorded.
   - The selected term is cropped to the study-area bounding box and written as a Cloud-Optimized GeoTIFF.
   - Pixels where `mask == 255` (outside the swath), `mask == 0` (partially focused samples, per GCOV spec 1.6), the value is non-finite, or the value is ≤ 0 become NaN.
   - The native 10 m grid is averaged 2×2 in linear power to 20 m. A block is NaN if fewer than half its samples are valid.
   - The median native `numberOfLooks` (about 4.2 for the demo frames) is recorded. It is deliberately not multiplied by 4 after averaging, because adjacent 10 m samples are correlated. The lower ENL makes the Lee filter smooth more.
3. **Compatibility checks** (`backend/preprocessing/quality.py`). Each failure below is a hard error that stops the analysis:
   - different sensor or product type
   - wrong date order
   - the polarization is missing
   - the track or pass direction differs
   - the footprints don't overlap
   - the study area isn't covered
   - the data isn't ingested
   - after alignment, fewer than 20% of pixels are valid

   Bandwidth, frame or processing-version differences only produce warnings.
4. **Alignment** (`alignment.py`). The later frame is mapped onto the earlier frame's grid:
   - no change if the grids are identical,
   - an integer-pixel window if the CRS and spacing match,
   - otherwise bilinear resampling in linear power.
5. **Speckle filtering** (`calibration.py`). A NaN-aware Lee filter (default 5×5) is applied in linear power, with Cu² = 1/ENL and ENL taken from the GCOV `numberOfLooks`.
6. **Conversion to dB.** B = 10·log₁₀(γ⁰).
7. **Change.** **ΔB = B_later − B_earlier** (dB), using only pixels that are valid in both frames and inside the study polygon.
8. **Classification.** Using |ΔB| ≥ T (default 3 dB): significant decrease / significant increase / limited change / no data.
9. **Potential inundation** (`inundation.py`, co-pol only).
   - *Open-water emergence:* significant decrease **and** B_later < −18 dB (configurable), in an 8-connected patch ≥ 2 ha.
   - *Flooded-vegetation candidates:* significant increase inside ESA WorldCover tree, herbaceous-wetland or mangrove classes, consistent with double-bounce scattering.
   - Both are labelled *potential*.
10. **Statistics** (`statistics.py`):
    - areas come from pixel count × |det(transform)| in m²
    - valid and missing share
    - ΔB distribution and histogram
    - a **noise reference**: the robust ΔB spread σ = 1.4826·MAD, with the share of pixels past the threshold compared against what a zero-mean Gaussian of that σ would produce. It indicates change beyond the bulk scatter; it is not a speckle model.
11. **Reference consistency** (`validation/`). JRC Global Surface Water occurrence and ESA WorldCover are read from public COGs onto the analysis grid. See [validation.md](validation.md).
12. **Environmental context.** GPM IMERG daily area means (Late Run, or Final Run when available) are fetched over the study-area bounding box through GES DISC OPeNDAP.

## Why these thresholds
- **3 dB** is a common change threshold for multilooked SAR. For the demo pair it is 2.2× the robust ΔB spread (1.37 dB). The UI reports the observed versus Gaussian-expected exceedance, so users can see how much of the result could be scatter.
- **−18 dB** is typical of the lower range of L-band HH γ⁰ for calm open water. It is site-dependent, so users can adjust it.

All parameters are exposed in the UI and stored with every result.

## What ΔB is not
ΔB is a change in the radar return. It is not a measurement of water depth or flood extent. A decrease is *consistent with* smooth water appearing, but it can also come from soil drying, harvest or geometry. See [limitations.md](limitations.md).

## Multi-sensor comparison (designed, not active)
- `backend/comparison/` aggregates two independently derived change-class rasters to a common coarser grid, using the dominant class per cell.
- It then labels each cell as agreement (stable / decrease / increase), change in only one sensor, or opposite directions.
- Raw L-band and C-band backscatter are never subtracted from each other.
- It stays inactive until calibrated RCM data is ingested.

## Open-water mapping (added for the monsoon case study)
- **Water/land split.** On each date, open water = speckle-filtered HH backscatter below a threshold.
- **Threshold choice.** The threshold is chosen per image with Otsu's method on the dB histogram, searched within −24 to −10 dB, a physically plausible window for L-band HH.
- **When the split is unclear.** The threshold is used only if the histogram is clearly two-peaked: Otsu's separability η = σ²_between / σ²_total ≥ 0.7. A single bell curve always gives η ≈ 2/π ≈ 0.64, so 0.7 sits just above that.
  - If one date fails (for example, almost no water), it reuses the other date's threshold.
  - If both fail, the fixed configured value is used.
  - The method and η are stored with every result. The Sylhet scenes give η 0.74–0.80.
- **Small patches.** Open-water patches smaller than the minimum region (2 ha) are removed.
- **Water change classes.** Land on both dates, water on both dates, water gained, water receded.
- **Flooded vegetation** can appear *brighter* than land (double bounce), so it is deliberately not counted as open water. It is flagged separately, as increases inside tree, wetland and mangrove cover.

## Validation against NASA OPERA (see validation.md)
- For each NISAR date, the closest OPERA DSWx-S1 and DSWx-HLS water maps within ±2 days are mosaicked onto the NISAR grid (nearest neighbour, 30 → 20 m).
- Optical maps must be at least 50% cloud-free over the basin. Radar maps must cover at least 30%.
- Pixels count only where both maps have valid data.
- Metrics: precision, recall, F1, IoU, overall accuracy and Cohen's κ, for open water. The "all water" variant also counts DSWx-S1 inundated vegetation and DSWx-HLS partial surface water.
- A threshold-sensitivity sweep (±3 dB around the chosen threshold) is stored with every comparison.

## L-band vs C-band comparison
- **Independent C-band map.** Sentinel-1 VV backscatter (OPERA RTC-S1, linear γ⁰, 30 m) from a single orbit, near both NISAR dates, is mosaicked onto the NISAR grid. It goes through the same Lee filter, dB, ΔB and ±3 dB classes as NISAR, on its own data.
- **Pass selection.** The pair is the same-orbit Sentinel-1 passes that minimise the total date offset from the NISAR pair (for the case study: orbit 41, 19 Jun and 12 Oct).
- **Common grid.** Both class maps are aggregated to 100 m cells. A cell takes "decrease" or "increase" when that class covers at least 30% of its valid pixels, and is "no data" when under half of it is valid.
- **Agreement classes.** Cells are compared as: both stable, both decrease, both increase, L-band only, C-band only, or opposite directions. These are reported overall and per ESA WorldCover land-cover class (dominant class per cell).
- **No cross-sensor differencing.** Raw L- and C-band backscatter are never subtracted from each other.
