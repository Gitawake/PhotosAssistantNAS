# Changelog

[English](CHANGELOG.md) | [简体中文](CHANGELOG.zh-CN.md)

## Main branch documentation

- Identify 0.6.1 as the current primary baseline, with its existing experimental/version limits.
- Document media selection, preview/video task separation, event triggers, retained resources and AME research boundaries. Runtime behavior and pinned dependencies are unchanged.

## 0.6.1 — bounded HDR color processing

- Reduce high-frame-rate inputs before expensive filters. On eligible VAAPI jobs, rotate and resize on the GPU before CPU HDR conversion; keep full-range conversion on the CPU.
- Prefer the pinned FFmpeg's SIMD `tonemapx` for HDR base-layer conversion, with the zscale/tonemap path as fallback. Validate output BT.709/range tags, unapplied rotation, codec and duration. No proprietary AME binaries or new runtime dependencies are included. See [AME reference and color pipeline](docs/ame-reference.md).

## 0.6.0 — event-driven persistent queues

- Replace repeated history scans with Linux inotify, a separate collector and a private SQLite queue. Wait for stable writes and query only the affected Photos folder.
- Preserve preview priority, GPU backends and delayed retries. Reconcile on startup, restart, explicit requests or event overflow; completing video batches never starts a full rescan. See [event processing](docs/events.md).

## 0.5.6 — optional GPU video backends

- Add capability-based Intel/AMD VAAPI, Intel QSV and NVIDIA NVENC dispatch with validated software fallback. Intel VAAPI is tested; AMD/NVIDIA remain unverified, current pinned FFmpeg lacks NVENC, and QSV initialization fails on the development NAS.
- Bundle private Intel userspace GPU drivers and their dependency closure; keep low-privilege/network isolation and resource limits. GPU-scale eligible SDR videos while retaining CPU HDR/full-range conversion and strict output checks. See [hardware support](docs/hardware.md).

## 0.5.5 — prioritize missing previews

- Drain missing-preview pages before starting compatibility-video work. Preview jobs never transcode a video; process at most two video jobs before scanning previews again. Keep sequential decoding and existing resource limits.
- Use independent scan cursors and media retry delays for the two phases. Store the accepted Photos cache key to avoid redundant compatibility probes after thumbnail publication.

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
