"""Compatibility checks between two observations before change detection.

Errors block the analysis; warnings are reported alongside results.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.preprocessing.georeferencing import footprint_intersection_fraction


@dataclass
class Compatibility:
    ok: bool = True
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)

    def error(self, code: str, message: str) -> None:
        self.ok = False
        self.errors.append({"code": code, "message": message})

    def warn(self, code: str, message: str) -> None:
        self.warnings.append({"code": code, "message": message})

    def as_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def check_pair(
    earlier: dict,
    later: dict,
    frequency: str,
    polarization: str,
    study_area: dict | None = None,
    allow_cross_geometry: bool = False,
) -> Compatibility:
    """Metadata-level checks. `earlier`/`later` are observation registry records."""
    c = Compatibility()
    if earlier["id"] == later["id"]:
        c.error("same_observation", "Earlier and later observations are the same acquisition.")
        return c
    if earlier.get("sensor") != later.get("sensor"):
        c.error(
            "sensor_mismatch",
            f"Cannot difference {earlier.get('sensor')} and {later.get('sensor')} backscatter directly: "
            "wavelength, calibration and geometry differ. Compare independently derived change maps instead.",
        )
    if earlier.get("product_type") != later.get("product_type"):
        c.error("product_mismatch", f"Product types differ ({earlier.get('product_type')} vs {later.get('product_type')}).")
    if earlier["start_time"] >= later["start_time"]:
        c.error("date_order", f"The earlier observation ({earlier['date']}) is not before the later one ({later['date']}).")

    pol = polarization.upper()
    for name, o in (("earlier", earlier), ("later", later)):
        pols = (o.get("polarizations") or {}).get(frequency, [])
        if pol not in pols:
            c.error("polarization_unavailable", f"{pol} is not available in frequency {frequency} of the {name} observation ({o['date']}); available: {pols or 'none'}.")

    bw_e = (earlier.get("range_bandwidth_mhz") or {}).get(frequency)
    bw_l = (later.get("range_bandwidth_mhz") or {}).get(frequency)
    if bw_e and bw_l and bw_e != bw_l:
        c.warn("bandwidth_differs", f"Range bandwidth differs ({bw_e} vs {bw_l} MHz); resolution and speckle statistics differ.")

    same_geom = earlier.get("track") == later.get("track") and earlier.get("pass_direction") == later.get("pass_direction")
    if not same_geom:
        msg = (
            f"Acquisition geometry differs (track {earlier.get('track')} {earlier.get('pass_direction')} vs "
            f"track {later.get('track')} {later.get('pass_direction')}). Incidence-angle and look-direction "
            "differences change backscatter independently of the surface."
        )
        if allow_cross_geometry:
            c.warn("geometry_differs", msg)
        else:
            c.error("geometry_differs", msg + " Select observations from the same track and pass direction.")
    elif earlier.get("frame") != later.get("frame"):
        c.warn("frame_differs", "Same track but different frame numbers; overlap may be partial.")

    if earlier.get("product_version") != later.get("product_version"):
        c.warn("version_differs", f"Processing versions differ ({earlier.get('product_version')} vs {later.get('product_version')}).")

    fe, fl = earlier.get("footprint"), later.get("footprint")
    if fe and fl:
        frac = footprint_intersection_fraction(fe, fl)
        if frac == 0:
            c.error("no_overlap", "The two observation footprints do not overlap.")
        if study_area is not None:
            from shapely.geometry import shape

            sa = shape(study_area["geometry"])
            cov = min(shape(fe).intersection(sa).area, shape(fl).intersection(sa).area) / sa.area if sa.area else 0
            if cov == 0:
                c.error("study_area_not_covered", "The study area is not covered by both observations.")
            elif cov < 0.5:
                c.warn("partial_coverage", f"Only {cov:.0%} of the study area is covered by both footprints.")
    return c


def check_valid_overlap(valid_fraction: float, minimum: float, c: Compatibility) -> None:
    """Pixel-level check after alignment."""
    if valid_fraction < minimum:
        c.error(
            "insufficient_valid_pixels",
            f"Only {valid_fraction:.1%} of study-area pixels are valid in both observations (minimum {minimum:.0%}).",
        )
    elif valid_fraction < 0.8:
        c.warn("missing_data", f"{1 - valid_fraction:.1%} of study-area pixels lack valid data in at least one observation.")
