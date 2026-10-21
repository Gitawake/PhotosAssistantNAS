# Data safety and risk disclaimer

[English](DISCLAIMER.md) | [简体中文](DISCLAIMER.zh-CN.md)

This is an experimental community tool, independent of Synology and without its endorsement or warranty. The software is provided as is, without guarantees of freedom from defects, continued compatibility, fitness for a particular purpose, or data integrity. Code licensing, warranty exclusions, and liability limitations are governed by LICENSE and applicable law.

## Possible effects

The program is designed to preserve original photos, videos, and directories while adding Photos previews and compatibility videos. That design is not a data-safety guarantee. Bugs, unknown media formats, Photos/DSM interface changes, permission errors, concurrent operations, insufficient resources, power loss, and filesystem or storage failures can cause corruption, loss, indexing problems, incorrect previews, unavailable albums, or other unexpected effects.

Installation creates a root coordinator service and submits persistent data to Photos. Processing can consume substantial CPU, memory, and storage and affect NAS responsiveness or other tasks. Decoder isolation, space checks, version checks, and existing tests reduce risk; they do not eliminate it.

## Before use

- Keep an independent backup of original media and necessary configuration outside the NAS, and verify recovery. RAID, same-disk copies, and preview caches are not substitutes for independent backups.
- Test a small set of noncritical or synthetic media first. Check results, storage use, start/stop, and uninstall behavior.
- Revalidate after upgrading DSM, Photos, dependencies, or this project. Do not bypass version or safety checks to force operation.
- Do not rely on this project as your only protection for originals. Users remain responsible for preserving and backing up their media.

Uninstall removes this project's service, application, state, and temporary files. **It does not delete thumbnails, previews, or compatibility videos already submitted to Photos, and is neither a data-repair procedure nor a complete rollback.** If problems occur, stop the service, retain redacted error information, and recover according to your own backup plan.

To the extent permitted by applicable law, users assess and accept the risks of deploying, running, and modifying this project. Contributors do not promise data recovery, continuing maintenance, or compensation for losses. This statement does not exclude liability that applicable law does not allow to be excluded.
