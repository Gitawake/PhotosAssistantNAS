# Community introduction draft

[English](community-post.md) | [简体中文](community-post.zh-CN.md)

Use the title and body below when introducing the project. This is a draft, not a record of a post already published to a community.

## Title

I built a NAS-side worker for Synology Photos HEIC/HEVC previews — no client Assistant for these tasks

## Body

After Synology moved some HEIC/HEVC processing to end devices, I wanted my NAS to handle preview and compatibility-copy generation again. I made **PhotosAssistantNAS**, an experimental open-source worker for Synology Photos.

Repository: [Gitawake/PhotosAssistantNAS](https://github.com/Gitawake/PhotosAssistantNAS)

It generates missing HEIC/HEIF photo previews, video thumbnails and saved H.264/AAC compatibility copies on the NAS. Originals, filenames and album directories stay in place, and results are submitted back to Photos. Uninstall removes the worker and retains resources Photos has already accepted.

Deployment is through SSH. It needs administrator privileges, but no Photos password, OTP, saved session or Container Manager. Its media decoders run unprivileged with private libraries and network isolation. The current image path reads a read-only original descriptor into libheif and ImageMagick without copying the original or writing an encoded intermediate image.

**The tested target is x64, DSM 7.4.1-90080 Update 1 and Photos 1.9.1-10928.** The worker deliberately refuses unvalidated Photos versions. It uses undocumented local interfaces and runs a root coordinator, so please keep a verified independent backup and start with noncritical media. Native phone App playback is not fully validated. This is background generation, not real-time transcoding or a promise to restore every older DSM feature.

Current validation includes three existing HEIC images, rotated 10-bit and alpha-channel synthetic images, a 48 MP synthetic HEIC, isolated video processing and malformed-file cleanup. These are tests on one NAS, not universal compatibility claims. [Illustrated walkthrough and test steps](https://github.com/Gitawake/PhotosAssistantNAS/blob/main/docs/demo.md) · [Detailed validation](https://github.com/Gitawake/PhotosAssistantNAS/blob/main/docs/compatibility.md).

To install, first review the [README and disclaimer](https://github.com/Gitawake/PhotosAssistantNAS#readme), then run in your NAS's SSH terminal:

```sh
curl -fsSL https://raw.githubusercontent.com/Gitawake/PhotosAssistantNAS/main/bootstrap.sh -o "$HOME/photos-assistant-install.sh" && sudo sh "$HOME/photos-assistant-install.sh"
```

GitHub hosts source and the entry script; the NAS fetches pinned dependencies and assembles its own installation. No binary Releases are published. Source and binary dependencies have different licensing terms; see the repository's distribution notes.

The inspiration came from [octavianx/synology-photos-server-side-thumbnailgen](https://github.com/octavianx/synology-photos-server-side-thumbnailgen). Thanks to its author and to FFmpeg, ImageMagick, libheif and SynoCommunity contributors.

I'd appreciate reproducible feedback: NAS CPU architecture, exact DSM/Photos versions, media codec and whether preview/compatible playback works. Please redact logs and never post credentials, NAS addresses or private media. If your Photos version is currently unsupported, report the version rather than bypassing the version guard.
