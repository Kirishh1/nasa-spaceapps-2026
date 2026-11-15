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
