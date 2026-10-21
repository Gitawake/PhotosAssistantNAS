# Changelog

[English](CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md)

## 0.5.4 — drain pending work without idle waits

- Continue immediately after processing tasks or while historical pages remain; wait 60 seconds only when the scan reaches idle. Increase each batch from 2 to 20 successful tasks while keeping sequential decoding and existing CPU/memory limits.
- Back off unavailable API contexts for 60 seconds independently; failed media retain their one-hour retry delay.

## 0.5.3 — skip compatible originals and scan historical media

- Probe original video streams through the read-only descriptor before transcoding. Conservative SDR H.264 MP4/M4V with AAC-LC audio can keep the original and generate missing thumbnails only. Existing compatibility copies are retained.
- Cache source compatibility against item identity and Photos cache key; recheck changed items. This does not mark Photos conversion status as ready or guarantee playback on every client.
- Scan the full Browse.Item collection instead of the limited RecentlyAdded collection, with a fresh historical cursor.

## 0.5.2 — limited-range compatibility videos

- Convert full-range input pixels to limited range and signal the output range explicitly, preserving strict video validation.
- Record fixed decoder failure categories without exposing media paths or raw decoder errors.

## 0.5.1 — direct HEIF image input

- Read HEIC/HEIF/HIF through an inherited read-only descriptor and libheif reader callbacks; import pixels directly into MagickWand. No source-image staging or encoded intermediate.
- Preserve primary-image transformations, high-bit-depth sample scaling, thumbnail geometry and ICC profiles. Disable disk/mapped image caches; apply dimension/profile/cache limits and abort safely when resources are unavailable.
- Keep Photos publication, original identity checks, isolated decoding, video behavior and uninstall retention. No compiler, extra SPK or PyPI dependency is required.

## 0.5.0 — direct video input

- Video decoding/transcoding reads an inherited read-only original descriptor using FFmpeg's seekable `fd:` protocol. No full source-video copy, Btrfs clone or original permission change.
- Remove the 8 GiB input cap. Reserve space from expected outputs and monitor free space during decoding; preserve duration, CPU and memory limits.
- Update pinned private dependencies to the latest available validated DSM x64 builds; resolve additional video-library dependencies without installing upstream packages.
- Keep private image staging, source mutation checks and retained Photos outputs on uninstall.

## 0.4.0 — experimental source preparation

- SSH deployment with a private runtime and dedicated systemd service.
- NAS-local Photos integration without password, OTP, stored session or Container Manager.
- Isolated HEIC/HEVC thumbnail and AVC/AAC compatible-copy generation.
- Uninstall retains original media and previews already accepted by Photos.
- GitHub-hosted SSH bootstrap with a pinned source revision, NAS-side dependency verification/build and an online uninstall entry. No Releases.
- Prominent data-corruption/loss disclaimer in documentation and installer output.
- Clean source layout and a build from locked original dependencies; no dependency on old private SPK outputs.
- Source-only CI and export checks. Public binary distribution remains blocked by the pinned nonfree FFmpeg configuration and incomplete dependency compliance audit.

This entry documents source preparation; it does not assert that a GitHub release has been published.
