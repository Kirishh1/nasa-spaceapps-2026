# Limitations

- **Backscatter change is not flood mapping.** ΔB measures a change in radar return. Wind roughening, soil moisture, crop harvest, vegetation phenology, smooth man-made surfaces and residual speckle can all change backscatter.
- **Flooded vegetation** can raise L-band backscatter through double bounce. Rules that only look at decreases under-detect it. The vegetation rule depends on WorldCover 2021, which may be out of date.
- **Residual speckle.** For the demo pair, about 2.8% of pixels would pass ±3 dB from Gaussian ΔB scatter alone; 10.8% did. So a minority of flagged pixels are likely noise. The connected-area rule reduces this for inundation flags only.
- **Thresholds are generic.** 3 dB and −18 dB are not calibrated for the Sylhet basin.
- **Only one repeat pair** (12 days) is analysed. Seasonal context comes only from JRC occurrence.
- **Geometry.** Only same-track, same-direction pairs are allowed. Incidence angle still varies across the swath, which affects interpretation but not ΔB within a pixel.
- **Validation.** There is no independent ground truth (see validation.md).
- **RCM comparison is not implemented on real data,** because no RCM product was obtained.
- **GPM IMERG** provides ~10 km area means. Late Run estimates are preliminary. Coincidence does not establish causation.
- **Product maturity.** NISAR GCOV is early-mission data, and calibration may be refined in later product versions. The product version is recorded with every observation.
