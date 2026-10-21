# Event-driven processing

[English](events.md) | [简体中文](events.zh-CN.md)

Version 0.6.0 replaces the repeating full-library scan with Linux inotify and a root-private SQLite queue. This is the standard Linux filesystem-event API, **not** a documented Synology Photos upload-complete callback. No supported public Photos callback was found in the reviewed documentation/API descriptors; the worker does not register an internal DSM media-index plugin or modify Synology's indexing service.

## Normal operation

1. A separate collector watches local Photos directories for closed writes, moved files and newly added directory trees. It does not follow directory symlinks and ignores hidden/generated directories such as `@eaDir` and `#recycle`.
2. Events are coalesced and persisted. The coordinator waits for a stable source fingerprint, resolves the matching Photos folder by name, and queries only that folder until an indexed item with matching filename and size exists.
3. Item tasks are persisted by context, item ID and phase. Missing previews have priority over compatible-video work; unchanged compatible originals retain the existing skip behavior. Active video work is not preempted, while the separate collector continues recording events.
4. Failed media retain delayed retries. Source changes invalidate the queued identity/cache token. When nothing is ready, the coordinator waits on a wakeup pipe and the collector waits on inotify; there is no timed full-library rescan.

One history reconciliation runs at startup/restart to discover pre-existing or offline changes. Another runs only after an explicit request, kernel-event overflow or loss/restoration of a root watch. Tasks already in the durable queue survive restart. Folder indexing delays cause targeted retries, not full-library rescans. Local account/root discovery and process-health checks still wake periodically; they do not enumerate the Photos library.

To request a one-off reconciliation without restarting the service:

```sh
sudo /bin/python3 -I /volume1/@PhotosAssistantNAS/app/service_entry.py reconcile
```

Adjust the volume if installed elsewhere. The coordinator takes the request at its next scheduling boundary. This requests discovery, not a forced Photos reindex and not replacement of accepted resources.

## Failure handling and boundaries

The collector becomes ready before history discovery starts, and recently created files in directories changed during watch setup are retained as events. New or moved directories receive recursive watches. Kernel overflow requests a fresh reconciliation. Watch-capacity or permission failures stop the collector and produce an error instead of silently claiming full coverage; inspect private `state/events.log`. No system inotify limits are changed automatically.

Events indicate a filesystem change, not proof that Photos indexing has completed. The worker waits for matching index metadata; normal Photos format/status checks and read-only source guards still apply. Network filesystems, unsupported Photos versions and arbitrary symlinked libraries are not newly supported. The listener does not intercept browser uploads, install a public HTTP endpoint or require account credentials.

Queue/database files, event logs and watches belong to this service and are removed/stopped on uninstall. Original media and Photos-accepted resources retain the existing uninstall policy.

## Validation

Unit tests cover durable queue restart, priority, identity/retry invalidation, source stability, symlink escape rejection, folder-targeted index lookup, deleted items, overflow recovery requests, and the absence of full rescans between successive tasks. A NAS-only test captured both a file move and an entire directory move, excluded generated-cache changes, retained events after queue reopen, and measured zero watcher CPU ticks over a three-second idle sample. These tests do not establish support for every filesystem or client upload path.

Reference: [Linux inotify manual](https://man7.org/linux/man-pages/man7/inotify.7.html).
