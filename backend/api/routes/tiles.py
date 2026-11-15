from functools import lru_cache

import numpy as np
import rasterio
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from rasterio.warp import transform as warp_transform
from rio_tiler.colormap import cmap
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import Reader

from backend.api.layers import LAYERS, categorical_cmap
from backend.processing import pipeline

router = APIRouter(tags=["tiles"])


@lru_cache(maxsize=1)
def _empty_png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (256, 256), (0, 0, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _path(aid: str, layer: str):
    if layer not in LAYERS:
        raise HTTPException(404, f"Unknown layer {layer}")
    p = pipeline.layer_path(aid, layer)
    if p is None:
        raise HTTPException(404, f"Layer {layer} not available for analysis {aid}")
    return p


@router.get("/tiles/{aid}/{layer}/{z}/{x}/{y}.png")
def tile(aid: str, layer: str, z: int, x: int, y: int):
    p = _path(aid, layer)
    spec = LAYERS[layer]
    headers = {"Cache-Control": "public, max-age=3600"}
    try:
        with Reader(str(p)) as r:
            if spec["kind"] == "categorical":
                img = r.tile(x, y, z, tilesize=256, resampling_method="nearest")
                cm = categorical_cmap(layer)
                data = img.data[0]
                rgba = np.zeros((256, 256, 4), dtype="uint8")
                for v, c in cm.items():
                    rgba[data == v] = c
                rgba[img.mask == 0] = 0
                import io

                from PIL import Image

                buf = io.BytesIO()
                Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
                return Response(buf.getvalue(), media_type="image/png", headers=headers)
            img = r.tile(x, y, z, tilesize=256, resampling_method="bilinear")
            if layer == "jrc_occurrence":
                img.array.mask |= img.array.data == 0
            img.rescale(in_range=(spec["rescale"],))
            content = img.render(img_format="PNG", colormap=cmap.get(spec["colormap"]))
            return Response(content, media_type="image/png", headers=headers)
    except TileOutsideBounds:
        return Response(_empty_png(), media_type="image/png", headers=headers)


@router.get("/analysis/{aid}/pixel")
def pixel(aid: str, lon: float = Query(...), lat: float = Query(...)):
    r = pipeline.load_result(aid)
    if r is None:
        raise HTTPException(404, f"Unknown analysis {aid}")
    out = {"lon": lon, "lat": lat, "values": {}}
    for layer in r["layers"]:
        p = pipeline.layer_path(aid, layer)
        if p is None:
            out["values"][layer] = None
            continue
        with rasterio.open(p) as src:
            xs, ys = warp_transform("EPSG:4326", src.crs, [lon], [lat])
            row, col = src.index(xs[0], ys[0])
            if not (0 <= row < src.height and 0 <= col < src.width):
                out["values"][layer] = None
                continue
            v = src.read(1, window=((row, row + 1), (col, col + 1)))[0, 0]
            nod = src.nodata
            if (isinstance(nod, float) and np.isnan(nod) and np.isnan(v)) or (nod is not None and not np.isnan(nod) and v == nod):
                out["values"][layer] = None
            else:
                out["values"][layer] = round(float(v), 3) if np.issubdtype(type(v), np.floating) else int(v)
            out["row"], out["col"] = int(row), int(col)
    return out


@router.get("/observations/{obs_id}/tiles/{study_area}/{layer}/{z}/{x}/{y}.png")
def observation_tile(obs_id: str, study_area: str, layer: str, z: int, x: int, y: int):
    """Original (unfiltered) observation backscatter in dB, for previewing frames before analysis."""
    from backend.ingestion import registry

    o = registry.get_observation(obs_id)
    if not o:
        raise HTTPException(404, f"Unknown observation {obs_id}")
    freq, _, term = layer.partition("_")
    rec = registry.processed_layer(o, study_area, freq, term)
    if not rec:
        raise HTTPException(404, f"{layer} not processed for {obs_id} over {study_area}")
    headers = {"Cache-Control": "public, max-age=3600"}
    try:
        with Reader(rec["path"]) as r:
            img = r.tile(x, y, z, tilesize=256, resampling_method="bilinear")
    except TileOutsideBounds:
        return Response(_empty_png(), media_type="image/png", headers=headers)
    arr = img.array
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10 * np.log10(arr.data)
    arr.mask |= ~np.isfinite(db)
    arr.data[...] = np.where(np.isfinite(db), db, -99)
    img.rescale(in_range=((-25.0, 0.0),))
    return Response(img.render(img_format="PNG", colormap=cmap.get("greys_r")), media_type="image/png", headers=headers)
