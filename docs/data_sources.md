# Data sources

| Dataset | Use | Access | Identifier |
|---|---|---|---|
| NISAR L2 GCOV v1 (NASA/ISRO, distributed by ASF DAAC) | Primary radar observations | NASA CMR search (no auth); HTTPS download with Earthdata Login | Collection `NISAR_L2_GCOV_V1`, `C3622241360-ASF` |
| NISAR L2 GCOV Provisional / Beta | Not used by default (longer history, lower maturity) | same | `C2854338529-ASF`, `C3622214170-ASF` |
| OPERA DSWx-S1 V1 (NASA JPL; NASA PO.DAAC) | Validation: radar water maps | CMR search; HTTPS download with Earthdata Login | `C2949811996-POCLOUD` |
| OPERA DSWx-HLS V1 (NASA JPL; NASA PO.DAAC) | Validation: optical water maps | same | `C2617126679-POCLOUD` |
| OPERA RTC-S1 V1 (NASA JPL; NASA ASF DAAC) | C-band comparison (Sentinel-1 VV) | same; requires approving the ASF app in Earthdata Login | `C2777436413-ASF` |
| SWOT LakeSP Prior, Version D (NASA/CNES; NASA PO.DAAC) | Independent water-level and lake-area evidence | CMR search; Earthdata Login download (continent-wide shapefiles; passes 189, 230, 467, 536 cover the basin) | `C3233942291-POCLOUD` |
| HLS v2.0 (HLSL30/HLSS30; NASA LP DAAC) | True-colour display images of clear days | Earthdata Login download | `C2021957657-LPCLOUD`, `C2021957295-LPCLOUD` |
| SMAP SPL3SMP_E v006 (NASA NSIDC DAAC) | Soil-moisture context | NASA Earthdata cloud OPeNDAP subset | `C2938664763-NSIDC_CPRD` |
| ASF Global 30 m HAND (ASF) | Terrain check | AWS Open Data `s3://glo-30-hand/v1/2021`, CC0, read directly | — |
| ICESat-2 ATL13 (NASA NSIDC DAAC) | Checked; not usable (no same-track in-basin pair) | Earthdata Login download | `C3565574351-NSIDC_CPRD` |
| WorldPop R2025A, 2025, 100 m constrained | Impact (population near drained land) | data.worldpop.org (no range requests, downloaded once) | doi:10.5258/SOTON/WP00839 |
| GPM IMERG daily v07 (Late `GPM_3IMERGDL`, Final `GPM_3IMERGDF`; file versions V07C/V07B) | Precipitation context | NASA Earthdata cloud OPeNDAP (`opendap.earthdata.nasa.gov`), with server-side subsetting to the basin. The legacy `gpm1.gesdisc` host refused connections from this environment | doi:10.5067/GPM/IMERGDL/DAY/07 |
| JRC Global Surface Water v1.4 occurrence | Reference: historical water frequency | Public COG, `storage.googleapis.com/global-surface-water` | Pekel et al. 2016, Nature 540 |
| ESA WorldCover 10 m 2021 v200 | Land-cover context, vegetation mask | Public COG, `esa-worldcover.s3.eu-central-1.amazonaws.com` | doi:10.5281/zenodo.7254221 |
| RCM (CSA) | Originally planned C-band source | EODMS ordering | **Not obtained.** Sentinel-1 via OPERA RTC-S1 is used instead |
| Basemaps | Visual context only | Esri Dark Gray Canvas, Esri World Imagery | — |

## Demo granules (Sylhet Haor Basin)
The exact granule IDs, download URLs, sizes, footprints, QA report links and file metadata are written to `data/reference/observations.json` by `scripts/fetch_demo.py`.

Each demo granule is a full frame of about 6.9 GB; only the study-area crop is kept as COGs. The demo pair is stack `069_A_014`: track 69, ascending, frame 14, HH+HV, with acquisitions on 2026-10-28 and 2026-11-09.

The other stacks over the area are 141_A_014 and 091_D_076. They are listed in the UI, but they can't be paired across tracks.
