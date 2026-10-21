# Changelog

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
