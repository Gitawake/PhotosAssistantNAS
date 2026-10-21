# Compatibility and validation

## Validated target

| Item | Tested |
| --- | --- |
| CPU architecture | x86_64, Intel N100 |
| DSM | 7.4.1-90080 Update 1 |
| Synology Photos | 1.9.1-10928 |
| NAS Python | DSM built-in Python 3.8 |
| Installation | Administrator SSH, dedicated systemd service |

Photos version checks deliberately fail on an unvalidated version. This is not a claim of support for all DSM 7 releases or all x64 NAS models. A simulated API unit test cannot establish compatibility with a new Photos build.

## Hardware observations from the original SSH implementation

- Synthetic HEVC video: missing thumbnails and compatible video became SM/M/XL ready and high video ready. Photos identified the variant as H.264/AAC, 24 FPS, three seconds.
- Synthetic HEIC: all three JPEG thumbnail sizes became ready.
- Media originals retained the same SHA256 after processing and uninstall.
- Stop/start succeeded. Uninstall removed the program directory, systemd unit and autostart link; Photos previews and compatible video remained available.
- Decoder used a non-login numeric UID, no supplementary groups, zero effective capabilities, no_new_privs, and a different network namespace.
- Personal and shared metadata scan calls succeeded; the shared space used for validation was empty. Existing package INFO hashes remained unchanged.

The public source preparation removes unused session-login and abandoned SPK code. Its build pipeline is independently tested from pinned original dependencies. The refactored source export has not been reinstalled on every NAS configuration; it remains experimental.

## Not fully validated

- Native phone App playback for this worker's outputs.
- Actual generation in a populated shared space; domain and LDAP users.
- Every supported container, malformed file, HDR or Dolby Vision variant.
- DSM upgrades, Photos API changes, other CPU models or hardware transcoding.
- Byte-for-byte or perceptually identical output to Synology Image Assistant.

HEIC/HEIF/HIF images and the video's declared extension list are candidates, not guarantees of successful decoding. Original quality and HDR are preserved in the original file; the compatibility copy may be SDR and lower resolution.
