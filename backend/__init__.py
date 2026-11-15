"""SAR-Pulse backend package."""


def _preload_native_libs() -> None:
    """Make libexpat.so.1 available to rasterio's bundled GDAL on minimal Linux runtimes (e.g. Vercel).

    See backend/_native/README.md. No-op on other platforms or when the system already provides it.
    """
    import ctypes
    import platform
    import sys
    from pathlib import Path

    if not sys.platform.startswith("linux") or platform.machine() not in ("x86_64", "AMD64"):
        return
    try:
        ctypes.CDLL("libexpat.so.1", mode=ctypes.RTLD_GLOBAL)
        return
    except OSError:
        pass
    vendored = Path(__file__).with_name("_native") / "libexpat.so.1"
    if vendored.exists():
        ctypes.CDLL(str(vendored), mode=ctypes.RTLD_GLOBAL)


_preload_native_libs()
