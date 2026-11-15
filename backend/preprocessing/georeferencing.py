"""CRS / footprint helpers."""
from __future__ import annotations

import numpy as np
from rasterio.crs import CRS
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from shapely.geometry import box, mapping, shape

WGS84 = CRS.from_epsg(4326)


def bbox_polygon(bbox: tuple[float, float, float, float]) -> dict:
    return mapping(box(*bbox))


def footprint_intersection_fraction(a: dict, b: dict) -> float:
    """Fraction of footprint `a` covered by footprint `b` (both lon/lat GeoJSON)."""
    ga, gb = shape(a), shape(b)
    if ga.area == 0:
        return 0.0
    return ga.intersection(gb).area / ga.area


def polygon_mask(geom_lonlat: dict, crs, transform, shape_hw) -> np.ndarray:
    """Boolean mask, True inside the polygon, for a raster grid."""
    g = transform_geom(WGS84, crs, geom_lonlat)
    return geometry_mask([g], out_shape=shape_hw, transform=transform, invert=True)


def pixel_area_m2(transform, crs) -> float:
    if crs is None or not CRS.from_user_input(crs).is_projected:
        raise ValueError("Pixel-area statistics require a projected CRS in metres")
    return abs(transform.a * transform.e - transform.b * transform.d)
