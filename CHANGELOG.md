# Changelog

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
