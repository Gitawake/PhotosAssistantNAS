#!/usr/bin/env python3
"""Create a source-only, checked, deterministic ZIP; never package private runtimes."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from check_public import ROOT, check


def package(output):
    files = check()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            name = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            manifest[name] = hashlib.sha256(data).hexdigest()
            info = zipfile.ZipInfo('PhotosAssistantNAS/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
        info = zipfile.ZipInfo('PhotosAssistantNAS/source-manifest.json', date_time=(1980, 1, 1, 0, 0, 0))
        info.external_attr = 0o100644 << 16
        archive.writestr(info, json.dumps(manifest, sort_keys=True, indent=2).encode())
    output.with_suffix(output.suffix + '.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + output.name + '\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/PhotosAssistantNAS-source.zip')
    print(package(parser.parse_args().output))
