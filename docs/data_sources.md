# Data sources

| Dataset | Use | Access | Identifier |
|---|---|---|---|
| NISAR L2 GCOV v1 (NASA/ISRO, distributed by ASF DAAC) | Primary radar observations | NASA CMR search (no auth); HTTPS download with Earthdata Login | Collection `NISAR_L2_GCOV_V1`, `C3622241360-ASF` |
| NISAR L2 GCOV Provisional / Beta | Not used by default (longer history, lower maturity) | same | `C2854338529-ASF`, `C3622214170-ASF` |
| GPM IMERG daily v07 (Late `GPM_3IMERGDL`, Final `GPM_3IMERGDF`; file versions V07C/V07B) | Precipitation context | GES DISC OPeNDAP with Earthdata token. The account must authorize "NASA GESDISC DATA ARCHIVE". Requests failed (401, then connection refused) during development | doi:10.5067/GPM/IMERGDL/DAY/07 |
| JRC Global Surface Water v1.4 occurrence | Reference: historical water frequency | Public COG, `storage.googleapis.com/global-surface-water` | Pekel et al. 2016, Nature 540 |
| ESA WorldCover 10 m 2021 v200 | Land-cover context, vegetation mask | Public COG, `esa-worldcover.s3.eu-central-1.amazonaws.com` | doi:10.5281/zenodo.7254221 |
| RCM (CSA) | Planned C-band comparison | EODMS ordering | **Not ingested.** No RCM product was obtained for the study area, so no RCM result is shown |
| Basemaps | Visual context only | Esri Dark Gray Canvas, Esri World Imagery | — |

## Demo granules (Sylhet Haor Basin)
The exact granule IDs, download URLs, sizes, footprints, QA report links and file metadata are written to `data/reference/observations.json` by `scripts/fetch_demo.py`.

Each demo granule is a full frame of about 6.9 GB; only the study-area crop is kept as COGs. The demo pair is stack `069_A_014`: track 69, ascending, frame 14, HH+HV, with acquisitions on 2026-10-28 and 2026-11-09.

The other stacks over the area are 141_A_014 and 091_D_076. They are listed in the UI, but they can't be paired across tracks.
