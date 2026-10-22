# AME reference and color pipeline

[English](ame-reference.md) | [简体中文](ame-reference.zh-CN.md)

The official AME HEVC/AAC payload was inspected offline as an interoperability reference. The 1.1.0-51005 x86_64 payload contains FFmpeg 4.1-family binaries and libraries, ImageMagick 6 Q8, libheif 1.12.0, libde265 and private VAAPI/DRM libraries. Its FFmpeg configuration enables VAAPI and H.264 encoding. This confirms component roles, not the exact command line used by Photos or complete HDR/Dolby Vision behavior.

PhotosAssistantNAS keeps its pinned open-source runtimes and independent queue. No AME executable, proprietary library, activation code or license implementation is included. The image path already uses libheif/libde265 plus ImageMagick; it is unchanged by 0.6.1.

## Video processing since 0.6.1

1. Read the original through a seekable read-only descriptor; keep existing source-change checks and compatible-original decisions.
2. Reduce known frame rates above 30 before expensive filtering. Do not increase lower or unknown rates.
3. On eligible VAAPI jobs, apply supported quarter-turn rotation and bounded scaling on the GPU. Portrait output stays within 720×1280; landscape within 1280×720; no upscaling. Full-range inputs and arbitrary-angle rotations do not enter this prefilter path.
4. For HLG/PQ, download the bounded frame and use the pinned FFmpeg's SIMD `tonemapx` (Hable, BT.709 limited range). If unavailable or failing, try the zscale/tonemap path. Software fallback also bounds resolution before color work. Full-range conversion stays on the CPU because the tested direct VPP range-conversion path did not change the pixels correctly.
5. Encode using the selected backend, then validate codec, output duration, range/BT.709 tags and absence of unapplied rotation. Invalid/partial output is discarded before retry. Only validated results are eligible for Photos submission.

The HDR path explicitly uses the compatible HDR base layer (`apply_dovi=0` in tonemapx). It does not claim complete Dolby Vision dynamic reshaping, and existing accepted resources are not regenerated automatically. Different filter order/implementation can produce different pixels; this is not a promise of pixel identity with AME, the old project pipeline or every client.

OpenCL HLG processing was separately demonstrated on one N100 NAS, but requires an additional compatible Intel compute-runtime/IGC stack. Version 0.6.1 deliberately uses the existing runtime: it does not bundle or enable that experimental stack. The low-privilege/network sandbox and resource limits remain active.

Logs identify `video-prefilter=vaapi`, `video-color-path=cpu-tonemapx` or `cpu-zscale`, and the existing video backend. Active tone mapping still consumes CPU; this change reduces the work, rather than promising idle CPU usage while processing history.

## Validation

On the development N100 NAS, an unprivileged, network-isolated candidate job processed a whole 28.7567-second 4K/120-fps HLG source in 39.026 seconds, using 40.576 child-process CPU seconds and approximately 187 MiB peak child RSS. Output was 720×1280, 30 fps, H.264/yuv420p, AAC-LC stereo, limited-range BT.709; duration 28.766667 seconds. Full output decoding passed and the source fingerprint remained unchanged. The production log for an earlier run of the same source recorded approximately 15 minutes. This is an illustrative comparison across runs with a changed filter pipeline and concurrent NAS work, not an equal-quality controlled benchmark.

Synthetic full-range and limited-range black/white sources both produced center luma values 16/235; full-range conversion stayed on the CPU. An unavailable test render device triggered the real software fallback and produced decodable output. Unit tests cover ordering, no low-rate upsampling, full-range/arbitrary-rotation exclusion, tag rejection and removal of a partial tonemapx result before legacy retry. These tests do not establish all-hardware or full Dolby Vision color equivalence.

## References and scope

- [Official AME archive](https://archive.synology.com/download/Package/CodecPack/3.1.0-3005)
- [Official HEVC/AAC payload](https://global.synologydownload.com/download/Package/spk/CodecPack_HEVC_AAC/1.1.0-51005/CodecPack_HEVC_AAC-x86_64-1.1.0-51005.spk), SHA-256 `77f0f544f24724397ddda6351b27df69a1256f70ff97cbae80f12e2db1ae0e1b`
- [Jellyfin-FFmpeg SIMD tonemapx work](https://github.com/jellyfin/jellyfin-ffmpeg)
- [Hardware support and limitations](hardware.md)

The old package's Intel i965 driver is not substituted for the current N100 iHD runtime. Other GPU backends retain their documented capability and testing limitations.
