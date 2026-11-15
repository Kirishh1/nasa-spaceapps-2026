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
| **NISAR L2 GCOV**, Geocoded Polarimetric Covariance (Validated, V1). NASA–ISRO mission, distributed by NASA's ASF DAAC | `NISAR_L2_GCOV_V1`, CMR collection [`C3622241360-ASF`](https://cmr.earthdata.nasa.gov/search/concepts/C3622241360-ASF.html) | **Primary data.** All radar frames, change maps, statistics and potential-inundation flags are computed from these L-band observations | ✅ Used |
| **NASA Common Metadata Repository (CMR)** | [cmr.earthdata.nasa.gov/search](https://cmr.earthdata.nasa.gov/search/) | Finds NISAR acquisitions over the study area: dates, track, frame, polarizations, footprints, download and QA links | ✅ Used |
| **NASA Earthdata Login** | [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov/) | Authenticates the NISAR downloads | ✅ Used |
| **OPERA DSWx-S1** surface water from Sentinel-1 (NASA JPL OPERA, NASA PO.DAAC) | `OPERA_L3_DSWX-S1_V1`, `C2949811996-POCLOUD` | **Independent validation**: radar-based water maps one day after each NISAR pass | ✅ Used |
| **OPERA DSWx-HLS** surface water from Landsat/Sentinel-2 (NASA JPL OPERA, NASA PO.DAAC) | `OPERA_L3_DSWX-HLS_V1`, `C2617126679-POCLOUD` | **Independent validation**: cloud-free optical water maps | ✅ Used |
| **OPERA RTC-S1** Sentinel-1 backscatter (NASA JPL OPERA, NASA ASF DAAC) | `OPERA_L2_RTC-S1_V1`, `C2777436413-ASF` | **C-band comparison**: an independent change map from a shorter wavelength | ✅ Used |
| **GPM IMERG Late daily V07**. NASA GPM mission, distributed by NASA GES DISC | `GPM_3IMERGDL`, CMR collection `C2723754859-GES_DISC`, [doi:10.5067/GPM/IMERGDL/DAY/07](https://doi.org/10.5067/GPM/IMERGDL/DAY/07) | Rainfall around the acquisition dates (environmental context) | ⚠️ Integrated; NASA GES DISC did not serve data to this deployment, so rainfall is shown as unavailable |

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
# 4. Fetch NASA OPERA references (validation water maps + Sentinel-1 C-band) on the same grid
.venv/bin/python scripts/fetch_reference.py   # about 400 MB of downloads
.venv/bin/python scripts/opera_timeline.py    # season-long water fraction used for the season chart

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
| GPM precipitation | ⚠️ Implemented; NASA GES DISC did not serve data to this environment |

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

**What this does not show.**
- **No ground truth.** The references are other satellite products, not field observations, and they disagree with each other.
- **Change agreement is weak.** NISAR's "water receded" map agrees only weakly with the C-band reference's own change (F1 0.26). That reference itself jumps between 22% and 45% water from one Sentinel-1 orbit to the next within days.
- **Possibly missed water.** Flooded vegetation under a canopy can look bright to L-band, and is not counted as open water.
- **No depth.** Nothing here measures water depth.

See [docs/methodology.md](docs/methodology.md), [docs/validation.md](docs/validation.md), [docs/limitations.md](docs/limitations.md) and the 2-minute [demo script](docs/demo_script.md).
