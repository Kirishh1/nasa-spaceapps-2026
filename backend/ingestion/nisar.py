"""NISAR L2 GCOV (Geocoded Polarimetric Covariance) reader.

GCOV covariance diagonal terms (e.g. HHHH, HVHV) are radiometrically terrain-corrected backscatter
in *linear power* units (gamma-naught by default) on a map-projected grid (UTM / polar stereographic).
We convert selected terms to Cloud-Optimized GeoTIFFs cropped to the study area for map display and analysis.

HDF5 paths follow the NISAR GCOV product specification and are checked at runtime by
`inspect_gcov`; anything missing is reported rather than assumed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

ROOT = "/science/LSAR"
IDENT = f"{ROOT}/identification"
GRIDS = f"{ROOT}/GCOV/grids"
PROC_PARAMS = f"{ROOT}/GCOV/metadata/processingInformation/parameters"

MASK_FILL = 255  # outside the radar acquisition extent
MASK_PARTIAL = 0  # sample built from partially focused / invalid radar samples (GCOV spec 1.6 mask description)


def _read(ds: h5py.Dataset | None) -> Any:
    if ds is None:
        return None
    v = ds[()]
    if isinstance(v, bytes):
        return v.decode(errors="replace").strip()
    if isinstance(v, np.ndarray) and v.dtype.kind in ("S", "O"):
        return [x.decode(errors="replace").strip() if isinstance(x, bytes) else str(x) for x in v.ravel()]
    if isinstance(v, np.generic):
        return v.item()
    return v


def _get(f: h5py.File, path: str) -> Any:
    return _read(f[path]) if path in f else None


def _attr(ds: h5py.Dataset, name: str) -> Any:
    v = ds.attrs.get(name)
    if isinstance(v, bytes):
        return v.decode(errors="replace")
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, np.ndarray) and v.size == 1:
        return v.item()
    return v


def _epsg(grp: h5py.Group) -> int | None:
    if "projection" not in grp:
        return None
    proj = grp["projection"]
    code = _attr(proj, "epsg_code")
    if code is None:
        code = _read(proj)
    return int(code) if code is not None else None


def open_source(source):
    """h5py-openable object for a local path or an https URL (streamed with Earthdata auth, only needed bytes)."""
    if isinstance(source, str) and source.startswith("https://"):
        import earthaccess

        fs = earthaccess.get_fsspec_https_session()
        return fs.open(source, block_size=8 * 1024 * 1024, cache_type="blockcache")
    return source


def inspect_gcov(path) -> dict[str, Any]:
    """Return metadata extracted from the GCOV file, with a list of any expected-but-missing items."""
    name = str(path).rsplit("/", 1)[-1]
    missing: list[str] = []
    with h5py.File(open_source(path), "r") as f:
        ident = {}
        for key in (
            "productType", "productVersion", "productSpecificationVersion", "missionId", "radarBand",
            "absoluteOrbitNumber", "trackNumber", "frameNumber", "orbitPassDirection", "lookDirection",
            "zeroDopplerStartTime", "zeroDopplerEndTime", "processingDateTime", "listOfFrequencies",
            "isFullFrame", "isUrgentObservation", "boundingPolygon", "granuleId",
        ):
            p = f"{IDENT}/{key}"
            if p in f:
                ident[key] = _read(f[p])
            else:
                missing.append(p)

        freqs: dict[str, Any] = {}
        if GRIDS not in f:
            missing.append(GRIDS)
        else:
            for fname in f[GRIDS]:
                if not fname.startswith("frequency"):
                    continue
                g = f[f"{GRIDS}/{fname}"]
                x = g["xCoordinates"][()] if "xCoordinates" in g else None
                y = g["yCoordinates"][()] if "yCoordinates" in g else None
                terms = [k for k in g if isinstance(g[k], h5py.Dataset) and len(k) == 4 and k.isupper() and g[k].ndim == 2]
                term_info = {}
                for t in terms:
                    ds = g[t]
                    term_info[t] = {
                        "shape": list(ds.shape),
                        "dtype": str(ds.dtype),
                        "units": _attr(ds, "units"),
                        "description": _attr(ds, "description"),
                        "fill_value": _attr(ds, "_FillValue"),
                    }
                freqs[fname[-1]] = {
                    "epsg": _epsg(g),
                    "x_spacing": float(_read(g["xCoordinateSpacing"])) if "xCoordinateSpacing" in g else (float(x[1] - x[0]) if x is not None else None),
                    "y_spacing": float(_read(g["yCoordinateSpacing"])) if "yCoordinateSpacing" in g else (float(y[1] - y[0]) if y is not None else None),
                    "x_first": float(x[0]) if x is not None else None,
                    "y_first": float(y[0]) if y is not None else None,
                    "width": int(len(x)) if x is not None else None,
                    "length": int(len(y)) if y is not None else None,
                    "covariance_terms": terms,
                    "list_of_polarizations": _read(g["listOfPolarizations"]) if "listOfPolarizations" in g else None,
                    "terms": term_info,
                    "has_mask": "mask" in g,
                    "has_number_of_looks": "numberOfLooks" in g,
                    "has_rtc_gamma_to_sigma": "rtcGammaToSigmaFactor" in g,
                }

        params = {}
        if PROC_PARAMS in f:
            for k, v in f[PROC_PARAMS].items():
                if isinstance(v, h5py.Dataset) and v.size <= 16:
                    params[k] = _read(v)
    return {
        "file": name,
        "identification": ident,
        "frequencies": freqs,
        "processing_parameters": params,
        "missing_paths": missing,
    }


def _grid_transform(x: np.ndarray, y: np.ndarray):
    """Affine transform from pixel-center coordinate vectors."""
    dx = float(x[1] - x[0])
    dy = float(y[1] - y[0])  # negative for north-up
    return from_origin(float(x[0]) - dx / 2, float(y[0]) - dy / 2, dx, -dy) if dy < 0 else None, dx, dy


def _multilook(a: np.ndarray, k: int) -> np.ndarray:
    """k×k block mean in linear power; a block with fewer than half valid samples becomes NaN."""
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    valid = np.isfinite(b)
    n = valid.sum(axis=(1, 3))
    s = np.where(valid, b, 0).sum(axis=(1, 3))
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (s / n).astype("float32")
    out[n < (k * k) / 2] = np.nan
    return out


def export_term_cog(
    h5_path: str | Path,
    out_path: str | Path,
    frequency: str = "A",
    term: str = "HHHH",
    bbox_lonlat: tuple[float, float, float, float] | None = None,
    multilook: int = 1,
) -> dict[str, Any]:
    """Write one covariance term (linear power, float32) to a COG, cropped to bbox_lonlat if given.

    Invalid pixels (mask == 255, non-finite, or <= 0) are written as NaN (nodata).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(open_source(h5_path), "r") as f:
        g = f[f"{GRIDS}/frequency{frequency}"]
        if term not in g:
            raise KeyError(f"{term} not present in frequency{frequency}; available: {[k for k in g if len(k) == 4 and k.isupper()]}")
        x = g["xCoordinates"][()]
        y = g["yCoordinates"][()]
        epsg = _epsg(g)
        if epsg is None:
            raise ValueError("GCOV grid has no projection EPSG code")
        transform, dx, dy = _grid_transform(x, y)
        if transform is None:
            raise ValueError("Unexpected south-up GCOV grid; not supported")
        r0, r1, c0, c1 = 0, len(y), 0, len(x)
        if bbox_lonlat is not None:
            w, s, e, n = transform_bounds(CRS.from_epsg(4326), CRS.from_epsg(epsg), *bbox_lonlat, densify_pts=21)
            cols = np.where((x >= w) & (x <= e))[0]
            rows = np.where((y >= s) & (y <= n))[0]
            if cols.size == 0 or rows.size == 0:
                raise ValueError("Study area does not intersect this observation's grid")
            r0, r1, c0, c1 = int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1
        data = g[term][r0:r1, c0:c1].astype("float32")
        invalid = ~np.isfinite(data) | (data <= 0)
        if "mask" in g:
            mask = g["mask"][r0:r1, c0:c1]
            invalid |= (mask == MASK_FILL) | (mask == MASK_PARTIAL)
        data[invalid] = np.nan
        # upper-left corner of the first pixel (from native pixel-centre coordinates)
        x_ul, y_ul = float(x[c0]) - dx / 2, float(y[r0]) - dy / 2
        if multilook > 1:
            data, dx, dy = _multilook(data, multilook), dx * multilook, dy * multilook
            invalid = ~np.isfinite(data)
        units = _attr(g[term], "units")
        median_looks = None
        if "numberOfLooks" in g:
            nl = g["numberOfLooks"][r0:r1, c0:c1].astype("float32")
            if multilook > 1:
                # Adjacent 10 m GCOV samples are correlated, so k*k averaging adds fewer than k*k
                # independent looks. We keep the native value: a conservative (lower) ENL for the Lee filter.
                nl = _multilook(nl, multilook)
            nl = nl[np.isfinite(nl) & (nl > 0) & ~invalid]
            median_looks = float(np.median(nl)) if nl.size else None
        sub_transform = from_origin(x_ul, y_ul, dx, -dy)

    profile = {
        "driver": "COG",
        "dtype": "float32",
        "count": 1,
        "width": data.shape[1],
        "height": data.shape[0],
        "crs": CRS.from_epsg(epsg),
        "transform": sub_transform,
        "nodata": np.nan,
        "compress": "deflate",
        "predictor": 3,
        "overview_resampling": "average",
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data, 1)
        dst.update_tags(1, units=str(units), term=term, frequency=frequency, quantity="linear backscatter power")
    valid = int(np.count_nonzero(~invalid))
    return {
        "path": str(out_path),
        "term": term,
        "frequency": frequency,
        "epsg": epsg,
        "pixel_spacing_m": [abs(dx), abs(dy)],
        "shape": list(data.shape),
        "valid_fraction": valid / data.size if data.size else 0.0,
        "units": units,
        "median_looks": median_looks,
        "multilook": multilook,
    }


def write_metadata_sidecar(meta: dict, out_path: str | Path) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(meta, indent=2, default=str))
