# SAR-Pulse

SAR-Pulse is a research tool for investigating environmental change with real **NISAR L-band radar** data. You pick a study area and two dated NISAR observations, and it does the following:
- Detects significant backscatter change (ΔB = B_later − B_earlier, in dB).
- Flags *potential* inundation-related change.
- Lays the result on an interactive map, next to the observation metadata, reference-data checks, precipitation context and a statement of uncertainty.

> Every number in the UI is computed by the backend from real processed observations. Nothing is hard-coded or simulated.

**Demo study area:** Sylhet Haor Basin, Bangladesh. It uses NISAR GCOV repeat pass track 69 ascending, frame 14, from 2026-10-28 to 2026-11-09.

## NASA resources used

| NASA resource | Identifier | What SAR-Pulse uses it for | Status |
|---|---|---|---|
| **NISAR L2 GCOV**, Geocoded Polarimetric Covariance (Validated, V1). NASA–ISRO mission, distributed by NASA's ASF DAAC | `NISAR_L2_GCOV_V1`, CMR collection [`C3622241360-ASF`](https://cmr.earthdata.nasa.gov/search/concepts/C3622241360-ASF.html) | **Primary data.** All radar frames, change maps, statistics and potential-inundation flags are computed from these L-band observations | ✅ Used |
| **NASA Common Metadata Repository (CMR)** | [cmr.earthdata.nasa.gov/search](https://cmr.earthdata.nasa.gov/search/) | Finds NISAR acquisitions over the study area: dates, track, frame, polarizations, footprints, download and QA links | ✅ Used |
| **NASA Earthdata Login** | [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov/) | Authenticates the NISAR downloads | ✅ Used |
| **GPM IMERG Late daily V07**. NASA GPM mission, distributed by NASA GES DISC | `GPM_3IMERGDL`, CMR collection `C2723754859-GES_DISC`, [doi:10.5067/GPM/IMERGDL/DAY/07](https://doi.org/10.5067/GPM/IMERGDL/DAY/07) | Rainfall around the acquisition dates (environmental context) | ⚠️ Integrated; GES DISC has not returned data to this account yet (needs the "NASA GESDISC DATA ARCHIVE" app authorized in Earthdata Login) |

The demo result uses these two NISAR granules, from NASA's ASF DAAC:
- `NISAR_L2_PR_GCOV_034_069_A_014_4005_DHDH_A_20261028T232132_20261028T232207_P05036_N_F_J_001` (28 Oct 2026)
- `NISAR_L2_PR_GCOV_035_069_A_014_4005_DHDH_A_20261109T232132_20261109T232207_P05036_N_F_J_001` (9 Nov 2026)

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

# 3. Download + process the real demo granules (2 full frames, ~6.9 GB each; ~15 GB free disk needed)
.venv/bin/python scripts/fetch_demo.py      # re-running skips files already in data/raw/

# 4. Run (the Next.js dev server forwards /api/* to uvicorn on :8000)
.venv/bin/uvicorn backend.api.main:app --port 8000      # API + docs at :8000/docs
cd frontend && npm install && npm run dev                # UI at http://localhost:3000
```

`scripts/fetch_demo.py --catalog-only` lists the real acquisitions from NASA CMR without downloading anything.

## Reproducing the analysis
1. Open http://localhost:3000. The Sylhet area and the processed same-track pair are preselected. If that pair has been analysed before, the newest stored result opens immediately and is labelled as stored.
2. Use the map views: **Where it changed**, **How much (ΔB)**, **Potential water** and **Before / after** (a swipe between the two radar frames). The legend sits on the map, and clicking any pixel reads its values.
3. To recompute live, open *Analysis settings*, adjust if you want, and click **Run analysis**. Progress stages are shown while it runs, which takes about 20 s.
4. For finer control, toggle, fade and reorder the individual overlays under *Overlays on the table*.
5. The interpretation sheet on the right shows statistics, metadata, reference consistency, rainfall and limitations. The same result is available at `GET /api/analysis/{id}`.

The same analysis can be run headless:
```bash
.venv/bin/python -c "from backend.processing.pipeline import run_analysis; import json; \
r = run_analysis('sylhet_haor', '<earlier granule id>', '<later granule id>'); print(json.dumps(r['statistics'], indent=1))"
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
| Frontend ↔ backend communication | ✅ |
| Real NISAR observation loaded and inspected | ✅ 2 GCOV full frames, HDF5 metadata recorded in `data/reference/observations.json` |
| Compatible metadata enforced | ✅ Same track, direction, polarization and product; incompatible pairs are rejected with reasons |
| Real change-detection result | ✅ Sylhet, 28 Oct → 9 Nov 2026 |
| Georeferenced display | ✅ UTM 46N COGs → XYZ tiles; registers with the river network on the basemap |
| Statistics from valid pixels | ✅ |
| Dates and sensor metadata inspectable | ✅ |
| Clear errors for missing or incompatible data | ✅ |
| RCM only if compatible data exists | ✅ Shown as unavailable, with the reason (no RCM product obtained) |
| Assumptions and limitations documented | ✅ `docs/` |
| No simulated results presented as real | ✅ Synthetic data appears only in tests |
| GPM precipitation (Priority 3) | ⚠️ Implemented; GES DISC refused or failed requests during development, so the UI shows "unavailable" with the reason |

## Findings: Sylhet Haor Basin, 28 Oct → 9 Nov 2026

**Data.** Two NISAR L2 GCOV full frames from the same repeat-pass stack (track 69, ascending, frame 14, product version 1.0.20), frequency A, HH:
- Earlier: `NISAR_L2_PR_GCOV_034_069_A_014_4005_DHDH_A_20261028T232132_20261028T232207_P05036_N_F_J_001`
- Later: `NISAR_L2_PR_GCOV_035_069_A_014_4005_DHDH_A_20261109T232132_20261109T232207_P05036_N_F_J_001`

**Processing.**
- Both frames were cropped to 90.95–91.45°E, 24.75–25.15°N and averaged 2×2 to 20 m.
- A Lee filter (5×5) was applied, then ΔB was computed with a ±3 dB threshold.
- The two grids were identical, so no resampling was needed.

**Results** (2,237 km² analysed, 100% valid pixels):
- Significant **decrease**: 120 km² (5.4%). Significant **increase**: 122 km² (5.5%). Median ΔB is −0.09 dB.
- The robust ΔB spread is σ = 1.37 dB. If ΔB were Gaussian scatter, about 2.8% of pixels would pass ±3 dB; 10.8% did. So the map contains change beyond the bulk scatter, but some flagged pixels are certainly residual speckle.
- **Potential open-water emergence: 19.7 km²** (0.9%). These patches darkened from −15.8 dB to −20.2 dB on average, in connected patches of at least 2 ha.
- Flooded-vegetation candidates (increases within WorldCover tree, wetland or mangrove cover): 9.5 km².
- Cropland changed most, at about 7% decrease and 7% increase each. Herbaceous wetland changed by 4.5–4.8%. Tree cover changed least, and more often decreased (1.9%) than increased (0.6%).

**Interpretation.**
- Over this 12-day window, increases and decreases are almost balanced. The data does **not** show one dominant basin-wide "drainage" signal at the 3 dB level.
- Changes concentrate in cropland and herbaceous wetland, which fits a mix of processes: draining fields, re-wetting or flooding of paddies, and vegetation and soil-moisture change.
- Every open-water candidate lies in pixels that JRC has recorded as water at some point. But 87% of the whole basin has, so that check is weak here.

**These results have not been independently validated.** The natural next steps are concurrent optical water maps, a longer NISAR time series, and Bangladesh FFWC water-level records. See [docs/validation.md](docs/validation.md) and [docs/limitations.md](docs/limitations.md).
