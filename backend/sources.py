"""Single source of truth for the data resources SAR-Pulse uses, served at GET /api/sources.

Identifiers were checked against NASA CMR on 2026-11-15. ``role`` says what the resource does in the
app; ``status`` says whether it actually contributed (``used``), is wired in but returned nothing
(``integrated``), or is not used (``not_used``). Never mark something ``used`` that the app does not use.
"""
from __future__ import annotations

NASA_RESOURCES = [
    {
        "id": "nisar_gcov",
        "name": "NISAR L2 GCOV, Geocoded Polarimetric Covariance (Version 1: provisional and validated collections)",
        "short_name": "NISAR_L2_GCOV",
        "identifier": "CMR collections C2854338529-ASF (provisional, Jun–Oct 2026 frames) and C3622241360-ASF (validated, late Oct–Nov 2026)",
        "provider": "NASA–ISRO NISAR mission; distributed by NASA's Alaska Satellite Facility DAAC (ASF)",
        "role": "Primary data. Every radar frame, change map, statistic and potential-inundation flag "
                "is computed from these L-band backscatter observations (HH and HV, frequency A).",
        "status": "used",
        "links": [
            {"label": "NASA Earthdata catalog", "url": "https://www.earthdata.nasa.gov/data/catalog/asf-nisar-l2-gcov-v1-1"},
            {"label": "Provisional collection record", "url": "https://cmr.earthdata.nasa.gov/search/concepts/C2854338529-ASF.html"},
            {"label": "CMR collection record", "url": "https://cmr.earthdata.nasa.gov/search/concepts/C3622241360-ASF.html"},
            {"label": "NISAR mission (NASA JPL)", "url": "https://nisar.jpl.nasa.gov/"},
        ],
    },
    {
        "id": "cmr",
        "name": "NASA Common Metadata Repository (CMR)",
        "short_name": "CMR",
        "identifier": "cmr.earthdata.nasa.gov/search",
        "provider": "NASA Earth Science Data and Information System (ESDIS)",
        "role": "Discovery. Finds the NISAR acquisitions over the study area and supplies their dates, track, "
                "frame, polarizations, footprints, download and QA-report links shown in the app.",
        "status": "used",
        "links": [{"label": "CMR search API", "url": "https://cmr.earthdata.nasa.gov/search/"}],
    },
    {
        "id": "earthdata_login",
        "name": "NASA Earthdata Login",
        "short_name": "EDL",
        "identifier": "urs.earthdata.nasa.gov",
        "provider": "NASA ESDIS",
        "role": "Authentication for downloading the NISAR granules (and for GPM requests).",
        "status": "used",
        "links": [{"label": "Earthdata Login", "url": "https://urs.earthdata.nasa.gov/"}],
    },
    {
        "id": "opera_dswx_s1",
        "name": "OPERA Dynamic Surface Water Extent from Sentinel-1 (DSWx-S1) V1",
        "short_name": "OPERA_L3_DSWX-S1_V1",
        "identifier": "CMR collection C2949811996-POCLOUD",
        "provider": "NASA JPL OPERA project; distributed by NASA PO.DAAC",
        "role": "Independent validation. NISAR open-water maps are scored against these radar-based water maps "
                "(open water and inundated vegetation) from within a few days of each NISAR pass.",
        "status": "integrated",
        "links": [{"label": "PO.DAAC dataset", "url": "https://podaac.jpl.nasa.gov/dataset/OPERA_L3_DSWX-S1_V1"},
                  {"label": "OPERA project (NASA Earthdata)", "url": "https://www.earthdata.nasa.gov/data/projects/opera"}],
    },
    {
        "id": "opera_dswx_hls",
        "name": "OPERA Dynamic Surface Water Extent from Harmonized Landsat-Sentinel-2 (DSWx-HLS) V1",
        "short_name": "OPERA_L3_DSWX-HLS_V1",
        "identifier": "CMR collection C2617126679-POCLOUD",
        "provider": "NASA JPL OPERA project; distributed by NASA PO.DAAC",
        "role": "Independent optical validation on cloud-free days: a completely different sensor type from radar.",
        "status": "integrated",
        "links": [{"label": "PO.DAAC dataset", "url": "https://podaac.jpl.nasa.gov/dataset/OPERA_L3_DSWX-HLS_V1"}],
    },
    {
        "id": "opera_rtc_s1",
        "name": "OPERA Radiometric Terrain Corrected Sentinel-1 backscatter (RTC-S1) V1",
        "short_name": "OPERA_L2_RTC-S1_V1",
        "identifier": "CMR collection C2777436413-ASF",
        "provider": "NASA JPL OPERA project; distributed by NASA's ASF DAAC",
        "role": "C-band comparison. An independent change map from Sentinel-1 VV is compared with NISAR's L-band change map.",
        "status": "integrated",
        "links": [{"label": "ASF dataset", "url": "https://www.earthdata.nasa.gov/data/catalog/asf-opera-l2-rtc-s1-v1-1"}],
    },
    {
        "id": "swot_lakesp",
        "name": "SWOT Level 2 Lake Single-Pass Vector Prior (LakeSP, Version D)",
        "short_name": "SWOT_L2_HR_LakeSP_prior_D",
        "identifier": "CMR collection C3233942291-POCLOUD",
        "provider": "NASA/CNES Surface Water and Ocean Topography mission; distributed by NASA PO.DAAC",
        "role": "Independent water-level evidence: SWOT measures each lake's water-surface height and area directly, "
                "so it checks the drainage finding with a different instrument and a different physical quantity.",
        "status": "integrated",
        "links": [{"label": "PO.DAAC dataset", "url": "https://podaac.jpl.nasa.gov/dataset/SWOT_L2_HR_LakeSP_prior_D"},
                  {"label": "SWOT mission (NASA JPL)", "url": "https://swot.jpl.nasa.gov/"}],
    },
    {
        "id": "gpm_imerg",
        "name": "GPM IMERG Late Precipitation L3 1 day 0.1° × 0.1° V07",
        "short_name": "GPM_3IMERGDL",
        "identifier": "CMR collection C2723754859-GES_DISC · doi:10.5067/GPM/IMERGDL/DAY/07",
        "provider": "NASA Global Precipitation Measurement mission; distributed by NASA GES DISC",
        "role": "Environmental context: daily basin-mean rainfall through the season, retrieved via NASA's Earthdata cloud OPeNDAP service.",
        "status": "integrated",
        "links": [
            {"label": "GES DISC dataset", "url": "https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGDL_07/summary"},
            {"label": "IMERG overview (NASA GPM)", "url": "https://gpm.nasa.gov/data/imerg"},
        ],
    },
]

OTHER_RESOURCES = [
    {"id": "jrc_gsw", "name": "JRC Global Surface Water occurrence v1.4", "provider": "European Commission Joint Research Centre",
     "role": "Reference: historical water frequency, for a consistency check.", "status": "used",
     "links": [{"label": "Dataset", "url": "https://global-surface-water.appspot.com/"}]},
    {"id": "worldcover", "name": "ESA WorldCover 10 m 2021 v200", "provider": "European Space Agency",
     "role": "Reference: land cover, for the flooded-vegetation rule and per-class breakdown.", "status": "used",
     "links": [{"label": "Dataset", "url": "https://esa-worldcover.org/"}]},
    {"id": "rcm", "name": "RADARSAT Constellation Mission (C-band)", "provider": "Canadian Space Agency",
     "role": "Originally planned C-band source. No RCM data was obtained; Sentinel-1 via NASA OPERA RTC-S1 provides the C-band comparison instead.",
     "status": "not_used", "links": []},
    {"id": "sentinel1", "name": "Copernicus Sentinel-1 (C-band SAR)", "provider": "European Space Agency / European Commission",
     "role": "The radar behind OPERA RTC-S1 and DSWx-S1 (processed by NASA JPL).", "status": "used",
     "links": [{"label": "Mission", "url": "https://sentiwiki.copernicus.eu/web/s1-mission"}]},
    {"id": "basemaps", "name": "Esri Dark Gray Canvas and World Imagery basemaps", "provider": "Esri and partners",
     "role": "Visual map background only; not used in any calculation.", "status": "used", "links": []},
]


def sources(precipitation: dict | None = None, result: dict | None = None) -> dict:
    """Resource list; statuses of optional products reflect the given analysis result."""
    nasa = [dict(r) for r in NASA_RESOURCES]
    used_refs = {a["product"] for a in ((result or {}).get("validation", {}).get("accuracy") or [])}
    cband_used = ((result or {}).get("sensor_comparison") or {}).get("status") == "available"
    for r in nasa:
        if r["id"] == "opera_dswx_s1" and "DSWX_S1" in used_refs:
            r["status"] = "used"
        if r["id"] == "opera_dswx_hls" and "DSWX_HLS" in used_refs:
            r["status"] = "used"
        if r["id"] == "opera_rtc_s1" and cband_used:
            r["status"] = "used"
        if r["id"] == "swot_lakesp" and ((result or {}).get("validation", {}).get("swot") or {}).get("status") == "available":
            r["status"] = "used"
        if r["id"] == "gpm_imerg":
            if precipitation and precipitation.get("status") == "available":
                r["status"] = "used"
            elif precipitation and precipitation.get("reason"):
                r["status_note"] = precipitation["reason"]
            else:
                r["status_note"] = "Requested for each analysis; values appear only when NASA GES DISC returns data."
    return {"nasa": nasa, "other": OTHER_RESOURCES}
