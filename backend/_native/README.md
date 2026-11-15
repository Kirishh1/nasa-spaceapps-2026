# Vendored native libraries

The `rasterio` Linux wheels bundle GDAL but expect the system to provide `libexpat.so.1`.
Vercel's Python runtime (Amazon Linux 2023) does not ship it, so importing rasterio failed with
`ImportError: libexpat.so.1: cannot open shared object file`.

`libexpat.so.1` here is `/usr/lib64/libexpat.so.1.12.3` from the official Amazon Linux 2023 package
`expat-2.8.3-1.amzn2023.0.1.x86_64.rpm` (MIT licence), downloaded from
`https://cdn.amazonlinux.com/al2023/blobstore/16f4c8e1fe525d9d3e8c8ef5387448d2587d5a34ad062efb6513a6250eda3778/`
and verified against the SHA-256 in the repository index (`16f4c8e1…a3778`).

`backend/__init__.py` loads it with `RTLD_GLOBAL` only on Linux x86-64 when the system has no
`libexpat.so.1`, before any module imports rasterio. Other platforms are unaffected.
