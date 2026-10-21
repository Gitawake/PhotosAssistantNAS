# Source publication and binary distribution

[English](distribution.md) | [简体中文](distribution.zh-CN.md)

## Current status: source only

Publish project source, documentation, tests, dependency lock and license texts. Do not upload the personal build's installer tar, downloaded SPKs or runtime binaries as GitHub release assets. The CI workflow checks and packages source; it does not publish binaries or deploy to a NAS.

The pinned FFmpeg binary was inspected and contains `--enable-gpl`, `--enable-version3` and **`--enable-nonfree`**. FFmpeg documents that a nonfree configuration can produce an unredistributable binary. Adding source links or license texts does not resolve this restriction. Local building for personal use is distinct from redistribution.

## Before considering a public binary release

1. Replace the pinned nonfree FFmpeg binary with a build whose complete dependency set permits redistribution. Revalidate decoding, HDR conversion, AVC/AAC output and private dynamic linking on the supported NAS.
2. Inventory every included library and data file, recording versions, origin, license, patches and build configuration. Review the ImageMagick and auxiliary library dependency trees too.
3. Provide the exact matching corresponding source and necessary build scripts for all applicable copyleft components, including local changes. A link to the latest upstream branch or several license files is insufficient.
4. Preserve required notices, attribution and license texts for every component. Project MIT terms apply to project code, not automatically to the runtime bundle.
5. Generate provenance, checksums and an auditable build manifest, then perform a clean build and compatibility test before manually releasing an artifact.

Open-source licenses and codec patent permissions are separate questions. The project does not promise a patent license for every codec or deployment jurisdiction.

Primary documentation:

- [FFmpeg license and distribution considerations](https://www.ffmpeg.org/legal.html)
- [FFmpeg configuration and license details](https://ffmpeg.org/doxygen/4.0/md_LICENSE.html)
- [ImageMagick license](https://imagemagick.org/license/)
