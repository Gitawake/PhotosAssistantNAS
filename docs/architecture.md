# Architecture

1. The SSH installer verifies the locally built payload checksum and the supported Photos version, then creates a root-controlled application directory and one systemd unit.
2. A root coordinator calls the existing DSM synowebapi executable using existing local user identities. It does not authenticate via password, keep SID cookies, create a DSM user, or expose an HTTP service.
3. The scanner examines known missing states. It downloads one item through Photos into a private temporary job directory on the installation volume.
4. A child process enters a separate network namespace, drops supplementary groups and switches to an unused numeric UID/GID. no_new_privs, execution deadlines, memory/file limits and thread settings restrict decoding.
5. The root coordinator rejects output symlinks, hard links, unexpected ownership and oversized files, copies accepted output into controlled staging and grants only the relevant Photos user read access.
6. It rechecks the original item, submits only missing results through ConvertedFile, and rereads Photos metadata to confirm success. Handler output may be in stdout or outfile; process status alone is not authoritative.
7. Temporary media is removed. Root-owned cursors, retry deadlines, bounded logs and per-item accounting remain under the service directory.

No system CodecPack, global PATH, shared loader configuration, Photos binaries, original media directory or Photos database is directly modified. ImageMagick and FFmpeg use private libraries. The root coordinator remains a privileged component: isolation of decoders does not make arbitrary changes to coordinator code safe.

Uninstall stops and disables only the dedicated service, removes its unit and owned installation directory, then reloads systemd. It does not remove resources already accepted by Photos. Standard system audit logs and user-owned source/download files remain.
