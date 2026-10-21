# Security policy

[English](SECURITY.md) | [简体中文](SECURITY.zh-CN.md)

This is experimental software that installs a root service on a personal NAS. Read the installer, coordinator and uninstall code before granting administrator permission. Build and review a pinned revision; source openness is not a security certification.

## Boundaries

- The root coordinator can act as existing local users through DSM's local Photos facility. Do not expose it as a general API, add shell execution, or accept arbitrary commands from media or network input.
- Installed code and service state must stay root controlled. No generic Python interpreter is made setuid and no sudoers entry is installed.
- Media decoders run under a non-login numeric identity, with no supplementary groups, no_new_privs, a separate network namespace and resource limits. Isolation failure aborts the job.
- Decode libraries, delegates, writable staging, file ownership and links are part of the attack surface. Do not broaden ImageMagick policy or library lookup without review.
- Only the current video’s read-only file descriptor is inherited by the isolated decoder and its private FFmpeg subprocesses. Other source paths are not granted additional permissions. Source inode size/timestamps are rechecked before publishing outputs.
- Originals are not rewritten, but generated previews and video copies are persistent writes to Photos and consume storage.
- Checksums detect an unexpected payload relative to its sidecar file; they are not publisher signatures and do not protect against replacement of both files.

## Reporting

Use the repository's private vulnerability reporting feature if the maintainer has enabled it. Otherwise ask for a private contact method without posting exploit details or personal data publicly. There is no dedicated disclosure mailbox configured in this source export.

Never attach passwords, OTPs, session cookies, authentication URLs, SSH keys, private media, addresses, usernames or raw NAS diagnostics to an issue. Prefer a synthetic reproducer with architecture, exact DSM/Photos versions, service state and redacted error codes. No remote NAS access or test credentials are required for an initial report.
