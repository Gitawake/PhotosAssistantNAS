"""Fetch pinned upstream packages and construct private runtimes without installing SPKs."""
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import posixpath
import tarfile
import urllib.request
from private_elf import private_elf

VIDEO_LIBS = {'libdrm.so.2', 'libva.so.2', 'libOpenCL.so.1', 'libmfx.so.1',
              'libva-drm.so.2', 'libvulkan.so.1', 'libexpat.so.1'}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download_locked(name, spec, downloads, offline=False):
    destination = Path(downloads) / (name + '.spk')
    if destination.is_file():
        if sha256(destination) != spec['sha256']:
            raise ValueError('Cached dependency digest mismatch: ' + name)
        return destination
    if offline:
        raise FileNotFoundError('Offline dependency missing: ' + name)
    if not spec['url'].startswith('https://packages.synocommunity.com/'):
        raise ValueError('Unexpected dependency origin')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.download')
    try:
        with urllib.request.urlopen(spec['url'], timeout=120) as response, temporary.open('xb') as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        if sha256(temporary) != spec['sha256']:
            raise ValueError('Downloaded dependency digest mismatch: ' + name)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def member_name(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe dependency member')
    result = str(path)
    return '' if result == '.' else result


def link_target(path, link):
    if PurePosixPath(link).is_absolute():
        raise ValueError('Absolute dependency symlink')
    result = posixpath.normpath(posixpath.join(posixpath.dirname(path), link))
    if result == '..' or result.startswith('../') or result.startswith('/'):
        raise ValueError('Escaping dependency symlink')
    return result


def add_bytes(archive, name, data, mode=0o644):
    member = tarfile.TarInfo(name)
    member.uid = member.gid = member.mtime = 0
    member.mode = mode
    member.size = len(data)
    archive.addfile(member, io.BytesIO(data))


def append_runtime(output, name, package, policy):
    with tarfile.open(package) as source:
        metadata = source.extractfile('INFO').read().decode('utf-8')
        blob = source.extractfile('package.tgz').read()
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as payload:
        members = {}
        for member in payload.getmembers():
            path = member_name(member.name)
            if not path:
                continue
            if path in members:
                raise ValueError('Duplicate dependency member: ' + path)
            members[path] = member
        selected = set()
        for path in members:
            if name == 'videodriver':
                if path.startswith('lib/') and posixpath.basename(path) in VIDEO_LIBS:
                    selected.add(path)
            elif path.startswith(('lib/', 'etc/', 'share/')) or (
                path.startswith('bin/') and posixpath.basename(path) in ('magick', 'convert', 'ffmpeg', 'ffprobe')
            ):
                selected.add(path)
        pending = list(selected)
        while pending:
            path = pending.pop()
            member = members[path]
            if member.issym():
                target = link_target(path, member.linkname)
                if target not in members:
                    raise ValueError('Missing dependency symlink target')
                if target not in selected:
                    selected.add(target)
                    pending.append(target)
        for path in selected:
            seen = set()
            target = path
            while members[target].issym():
                if target in seen:
                    raise ValueError('Cyclic dependency symlink')
                seen.add(target)
                target = link_target(target, members[target].linkname)
        count = size = changes = 0
        nonfree = False
        for path in sorted(selected):
            source = members[path]
            dest = 'runtime/' + name + '/' + path
            if source.issym():
                item = tarfile.TarInfo(dest)
                item.type = tarfile.SYMTYPE
                item.linkname = source.linkname
                item.mode = 0o777
                output.addfile(item)
            elif source.isdir():
                item = tarfile.TarInfo(dest)
                item.type = tarfile.DIRTYPE
                item.mode = 0o755
                output.addfile(item)
            elif source.isfile():
                data = payload.extractfile(source).read()
                if name == 'ffmpeg' and path == 'bin/ffmpeg':
                    nonfree = b'--enable-nonfree' in data
                if name == 'imagemagick' and path == 'etc/ImageMagick-7/policy.xml':
                    data = Path(policy).read_bytes()
                data, modified = private_elf(data)
                changes += modified
                size += len(data)
                add_bytes(output, dest, data, 0o755 if source.mode & 0o111 else 0o644)
            else:
                raise ValueError('Unsupported dependency member type: ' + path)
            count += 1
    return {'package_info': metadata, 'files': count, 'private_payload_bytes': size,
            'cleared_elf_search_paths': changes, 'nonfree_enabled': nonfree}
