"""Single source of truth for the data resources SAR-Pulse uses, served at GET /api/sources.

Identifiers were checked against NASA CMR on 2026-11-15. ``role`` says what the resource does in the
app; ``status`` says whether it actually contributed (``used``), is wired in but returned nothing
(``integrated``), or is not used (``not_used``). Never mark something ``used`` that the app does not use.
"""
from __future__ import annotations

NASA_RESOURCES = [
    {
        "id": "nisar_gcov",
        "name": "NISAR L2 GCOV, Geocoded Polarimetric Covariance (Validated, Version 1)",
        "short_name": "NISAR_L2_GCOV_V1",
        "identifier": "CMR collection C3622241360-ASF",
        "provider": "NASA–ISRO NISAR mission; distributed by NASA's Alaska Satellite Facility DAAC (ASF)",
        "role": "Primary data. Every radar frame, change map, statistic and potential-inundation flag "
                "is computed from these L-band backscatter observations (HH and HV, frequency A).",
        "status": "used",
        "links": [
            {"label": "NASA Earthdata catalog", "url": "https://www.earthdata.nasa.gov/data/catalog/asf-nisar-l2-gcov-v1-1"},
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
        "id": "gpm_imerg",
        "name": "GPM IMERG Late Precipitation L3 1 day 0.1° × 0.1° V07",
        "short_name": "GPM_3IMERGDL",
        "identifier": "CMR collection C2723754859-GES_DISC · doi:10.5067/GPM/IMERGDL/DAY/07",
        "provider": "NASA Global Precipitation Measurement mission; distributed by NASA GES DISC",
        "role": "Environmental context: daily area-mean rainfall around the two acquisition dates.",
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
     "role": "Planned C-band comparison. No RCM data was obtained, so nothing from RCM is shown.", "status": "not_used",
     "links": []},
    {"id": "basemaps", "name": "Esri Dark Gray Canvas and World Imagery basemaps", "provider": "Esri and partners",
     "role": "Visual map background only; not used in any calculation.", "status": "used", "links": []},
]


def sources(precipitation: dict | None = None) -> dict:
    """Resource list, with GPM status taken from an analysis result when one is given."""
    nasa = [dict(r) for r in NASA_RESOURCES]
    for r in nasa:
        if r["id"] == "gpm_imerg":
            if precipitation and precipitation.get("status") == "available":
                r["status"] = "used"
            elif precipitation and precipitation.get("reason"):
                r["status_note"] = precipitation["reason"]
            else:
                r["status_note"] = "Requested for each analysis; values appear only when NASA GES DISC returns data."
    return {"nasa": nasa, "other": OTHER_RESOURCES}
