# Acknowledgements and project origins

[English](ACKNOWLEDGEMENTS.md) | [简体中文](ACKNOWLEDGEMENTS.zh-CN.md)

PhotosAssistantNAS builds on media tools and packaging work maintained by the open-source community. Thank you to the authors, maintainers, and contributors below. Attribution expresses origin and appreciation, not endorsement of this project.

## Inspiration

The initial direction came from [octavianx/synology-photos-server-side-thumbnailgen](https://github.com/octavianx/synology-photos-server-side-thumbnailgen): generating Synology Photos media previews on the NAS to reduce dependence on client processing.

The reference revision is `11ed028780d51d00f8056b123b22bc716ba6a0ec`. Its notice is **Copyright (c) 2026 octavianx, MIT License**. Copyright and permission notices are retained in [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). Thank you to octavianx and the upstream contributors for exploring and sharing this approach.

The current SSH deployment, local-interface coordination without Photos login, isolated decoding, read-only descriptor video input, and uninstall mechanism are this project's present implementation. Inspiration does not imply identical system integration or responsibility by upstream authors for this project's data safety or compatibility.

## Tools and packaging used directly

| Project / team | Use in this project | Source and license information |
| --- | --- | --- |
| FFmpeg project and contributors | FFprobe inspection, video thumbnails, H.264/AAC compatibility copies, seekable read-only `fd:` input | [Website](https://ffmpeg.org/) · [Licensing](https://ffmpeg.org/legal.html) |
| ImageMagick Studio and contributors | In-memory MagickWand resizing and JPEG thumbnails | [Website](https://imagemagick.org/) · [License](https://imagemagick.org/license/) |
| SynoCommunity maintainers and contributors | Original DSM builds of media tools and private shared libraries, and package recipes | [spksrc](https://github.com/SynoCommunity/spksrc) · [FFmpeg package](https://synocommunity.com/package/ffmpeg8) · [ImageMagick package](https://synocommunity.com/package/imagemagick) · [Video libraries](https://synocommunity.com/package/synocli-videodriver) |
| Python Software Foundation and Python contributors | Standard library used by installation, uninstall, coordination, and build scripts | [Python](https://www.python.org/) · [License](https://docs.python.org/3/license.html) |
| Linux / systemd projects and contributors | File descriptors, process privilege isolation, service management | [Linux](https://www.kernel.org/) · [systemd](https://systemd.io/) |

Thank you to hgy59 for ImageMagick/libheif adaptation work; see [spksrc PR #6744](https://github.com/SynoCommunity/spksrc/pull/6744). The reference project also lists its background material and acknowledgements in its [Credits](https://github.com/octavianx/synology-photos-server-side-thumbnailgen#credits).

## Underlying media and graphics libraries

Upstream runtimes include or link additional open-source components. The following are representative projects involved in the main functionality. Extracted library files and original package information are recorded in `runtime-manifest.json`; this table is not a complete license-compliance inventory.

| Project | Role | Upstream |
| --- | --- | --- |
| libheif | HEIF/HEIC primary-image decoding, transformations and seekable reader callbacks | [strukturag/libheif](https://github.com/strukturag/libheif) |
| libde265 | HEVC image decoding | [strukturag/libde265](https://github.com/strukturag/libde265) |
| libjpeg-turbo | JPEG encoding and decoding | [libjpeg-turbo](https://github.com/libjpeg-turbo/libjpeg-turbo) |
| x264 | H.264 encoding | [VideoLAN x264](https://www.videolan.org/developers/x264.html) |
| libva / libdrm | User-space shared libraries required by the video tools | [libva](https://github.com/intel/libva) · [libdrm](https://gitlab.freedesktop.org/mesa/drm) |
| oneVPL / Media SDK | Media-interface runtimes required by the FFmpeg build | [oneVPL](https://github.com/oneapi-src/oneVPL) · [Media SDK](https://github.com/Intel-Media-SDK/MediaSDK) |
| shaderc / glslang / SPIRV-Tools | Dependencies of the upstream FFmpeg graphics-processing build | [shaderc](https://github.com/google/shaderc) · [glslang](https://github.com/KhronosGroup/glslang) · [SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools) |

This project does not implement these codecs or claim ownership of third-party work. Each component retains its own license and copyright; this project's MIT license does not cover third-party runtimes. See [THIRD_PARTY.md](THIRD_PARTY.md), [vendor/lock.json](vendor/lock.json), and [distribution requirements](docs/distribution.md) for restrictions, original packages, pinned versions, and checksums.

Synology Photos is the target platform, not a dependency supplied or redistributed by this project. Thank you to Synology for its photo product. This project is independent of Synology and is not endorsed by it.
