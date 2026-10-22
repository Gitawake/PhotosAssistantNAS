#!/bin/sh
set -eu
/bin/python3 -I - "$@" <<'PHOTOS_ASSISTANT_PY'
"""GitHub-hosted SSH bootstrap: build private runtimes on the user's NAS."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request

REPOSITORY = 'Gitawake/PhotosAssistantNAS'
MAX_SOURCE_BYTES = 32 * 1024 * 1024


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        'User-Agent': 'PhotosAssistantNAS-bootstrap', 'Accept': 'application/vnd.github+json'}), timeout=120)


def resolve_ref(ref):
    if re.fullmatch(r'[0-9a-fA-F]{40}', ref):
        return ref.lower()
    url = 'https://api.github.com/repos/' + REPOSITORY + '/commits/' + urllib.parse.quote(ref, safe='')
    with request(url) as response:
        data = json.loads(response.read(1024 * 1024))
    commit = data.get('sha', '')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise RuntimeError('GitHub did not return a valid source revision')
    return commit


def extract_source(archive_path, target):
    target = Path(target)
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        if len(members) > 5000 or sum(m.size for m in members) > MAX_SOURCE_BYTES:
            raise ValueError('Unexpected source archive size')
        roots = set()
        seen = set()
        for member in members:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts:
                raise ValueError('Unsafe source archive path')
            if not (member.isfile() or member.isdir()):
                raise ValueError('Source archive links and devices are not accepted')
            if str(path) in seen:
                raise ValueError('Duplicate source archive path')
            seen.add(str(path))
            roots.add(path.parts[0])
        if len(roots) != 1:
            raise ValueError('Expected one source archive root')
        for member in members:
            path = target / str(PurePosixPath(member.name))
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, path.open('xb') as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                os.chmod(path, 0o644)
    return target / next(iter(roots))


def check_environment(volume):
    if not re.fullmatch(r'/volume[1-9][0-9]*', volume):
        raise ValueError('Invalid volume')
    if os.geteuid() != 0:
        raise RuntimeError('Run the bootstrap using sudo or root; no Photos login is needed')
    if os.uname().machine != 'x86_64':
        raise RuntimeError('This build supports x86_64 only')
    if sys.version_info < (3, 8):
        raise RuntimeError('Python 3.8 or later is required')
    metadata = Path('/var/packages/SynologyPhotos/INFO').read_text()
    if 'version="1.9.1-10928"' not in metadata.splitlines():
        raise RuntimeError('Validated Photos version required: 1.9.1-10928')
    if not Path('/usr/syno/bin/synowebapi').is_file():
        raise RuntimeError('DSM local API is unavailable')
    if not Path(volume).is_dir() or not (Path(volume) / '@tmp').is_dir():
        raise RuntimeError('Installation volume and its @tmp directory must exist')
    if shutil.disk_usage(volume).free < 2 * 1024 ** 3:
        raise RuntimeError('At least 2 GiB of build workspace is required')
    subprocess.run(['/bin/systemctl', '--version'], check=True, stdout=subprocess.PIPE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='main', help='Branch, tag or full source commit; full commit recommended')
    parser.add_argument('--volume', default='/volume1')
    parser.add_argument('--no-start', action='store_true')
    parser.add_argument('--build-only', action='store_true', help='Download and build in temporary storage; do not install or change a service')
    parser.add_argument('--check', action='store_true', help='Check NAS environment only; no downloads or installation')
    args = parser.parse_args()
    print('WARNING: Experimental root service. Data loss/corruption and Photos unavailability are possible.', flush=True)
    print('Keep a verified independent backup and test noncritical media first. See DISCLAIMER.md.', flush=True)
    print('No data-integrity or recovery warranty is provided. Existing Photos outputs are retained on uninstall.', flush=True)
    check_environment(args.volume)
    if args.check:
        print('NAS environment checks passed. Nothing installed.')
        return
    os.umask(0o077)
    revision = resolve_ref(args.ref)
    print('Source:', REPOSITORY, revision, flush=True)
    with tempfile.TemporaryDirectory(prefix='photos-assistant-bootstrap-', dir=args.volume + '/@tmp') as work:
        work = Path(work)
        source_archive = work / 'source.tar.gz'
        url = 'https://codeload.github.com/' + REPOSITORY + '/tar.gz/' + revision
        with request(url) as response, source_archive.open('xb') as output:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SOURCE_BYTES:
                    raise ValueError('Source archive download exceeds limit')
                output.write(chunk)
        source = extract_source(source_archive, work / 'source')
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': str(work), 'TMPDIR': str(work)}
        build = work / 'built'
        subprocess.run([sys.executable, '-E', '-s', str(source / 'tools/build.py'),
                        '--downloads', str(work / 'dependencies'), '--output', str(build)],
                       check=True, env=env, cwd=str(source))
        if args.build_only:
            print('Build validation passed. No service or installation was changed; temporary files will be removed.')
            return
        installer = build / 'PhotosAssistantNAS-0.6.1-x64/install.py'
        command = [sys.executable, '-I', str(installer), '--volume', args.volume]
        if args.no_start:
            command.append('--no-start')
        subprocess.run(command, check=True, env=env)
        marker = Path(args.volume) / '@PhotosAssistantNAS/installation.json'
        data = json.loads(marker.read_text())
        data.update(source_repository=REPOSITORY, source_commit=revision)
        marker.write_text(json.dumps(data, indent=2))
        os.chmod(marker, 0o600)
    print('Installed from GitHub source. Temporary source, dependency downloads and build files were removed.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Bootstrap failed: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
PHOTOS_ASSISTANT_PY
