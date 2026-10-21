# Hardware acceleration

[English](hardware.md) | [简体中文](hardware.zh-CN.md)

Version 0.5.6 adds capability-based video acceleration. Image/thumbnail processing remains unchanged. Decoding stays unprivileged and network-isolated; only the required device groups are granted to the video job. No device permissions, kernel drivers or other packages are changed.

| Backend | Selection | Validation / requirements |
|---|---|---|
| VAAPI, Intel | Automatic when the encoder, render device and private driver exist | Tested on the development NAS with Intel N100; private iHD driver is extracted from the pinned dependency |
| VAAPI, AMD | Automatic when the encoder, render device and a trusted installed `radeonsi` driver exist | Implemented, not tested on AMD hardware; no AMD driver is bundled |
| Intel QSV | Select `qsv` explicitly | Implemented; initialization failed on the development NAS with its current MFX runtime, so software fallback applies there |
| NVIDIA NVENC | Automatic when the FFmpeg encoder and NVIDIA device nodes exist | Implemented, not tested on NVIDIA; the current pinned FFmpeg does **not** include NVENC, so it cannot activate this path. Requires a compatible NVENC-enabled private FFmpeg build and installed NVIDIA userspace/kernel drivers |
| Software | Automatic fallback or select explicitly | Existing libx264 path |

Detection never assumes that an encoder listing means the device works. Initialization, encoding, range/codec validation or duration failures trigger software retry. Partial hardware output is removed before retrying, and Photos receives only validated output. CPU and memory limits remain active.

Eligible SDR VAAPI/QSV jobs keep decoded frames on the GPU for scaling and encoding. HDR tone mapping and full-range pixel conversion retain CPU filters; rotation/driver incompatibilities may fall back to software. Hardware output uses a different rate-control configuration from libx264, so size/quality and speed can differ; acceleration is not guaranteed for every file.

To force a backend, create a root-owned, non-group/world-writable `hardware.json` in the installation's `state` directory:

```json
{"backend":"software"}
```

Allowed values: `auto` (default), `software`, `vaapi`, `qsv`, `nvenc`. The coordinator reads this at the start of each new video job. Unsupported selections fall back to software; they do not install missing drivers. Logs identify `video-backend=...` and `hardware-fallback=software`.

Testing used read-only original descriptors and temporary output; original fingerprints were checked. A 21.6-second SDR HEVC sample took approximately 5.6 seconds with the VAAPI GPU-scaling path, versus 33 seconds in an earlier software run on the same NAS. This is illustrative, not an equal-quality controlled benchmark. Full- and limited-range black/white samples both produced limited-range luma values of 16/235; full-range input deliberately uses CPU range conversion because the tested VPP path did not convert those pixels correctly.

These are video-processing backends, not a system-wide AME replacement. Existing Photos outputs are retained on uninstall.
