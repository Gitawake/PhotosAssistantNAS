# Walkthrough and validation

[English](demo.md) | [简体中文](demo.zh-CN.md)

![PhotosAssistantNAS workflow](media/overview.svg)

This is a workflow illustration, not a Photos screenshot or screen recording. The results below are documented NAS tests, not an animation pretending to be a live run.

The walkthrough targets web uploads without desktop Image Assistant, and File Station/SMB imports into Photos-indexed folders. A phone-only backup workflow that already displays and plays correctly usually needs no additional worker. The mobile Image Assistant switch can generate JPEG previews when browsing, including for these imports, but does not generate compressed compatibility videos. See [Synology's desktop/mobile comparison](https://kb.synology.com/en-eu/DSM/tutorial/Unable_to_view_HEIC_photos_HEVC_videos_on_Synology_Photos).

## What has actually been checked

| Check | Observed result |
| --- | --- |
| Photos integration in the original SSH implementation | Synthetic HEIC and HEVC thumbnail states became ready; the synthetic video's high compatibility copy became ready |
| 0.5.1 image processing | Three existing HEIC images produced nine thumbnails whose decoded pixels matched 0.5.0 |
| 10-bit, rotation and alpha | Synthetic cases matched the old output pixels |
| 48 MP image | An 8000×6000 synthetic HEIC completed all three thumbnail sizes |
| Image scratch writes | Directory event monitoring saw only final JPEG creations, without a source copy, encoded intermediate or pixel-cache file |
| Failure cleanup | Malformed HEIC was rejected and the task directory removed |

See [full validation and remaining gaps](compatibility.md), including native phone App playback, which is not fully validated. Identical output to official Image Assistant is not claimed. The original SSH integration tests and the 0.5.1 decoder tests are separate checks, not a claim that every client and media format has passed an end-to-end test.

## Repeat a small test on your NAS

Use an independent backup and noncritical test media. The supported target is currently x64 DSM with Photos **1.9.1-10928**; the full validated DSM build is listed in the compatibility document. This runs a root service and uses undocumented Photos interfaces. Read the [disclaimer](../DISCLAIMER.md) and [installation instructions](../README.md#one-command-ssh-installation) first.

1. Disable Image Assistant on every client involved in this test. Choose one HEIC and a short HEVC video that have not already been processed in this Photos library. Simply renaming an existing item may still trigger duplicate detection or reuse existing resources.
2. In a small personal-space test folder, upload the test media without client-side assistance, or copy it into your own indexed Photos directory. Do not delete an existing media item's resources to force a test.
3. On the NAS, check the service and follow its log:

   ```sh
   sudo systemctl is-active photos-assistant-nas.service
   sudo tail -f /volume1/@PhotosAssistantNAS/state/worker.log
   ```

   Substitute the installation volume if it is not `/volume1`. Press `Ctrl+C` to stop following the log; this does not stop the service.

4. The worker scans every 60 seconds. Photos must index the upload and mark a supported missing/broken state before the worker processes it; indexing and video encoding can take longer. Look for `source=readonly-fd`, followed by `processed` for the same item ID. The latter is logged after Photos reports the submitted resources ready. An existing usable resource is skipped, so no log entry does not by itself prove failure. Failed items wait an hour before retrying.
5. Refresh Photos. Check the image's thumbnail and opened preview, including orientation and color. Check the video's thumbnail and compatible playback. Existing compatible videos may need only thumbnails and no new video copy. Treat phone App behavior as a test result to report, not a guaranteed outcome.
6. To check original bytes, run this on the same test original before and after processing, replacing the example path:

   ```sh
   sha256sum "/path/to/test.heic"
   ```

   A matching digest checks bytes, not every filesystem property. Keep the original in place during the test. Remove unwanted test media through Photos afterward, without deleting a whole `@eaDir` directory.

The `readonly-fd` log proves the selected input path; it does **not** independently prove zero temporary writes. The no-copy/cache observation above used OS directory event monitoring. Final thumbnails, publication staging, logs and compatibility copies still write to storage; RAM can also be swapped by the OS.

## A short recording to share

For an actual screen recording, use synthetic or nonprivate media. Show clients' Assistant disabled, the new test upload, the relevant sanitized log lines, and the result in Photos. Keep the same item ID visible so viewers can connect processing with acceptance. Waiting can be cut, but label any time jump; do not call edited footage real-time performance. Hide accounts, hosts, private media, paths, cookies and unrelated notifications.

The repository currently provides this illustration and reproducible walkthrough, **not an actual Photos screen recording**. Please link the precise version and [compatibility notes](compatibility.md) when sharing a recording. Ready-to-copy introduction text is in the [community post draft](community-post.md).
