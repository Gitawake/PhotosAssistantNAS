#!/usr/bin/env python3
"""Build a private-use NAS installer from pinned original dependencies, never an old SPK."""
import argparse
import gzip
import json
from pathlib import Path
import tarfile
from runtime import add_bytes, append_runtime, download_locked, sha256

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.4.0'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--downloads', type=Path, default=ROOT / 'vendor/downloads')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'vendor/lock.json').read_text())
    packages = {name: download_locked(name, spec, args.downloads, args.offline)
                for name, spec in sorted(lock.items())}
    folder = args.output / ('PhotosAssistantNAS-' + VERSION + '-x64')
    folder.mkdir(parents=True, exist_ok=True)
    payload = folder / ('PhotosAssistantNAS-x64-' + VERSION + '.tar.gz')
    manifest = {'schema': 1, 'dependencies': {}, 'binary_distribution': 'private-use-only; not a public binary release'}
    with payload.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=1) as zipped:
        with tarfile.open(fileobj=zipped, mode='w|', format=tarfile.GNU_FORMAT) as archive:
            for name, package in sorted(packages.items()):
                details = append_runtime(archive, name, package, ROOT / 'src/photos_assistant/policy.xml')
                manifest['dependencies'][name] = dict(lock[name], **details)
            for name in ('worker.py', 'native_worker.py', 'decode_job.py', 'service_entry.py'):
                add_bytes(archive, name, (ROOT / 'src/photos_assistant' / name).read_bytes())
            add_bytes(archive, 'uninstall.py', (ROOT / 'scripts/uninstall.py').read_bytes())
            for path in sorted((ROOT / 'licenses').iterdir()):
                add_bytes(archive, 'licenses/' + path.name, path.read_bytes())
            for name in ('LICENSE', 'NOTICE.md', 'THIRD_PARTY.md', 'DISCLAIMER.md'):
                add_bytes(archive, name, (ROOT / name).read_bytes())
            add_bytes(archive, 'runtime-manifest.json', json.dumps(manifest, sort_keys=True, indent=2).encode())
    checksum_name = payload.name + '.sha256'
    (folder / checksum_name).write_text(sha256(payload) + '  ' + payload.name + '\n')
    files = [payload.name, checksum_name]
    for name in ('install.sh', 'install.py', 'uninstall.sh', 'uninstall.py'):
        (folder / name).write_bytes((ROOT / 'scripts' / name).read_bytes())
        files.append(name)
    (folder / 'README-SSH.md').write_bytes((ROOT / 'README.md').read_bytes())
    files.append('README-SSH.md')
    result = args.output / ('PhotosAssistantNAS-' + VERSION + '-x64.private.tar')
    with tarfile.open(result, 'w', format=tarfile.GNU_FORMAT) as archive:
        for name in sorted(files):
            add_bytes(archive, name, (folder / name).read_bytes(), 0o700 if name.endswith('.sh') else 0o644)
    result.with_suffix('.tar.sha256').write_text(sha256(result) + '  ' + result.name + '\n')
    print(result)
    print('PRIVATE USE ONLY: pinned FFmpeg enables --enable-nonfree. Do not publish this binary archive.')
    print('See docs/distribution.md before changing dependencies or preparing a public binary release.')


if __name__ == '__main__':
    main()
