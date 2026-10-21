# Architecture

[English](architecture.md) | [简体中文](architecture.zh-CN.md)

1. The SSH installer verifies the locally built payload checksum and the supported Photos version, then creates a root-controlled application directory and one systemd unit.
2. A root coordinator calls the existing DSM synowebapi executable using existing local user identities. It does not authenticate via password, keep SID cookies, create a DSM user, or expose an HTTP service.
3. The scanner resolves known missing items through Photos folder metadata and opens originals read-only using no-follow directory traversal. For video it passes that one descriptor through privilege drop to FFmpeg/FFprobe's seekable `fd:` input protocol. No source-video copy, reflink, ACL change or Btrfs feature is needed. Images pass the same read-only descriptor to a private libheif reader-v1 callback bridge. Its decoded RGB/RGBA rows are imported directly into MagickWand; the primary image, transformations, bit depth and ICC profile are retained without an encoded intermediate or source copy. ImageMagick's disk/mapped pixel caches are disabled in this helper. The pinned private jemalloc is preloaded only into the isolated helper to satisfy its startup TLS requirement; no global loader setting is changed.
4. A child process enters a separate network namespace, drops supplementary groups and switches to an unused numeric UID/GID. no_new_privs, execution deadlines, memory/output-file limits and thread settings restrict decoding. FFmpeg streams the original read-only descriptor; its size is not capped at 8 GiB. Space is reserved from duration/output bitrate, and free-space checks run at five-second intervals during decoding.
5. The root coordinator rejects output symlinks, hard links, unexpected ownership and oversized files, copies accepted output into controlled staging and grants only the relevant Photos user read access.
6. It rechecks the open original inode fingerprint and original item, submits only missing results through ConvertedFile, and rereads Photos metadata to confirm success. Handler output may be in stdout or outfile; process status alone is not authoritative.
7. Temporary media is removed. Root-owned cursors, retry deadlines, bounded logs and per-item accounting remain under the service directory.

No system CodecPack, global PATH, shared loader configuration, Photos binaries, original media directory or Photos database is directly modified. ImageMagick and FFmpeg use private libraries. The root coordinator remains a privileged component: isolation of decoders does not make arbitrary changes to coordinator code safe.

Uninstall stops and disables only the dedicated service, removes its unit and owned installation directory, then reloads systemd. It does not remove resources already accepted by Photos. Standard system audit logs and user-owned source/download files remain.
