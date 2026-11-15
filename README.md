# SAR-Pulse

**What changed between two NASA–ISRO NISAR radar passes, and how sure can we be?**

SAR-Pulse turns real NISAR L-band radar observations into a validated surface-water change analysis:
- It maps open water on each date, with a threshold chosen automatically per image.
- It measures where water receded or appeared, and how backscatter changed.
- It scores those water maps against independent NASA OPERA surface-water products: radar (Sentinel-1) and cloud-free optical (Landsat/Sentinel-2).
- It compares NISAR's L-band change map with an independent C-band (Sentinel-1) change map, to show where the two wavelengths disagree and why.

> Every number in the app comes from processing real observations. Nothing is hard-coded or simulated.

**Case study:** monsoon drainage of the Sylhet haor wetlands, Bangladesh. NISAR track 69 ascending, frame 14, from **18 June to 16 October 2026** (120 days).

## NASA resources used

| NASA resource | Identifier | What SAR-Pulse uses it for | Status |
|---|---|---|---|
| **NISAR L2 GCOV**, Geocoded Polarimetric Covariance (V1). NASA–ISRO mission, distributed by NASA's ASF DAAC | Provisional [`C2854338529-ASF`](https://cmr.earthdata.nasa.gov/search/concepts/C2854338529-ASF.html) (Jun–Oct frames) and validated [`C3622241360-ASF`](https://cmr.earthdata.nasa.gov/search/concepts/C3622241360-ASF.html) (late Oct–Nov) | **Primary data.** All radar frames, change maps, statistics and potential-inundation flags are computed from these L-band observations | ✅ Used |
| **NASA Common Metadata Repository (CMR)** | [cmr.earthdata.nasa.gov/search](https://cmr.earthdata.nasa.gov/search/) | Finds NISAR acquisitions over the study area: dates, track, frame, polarizations, footprints, download and QA links | ✅ Used |
| **NASA Earthdata Login** | [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov/) | Authenticates the NISAR downloads | ✅ Used |
| **OPERA DSWx-S1** surface water from Sentinel-1 (NASA JPL OPERA, NASA PO.DAAC) | `OPERA_L3_DSWX-S1_V1`, `C2949811996-POCLOUD` | **Independent validation**: radar-based water maps one day after each NISAR pass | ✅ Used |
| **OPERA DSWx-HLS** surface water from Landsat/Sentinel-2 (NASA JPL OPERA, NASA PO.DAAC) | `OPERA_L3_DSWX-HLS_V1`, `C2617126679-POCLOUD` | **Independent validation**: cloud-free optical water maps | ✅ Used |
| **OPERA RTC-S1** Sentinel-1 backscatter (NASA JPL OPERA, NASA ASF DAAC) | `OPERA_L2_RTC-S1_V1`, `C2777436413-ASF` | **C-band comparison**: an independent change map from a shorter wavelength | ✅ Used |
| **SWOT LakeSP Prior, Version D** (NASA/CNES SWOT, NASA PO.DAAC) | `SWOT_L2_HR_LakeSP_prior_D`, `C3233942291-POCLOUD` | **Independent water-level evidence**: lake water-surface height and area, measured directly | ✅ Used |
| **HLS** surface reflectance (HLSL30/HLSS30 v2.0; NASA LP DAAC) | `C2021957657-LPCLOUD`, `C2021957295-LPCLOUD` | True-colour images of clear days (15 Sep, 4 Oct, 17 Oct) for the map's "Optical photo" view | ✅ Used |
| **SMAP** L3 Enhanced soil moisture (NASA NSIDC DAAC) | `SPL3SMP_E`, `C2938664763-NSIDC_CPRD` | Context for false positives: soil drying lowers land backscatter | ✅ Used |
| **ASF Global 30 m HAND** (Alaska Satellite Facility) | `s3://glo-30-hand/v1/2021` | Terrain check: the basin lies a median 0.2 m above drainage | ✅ Used |
| **ICESat-2 ATL13** inland water height (NASA NSIDC DAAC) | `C3565574351-NSIDC_CPRD` | Checked as a second altimeter; only 2 in-basin passes on different tracks, so no before/after possible | ⛔ Checked, not usable |
| **GPM IMERG Late daily V07**. NASA GPM mission, distributed by NASA GES DISC | `GPM_3IMERGDL`, CMR collection `C2723754859-GES_DISC`, [doi:10.5067/GPM/IMERGDL/DAY/07](https://doi.org/10.5067/GPM/IMERGDL/DAY/07) | Rainfall around the acquisition dates (environmental context) | ✅ Used (season series via NASA Earthdata cloud OPeNDAP) |

The case study uses these two NISAR granules (provisional collection `C2854338529-ASF`, product version 1.0.11), from NASA's ASF DAAC:
- `NISAR_L2_PR_GCOV_023_069_A_014_4005_DHDH_A_20260618T232135_20260618T232210_P05023_N_F_J_001` (18 Jun 2026)
- `NISAR_L2_PR_GCOV_033_069_A_014_4005_DHDH_A_20261016T232132_20261016T232206_P05023_N_F_J_001` (16 Oct 2026)

The app also includes stored results for 16 Oct → 9 Nov and 28 Oct → 9 Nov. The 9 Nov and 28 Oct granules come from the validated collection, product version 1.0.20.

The same list is served live at `GET /api/sources` and shown in the app under **Data sources**. Non-NASA resources (JRC Global Surface Water, ESA WorldCover, Esri basemaps) and the unused RCM are listed there and in [docs/data_sources.md](docs/data_sources.md).

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/), Node ≥ 20, and a NASA Earthdata account.

```bash
# 1. Backend environment (Python 3.11; rasterio wheels bundle GDAL)
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements-dev.txt

# 2. Credentials: create a token at https://urs.earthdata.nasa.gov → Generate Token
cp .env.example .env        # then set EARTHDATA_TOKEN=...  (username/password not needed)
#    Optional, for GPM rainfall: in your Earthdata profile → Applications → Authorized Apps,
#    approve "NASA GESDISC DATA ARCHIVE".

#    For the OPERA C-band data, also approve ASF's app (the download error links to it), and
#    accept the PO.DAAC terms if prompted.
# 3. Download and process the real NISAR frames (full frames, ~7 GB each; ~30 GB free disk needed)
.venv/bin/python scripts/fetch_demo.py        # re-running skips files already in data/raw/
# 4. Fetch the independent references on the same grid
.venv/bin/python scripts/fetch_reference.py   # NASA OPERA water maps, Sentinel-1 C-band, land cover (~450 MB)
.venv/bin/python scripts/opera_timeline.py    # season-long OPERA water fraction for the season chart
.venv/bin/python scripts/fetch_swot.py        # NASA/CNES SWOT lake heights/areas (~650 MB of continent-wide files)
.venv/bin/python scripts/fetch_rainfall.py    # NASA GPM IMERG daily rainfall via cloud OPeNDAP
.venv/bin/python scripts/fetch_soil_moisture.py  # NASA SMAP soil moisture via cloud OPeNDAP
.venv/bin/python scripts/fetch_context.py     # ASF HAND, WorldPop 2025, NASA HLS true colour
.venv/bin/python scripts/nisar_season.py      # NISAR water fraction + validation for every processed frame

# 5. Run (the Next.js dev server forwards /api/* to uvicorn on :8000)
.venv/bin/uvicorn backend.api.main:app --port 8000      # API + docs at :8000/docs
cd frontend && npm install && npm run dev                # UI at http://localhost:3000
```

`scripts/fetch_demo.py --catalog-only` lists the real acquisitions from NASA CMR without downloading anything.

## Reproducing the analysis
1. Open http://localhost:3000. The featured pair, 18 Jun → 16 Oct, is preselected, and its stored result opens.
2. Press **Take the 1-minute tour**. It steps through the problem, the data, the discovery, the validation and the wavelength comparison, switching the map view as it goes.
3. Explore on your own using the map views: **Water change**, **Backscatter change**, **ΔB**, **L vs C band** and **Before / after**. Click any pixel to read its values.
4. Press **Run analysis** to recompute live. It takes about 15–20 s, and progress is shown.

The same analysis can be run headless:
```bash
.venv/bin/python -c "from backend.processing.pipeline import run_analysis; import json; \
r = run_analysis('sylhet_haor', '<earlier granule id>', '<later granule id>'); print(json.dumps(r['validation']['accuracy'], indent=1))"
```

## Deploying to Vercel

`vercel.json` deploys two services as one Vercel project:

| Service | Root | Framework | Public path |
|---|---|---|---|
| `api` | `.` | FastAPI (`backend.api.main:app`) | `/api/*` |
| `web` | `frontend/` | Next.js | everything else |

The browser calls the API on the same origin (`/api/...`), so the services need no bindings.

Data comes from **Vercel Blob**, because `data/` is not in git:

1. In the Vercel project, create a Blob store (**private** access) and connect it to the project.
2. In the project's environment variables, set `SARPULSE_STORAGE=blob`.
3. Locally, copy the store's `BLOB_READ_WRITE_TOKEN` into `.env`. Then, after `scripts/fetch_demo.py` has run, upload the demo data (about 180 MB):
   ```bash
   .venv/bin/python scripts/upload_to_blob.py --dry-run   # see what will be uploaded
   .venv/bin/python scripts/upload_to_blob.py
   ```
4. Deploy with `vercel deploy`, or push to the connected Git repository.

On Vercel:
- **Runtime behaviour:** analyses run inside the request (about 20 s; the function limit is 300 s) and write to `/tmp`. Results are then uploaded to Blob, so every instance can serve their tiles. Each instance downloads the rasters it needs into a `/tmp` cache on first use.
- **Local testing:** `vercel dev` runs both services together.
- **Rainfall:** GPM precipitation also needs `EARTHDATA_TOKEN` set as a project environment variable.

## Tests
```bash
.venv/bin/python -m pytest backend/tests
```

## Repository
```
backend/   ingestion · preprocessing · processing · comparison · environmental_context · validation · api · tests
frontend/  Next.js + MapLibre (app/, maps/, components/, dashboard/, services/)
scripts/   fetch_demo.py, demo_areas.json
docs/      architecture · methodology · data_sources · validation · limitations
data/      raw/ processed/ reference/   (git-ignored; created by the scripts)
```

## Status against the acceptance checklist
| Item | Status |
|---|---|
| Starts locally with documented instructions | ✅ |
| Frontend ↔ backend communication | ✅ Same-origin `/api`, deployed on Vercel |
| Real NISAR observations loaded and inspected | ✅ 4 GCOV full frames, with HDF5 metadata recorded |
| Compatible metadata enforced | ✅ Same track, direction, polarization and product. A product-version difference is flagged as a warning |
| Real change-detection result | ✅ Backscatter change plus open-water change |
| Georeferenced display | ✅ UTM 46N COGs → XYZ tiles |
| Statistics from valid pixels | ✅ |
| Independent validation | ✅ Pixel-wise against NASA OPERA DSWx-HLS (optical) and DSWx-S1 (radar): precision, recall, F1, IoU, κ, plus a threshold-sensitivity sweep |
| Multi-wavelength comparison | ✅ NISAR L-band vs Sentinel-1 C-band (NASA OPERA RTC-S1). RCM itself could not be obtained |
| Dates and sensor metadata inspectable | ✅ |
| Clear errors for missing or incompatible data | ✅ |
| Assumptions and limitations documented | ✅ `docs/` |
| No simulated results presented as real | ✅ Synthetic data appears only in tests |
| GPM precipitation | ✅ Daily basin-mean series, Jun–Nov 2026 |
| Water-level evidence | ✅ NASA/CNES SWOT lake heights and areas, per lake |
| Calibration check | ✅ Invariant-target ΔB reported with every analysis |

## Findings: Sylhet haor wetlands, 18 June → 16 October 2026

**Question.** How much of the Sylhet haor wetlands drained between monsoon high water and the post-monsoon season? How well does NISAR L-band map that water compared with independent NASA OPERA maps? And where does L-band see change that C-band does not?

**1. The wetlands drained.**
- NISAR maps open water across **1766 km²** of the 2237 km² basin on 18 June (79%). By 16 October that is **1469 km²** (66%).
- **308 km²** receded, and only 11 km² newly flooded.
- The thresholds were chosen automatically for each image (Otsu, -12.24 and -12.02 dB). Both histograms were clearly bimodal (separability η 0.801 and 0.794).

**2. The water maps agree with an independent optical sensor.**
- Against the cloud-free NASA OPERA DSWx-HLS map (Landsat-9, 17 Oct, one day later), the 16 October NISAR water map scores **F1 0.90, IoU 0.81, κ 0.74** (precision 0.83, recall 0.97).
- Shifting the threshold by ±3 dB keeps F1 between 0.84 and 0.91, so the agreement does not depend on one lucky threshold.
- A second optical check, 28 Oct NISAR against Sentinel-2B on 27 Oct, gives F1 0.85.

**3. Against C-band radar, NISAR finds much more water.**
- Recall against OPERA DSWx-S1 is ≥ 0.99, but precision is only 0.58–0.59: NISAR marks as water many pixels that the C-band map calls land.
- On the same pixels on 17 Oct, NISAR maps 68% as open water, C-band 40%, and optical 56%. The optical map sides with L-band.

**4. The two wavelengths disagree where there is water.**
- Comparing NISAR's change map with an independent Sentinel-1 C-band change map (OPERA RTC-S1, orbit 41, 2026-06-19 → 2026-10-12) on 100 m cells, the bands agree on **46%** of cells.
- Agreement is 90.8% over tree cover, but only 32.5% over herbaceous wetland and 31.5% over permanent water. There, C-band alone reports change on 62.1% and 56.6% of cells.
- This is consistent with known physics. C-band (5.6 cm) responds strongly to centimetre-scale wind ripples on water and to emergent vegetation; L-band (24 cm) largely does not. It has not been proven for this scene.

**5. An independent instrument confirms the drainage.** NASA/CNES SWOT measures lake water *height* directly.
- Paired lake by lake between the SWOT passes closest to the NISAR dates, **every lake it observed fell**: median **-1.38 m** across 11 lakes (pass 467, 2026-06-15 → 2026-10-18) and **-1.25 m** across 9 lakes (pass 536). SWOT's measurement uncertainty is 3–5 cm.
- Per-lake open-water area agrees between NISAR and SWOT at r = 0.848 (20 lakes). Per-lake area *change* agrees at r = 0.59 (rank ρ 0.266, so a few large lakes drive r), with the same direction for 90% of lakes.
- Lake outlines are widened by 250 m, chosen by matching earlier-date total area, never by the change score.

**6. Rainfall explains the timing.** NASA GPM IMERG basin-mean rainfall was 364 mm in June, 303 mm in July and 308 mm in August, then fell to 141 mm in September and 24 mm in October. The monsoon switched off before the drainage. This is coincidence in time, not proof of cause.

**7. The two frames are radiometrically consistent.** Buildings and trees that stayed land changed by a median of 0.00 dB between the passes, so the change is not a calibration artefact. The same check flags the mixed-version pair (16 Oct → 9 Nov, product versions 1.0.11 / 1.0.20) at -0.72 dB, beyond the 0.5 dB tolerance, and the app warns about it.

**8. NISAR tracks the whole season, and optical agrees at every clear date.** Seven NISAR passes (18 Jun to 9 Nov) show open water falling steadily from 79% to 63% of the basin. Every pass with a clear optical map nearby agrees closely:
- 2026-09-10: F1 **0.93** vs optical (2026-09-15, ±5 d)
- 2026-09-22: F1 **0.95** vs optical (2026-09-27, ±5 d)
- 2026-10-04: F1 **0.98** vs optical (2026-10-04, ±0 d)
- 2026-10-16: F1 **0.90** vs optical (2026-10-17, ±1 d)
- 2026-10-28: F1 **0.85** vs optical (2026-10-27, ±1 d)

**9. Optical before/after confirms which neighbourhoods drained.** For 10 Sep → 16 Oct, both ends have clear optical maps (15 Sep, 17 Oct).
- NISAR's "water receded" map agrees with optical on the direction of change in **93% of 500 m cells** that changed (r = 0.353).
- At pixel level it agrees only modestly: F1 0.30, direction 54% at 100 m. NISAR finds the right areas, but exact edges differ.

**10. Why it matters.** Between 18 June and 16 October:
- **281 km² of cropland** (ESA WorldCover) came out of the water. Haor farmers prepare boro rice seedbeds as water recedes in November–December, so the map shows where planting can start.
- About **1.26 million people** (WorldPop 2025, 100% of the basin) live within 1 km of land that drained.
- Roughly **2.1 km³** of water left the basin. This is an order of magnitude: mean water area × SWOT level drop.
- NASA SMAP shows soil moisture falling from 0.45 (June) to 0.23 m³/m³ (October), which is why some land backscatter also changed.

**What this does not show.**
- **No ground truth.** The references are other satellite products, not field observations, and they disagree with each other.
- **Pixel-exact edges are not confirmed.** Neighbourhood-level change agrees with optical (point 9), but at 20 m pixels the "water receded" map agrees only modestly with optical (F1 ≈ 0.30) and weakly with the C-band reference (F1 0.09–0.25, a reference that agrees with *itself* across orbits only at F1 0.37–0.60). June is too cloudy for an optical pair.
- **Possibly missed water.** Flooded vegetation under a canopy can look bright to L-band, and is not counted as open water.
- **No depth.** Nothing here measures water depth.

See [docs/methodology.md](docs/methodology.md), [docs/validation.md](docs/validation.md), [docs/limitations.md](docs/limitations.md) and the 2-minute [demo script](docs/demo_script.md).
