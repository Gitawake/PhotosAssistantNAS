# Scope and processing decisions

[English](scope.md) | [简体中文](scope.zh-CN.md)

## Current baseline

Version **0.6.1** on `main` is the current primary version. It retains event-driven queues, direct read-only source input, preview priority, optional GPU processing and validated fallback. It is experimental and validated on Intel N100 / DSM 7.4.1-90080 Update 1 / Photos 1.9.1-10928. See [compatibility](compatibility.md) and [hardware status](hardware.md). Documentation updates do not imply a new decoder version.

## Responsibility

Generate missing Photos previews and compatibility videos on the NAS for supported Photos-indexed items. Personal and Shared Space are within the intended scope; generation in a populated Shared Space remains unvalidated. Files elsewhere on the NAS are outside scope.

This is an independent worker, not a complete AME replacement. AME supplied shared codec capabilities; Photos and DSM callers selected media tasks and their timing. This project uses its own queue and conservative compatibility policy. It does not reproduce every historical AME/Photos decision or provide real-time playback transcoding.

| Item or state | Worker decision |
| --- | --- |
| HEIC/HEIF/HIF with a recognized missing/broken preview state | Generate JPEG preview sizes from the original descriptor |
| Video in the supported extension list with a recognized missing/broken preview state | Extract a frame and generate JPEG preview sizes; this phase does not transcode the whole video |
| Existing usable preview or high compatibility variant | Retain it; do not replace it automatically |
| Missing high variant and an original meeting the project's conservative compatibility checks | Keep the original; cache the decision without falsely marking a generated variant ready |
| Missing high variant and an original not meeting those checks | Queue H.264/AAC MP4 generation, subject to media/resource limits and validation |
| Unsupported format/version, unavailable context or unsafe/changed source | Skip, defer or fail closed according to the existing checks; never rewrite the original |

The extension list includes containers beyond HEVC, such as MOV, MP4, M4V and AVI. A container extension is not a codec or a playback guarantee. Ordinary JPEG/PNG images are outside the private HEIF decoder path. Conservative compatibility checks may generate a copy even when a particular client could play the original; they do not test every phone/browser. See [current checks](../src/photos_assistant/worker.py) and [resource limits](../README.md#management-and-uninstall).

## When processing happens

- At service startup/restart, reconcile the indexed library for historical or offline changes. Discovery does not force regeneration of accepted resources.
- During normal operation, filesystem events identify new/changed media. Wait for a stable source and matching Photos index metadata, then queue work for the affected folder.
- Previews and compatibility videos have separate task phases and delayed failure retries. Previews have priority; a running video job is not interrupted.
- Cache unchanged compatibility decisions. Event overflow, lost/restored watches or an explicit reconciliation request can trigger recovery discovery. There is no repeating timed full-library scan.
- Browsing or pressing Play is not this worker's transcode trigger. It prepares resources in the background.

See [event processing and reconciliation](events.md). The listener uses Linux inotify, not an official Photos upload callback.

## Uninstall and experiments

Uninstall removes the worker's service, application, state and temporary work. Original files, names, album directory structure and resources already accepted by Photos are retained.

The old caller's 15-fps/Baseline parameter branch and the separate Intel OpenCL runtime were investigated, but are not enabled in the primary version. Old AME proprietary binaries are not bundled. Version 0.6.1 keeps its bounded 30-fps pipeline and existing GPU/software fallback. See [AME reference and color limitations](ame-reference.md). Source-only distribution and the existing [data-safety disclaimer](../DISCLAIMER.md) remain applicable.
