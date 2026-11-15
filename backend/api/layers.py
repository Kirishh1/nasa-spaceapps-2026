"""Layer catalogue: rendering parameters and legends for map tiles."""
from __future__ import annotations

from backend.comparison.disagreement import COMPARISON_LEGEND
from backend.processing.change_detection import CLASS_LEGEND
from backend.processing.inundation import INUNDATION_LEGEND
from backend.processing.water import WATER_CHANGE_LEGEND


def _hex(c: str) -> tuple[int, int, int, int]:
    if c == "transparent":
        return (0, 0, 0, 0)
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)


LAYERS = {
    "earlier_db": {"title": "Earlier NISAR observation", "kind": "continuous", "units": "dB", "rescale": (-25.0, 0.0), "colormap": "greys_r",
                   "description": "Speckle-filtered backscatter of the earlier acquisition"},
    "later_db": {"title": "Later NISAR observation", "kind": "continuous", "units": "dB", "rescale": (-25.0, 0.0), "colormap": "greys_r",
                 "description": "Speckle-filtered backscatter of the later acquisition"},
    "delta_db": {"title": "NISAR backscatter change (ΔB)", "kind": "continuous", "units": "dB", "rescale": (-10.0, 10.0), "colormap": "rdbu_r",
                 "description": "ΔB = B_later − B_earlier; blue = decrease, red = increase"},
    "change_class": {"title": "NISAR change classification", "kind": "categorical", "legend": CLASS_LEGEND,
                     "description": "Pixels whose |ΔB| exceeds the threshold"},
    "inundation": {"title": "Potential inundation-related change", "kind": "categorical", "legend": INUNDATION_LEGEND,
                   "description": "Rule-based indicators consistent with surface-water change (not confirmed floods)"},
    "water_change": {"title": "Open-water change (NISAR)", "kind": "categorical", "legend": WATER_CHANGE_LEGEND,
                     "description": "Open water mapped on each date (Otsu threshold) and how it changed"},
    "cband_change": {"title": "Sentinel-1 C-band change classification", "kind": "categorical", "legend": CLASS_LEGEND,
                     "description": "Same method applied to OPERA RTC-S1 VV backscatter"},
    "lc_agreement": {"title": "L-band vs C-band agreement", "kind": "categorical", "legend": COMPARISON_LEGEND,
                     "description": "Where NISAR and Sentinel-1 change maps agree or disagree (100 m cells)"},
    "jrc_occurrence": {"title": "JRC historical surface water", "kind": "continuous", "units": "% of months", "rescale": (1.0, 100.0), "colormap": "blues",
                       "description": "Reference: how often each pixel was water 1984–2021"},
}

COMPARISON_LAYERS = {"agreement": COMPARISON_LEGEND}


# On the map, "limited change" is a faint wash so the radar frame underneath stays readable.
TILE_ALPHA = {("change_class", 2): 40, ("water_change", 2): 90}  # limited change / persistent water stay see-through


def categorical_cmap(name: str) -> dict[int, tuple[int, int, int, int]]:
    out = {}
    for item in LAYERS[name]["legend"]:
        r, g, b, a = _hex(item["color"])
        out[item["value"]] = (r, g, b, TILE_ALPHA.get((name, item["value"]), a))
    return out
