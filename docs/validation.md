# Validation

**Status: not independently validated.** No event-specific ground truth was available for the observation dates, such as field surveys or concurrent optical or SAR flood maps. The application states this on every result.

## What is checked
1. **Software tests** (`pytest backend/tests`, 19 tests):
   - dB conversion
   - the sign of ΔB
   - threshold classification and nodata propagation
   - Lee/boxcar filter behaviour
   - connected-component inundation rules
   - area statistics against the raster transform
   - rejection of incompatible pairs (dates, polarization, geometry, overlap, sensor)
   - the full API flow, including tiles and pixel reads
   - strict-JSON results when HDF5 fill values are NaN
   - 2×2 multilooking and the Gaussian noise reference

   The end-to-end test uses a **synthetic** HDF5 file with the GCOV layout. It exists only inside the test suite and is never shown in the app.
2. **Reference consistency** (computed for every analysis):
   - The share of open-water candidates that fall in pixels JRC GSW has ever recorded as water, compared with the same share for all valid pixels. A much higher share means the candidates sit in known floodplains or wetlands.
   - The share of candidates in permanent water (≥ 90% occurrence). Change there more likely reflects wind or water-surface state than new inundation.
   - The ΔB class breakdown by ESA WorldCover land-cover class.
3. **Manual checks** (team, Member 4):
   - compare the output against the NISAR browse PNG and QA report linked for each granule
   - spot-check pixel values against direct `h5py` reads
   - confirm the overlay registers with rivers and coastlines on the optical basemap

## What would validate it
- Concurrent Sentinel-1 or optical (Sentinel-2/Landsat) water maps for 28 Oct and 9 Nov 2026.
- Bangladesh FFWC water-level records.
- Field observations from the haor region.
