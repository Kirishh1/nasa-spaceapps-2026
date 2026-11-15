# Architecture

```
NASA CMR / ASF ──► scripts/fetch_demo.py ──► data/raw/*.h5
                        │  backend/ingestion (discovery, nisar reader)
                        ▼
              data/processed/observations/<granule>/<area>_A_HHHH.tif (COG, linear γ⁰)
              data/reference/{study_areas,observations}.json (registry)
                        │
FastAPI (backend/api) ── POST /api/analysis ─► processing/pipeline.py
                        │   quality → alignment → Lee filter → dB → ΔB → classes
                        │   → inundation → statistics → validation (JRC, WorldCover)
                        │   → GPM context
                        ▼
              data/processed/analyses/<id>/{earlier_db,later_db,delta_db,change_class,inundation,jrc_occurrence}.tif + result.json
                        │
              GET /api/tiles/<id>/<layer>/{z}/{x}/{y}.png  (rio-tiler, reprojects COG → Web Mercator)
                        ▼
Next.js frontend (frontend/) — MapLibre GL JS light table, tool tray, interpretation sheet
```

## Endpoints
| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Health check |
| `GET /api/study-areas` | Study areas, each with its boundary |
| `GET /api/observations?study_area=&sensor=NISAR\|RCM` | Real observations, with footprints and ingestion state |
| `GET /api/observations/{id}` | Full CMR and HDF5 metadata |
| `GET /api/observations/{id}/tiles/{area}/{A_HHHH}/{z}/{x}/{y}.png` | Original frame preview in dB |
| `POST /api/analysis/check` | Compatibility check without running the analysis |
| `POST /api/analysis` | Starts an analysis. Returns 202, or 422 with `errors[]` when the pair is incompatible |
| `GET /api/analysis/{id}` | Status, or the full result |
| `GET /api/analysis/{id}/statistics` | Statistics, validation and inundation info |
| `GET /api/analysis/{id}/layers` | Tile templates, bounds and legends |
| `GET /api/analysis/{id}/pixel?lon=&lat=` | Pixel inspection |
| `GET /api/tiles/{id}/{layer}/{z}/{x}/{y}.png` | Result tiles |

Interactive OpenAPI docs are served at `http://localhost:8000/docs`.

## Storage and deployment
- `backend/storage.py` addresses all data by paths relative to the data root.
  - **local** mode (the default) reads and writes `data/`.
  - **blob** mode (`SARPULSE_STORAGE=blob`) uses a Vercel Blob store under the prefix `sarpulse/`. Rasters are cached in `/tmp` on first use.
- Paths in `observations.json` are relative to the data root, so the registry is portable between machines and the store.
- **On Vercel** (`vercel.json`): `api` (FastAPI) serves `/api/*` and `web` (Next.js) serves everything else.
  - Analyses run synchronously inside the request.
  - Results are uploaded to Blob with `result.json` written last.
