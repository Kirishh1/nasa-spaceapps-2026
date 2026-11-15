"""Align two rasters onto a common grid (the earlier observation's grid)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds


@dataclass
class AlignedPair:
    earlier: np.ndarray
    later: np.ndarray
    transform: object
    crs: object
    resampled: bool
    notes: list[str]


def align_to_reference(earlier_path: str, later_path: str) -> AlignedPair:
    """Resample the later raster (linear power) onto the earlier raster's grid.

    Resampling happens in linear power with bilinear interpolation. If the grids are already
    identical (same CRS, transform and shape) no resampling is performed.
    """
    notes: list[str] = []
    with rasterio.open(earlier_path) as ref, rasterio.open(later_path) as src:
        e = ref.read(1).astype("float32")
        same_grid = (
            ref.crs == src.crs and ref.shape == src.shape and ref.transform.almost_equals(src.transform, precision=1e-6)
        )
        if ref.crs != src.crs:
            notes.append(f"CRS differs ({src.crs} -> {ref.crs}); later observation reprojected.")
        if same_grid:
            l = src.read(1).astype("float32")
            resampled = False
        else:
            # Integer-pixel shift on the same CRS & spacing: use a window read (no interpolation).
            if (
                ref.crs == src.crs
                and abs(ref.transform.a - src.transform.a) < 1e-6
                and abs(ref.transform.e - src.transform.e) < 1e-6
            ):
                win = from_bounds(*ref.bounds, transform=src.transform)
                off_c, off_r = win.col_off, win.row_off
                if abs(off_c - round(off_c)) < 1e-3 and abs(off_r - round(off_r)) < 1e-3:
                    l = src.read(1, window=win.round_offsets().round_lengths(), boundless=True, fill_value=np.nan).astype("float32")
                    if l.shape != e.shape:
                        l = l[: e.shape[0], : e.shape[1]]
                        pad = np.full(e.shape, np.nan, "float32")
                        pad[: l.shape[0], : l.shape[1]] = l
                        l = pad
                    notes.append("Grids share CRS and spacing; later observation windowed onto earlier grid without interpolation.")
                    return AlignedPair(e, l, ref.transform, ref.crs, False, notes)
            l = np.full(e.shape, np.nan, dtype="float32")
            reproject(
                source=rasterio.band(src, 1), destination=l,
                src_transform=src.transform, src_crs=src.crs, src_nodata=np.nan,
                dst_transform=ref.transform, dst_crs=ref.crs, dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
            resampled = True
            notes.append("Later observation bilinearly resampled (linear power) onto earlier grid.")
        return AlignedPair(e, l, ref.transform, ref.crs, resampled, notes)
