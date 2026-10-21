#!/usr/bin/env python3
"""Validate a source-only public tree without displaying matched sensitive values."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {'README.md', 'LICENSE', 'NOTICE.md', 'THIRD_PARTY.md', 'DISCLAIMER.md', 'ACKNOWLEDGEMENTS.md',
              'SECURITY.md', 'CONTRIBUTING.md', 'CHANGELOG.md', '.gitignore', '.gitattributes',
              'bootstrap.sh', 'uninstall.sh'}
PUBLIC_DIRS = {'src', 'scripts', 'tools', 'tests', 'docs', 'licenses', '.github'}
SUFFIXES = {'.py', '.sh', '.md', '.txt', '.yml', '.yaml', '.json', '.xml'}
SKIP = {'.git', '__pycache__', '.pytest_cache', '.venv', 'dist', 'build'}
PATTERNS = {
    'private_network_address': re.compile(r'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b'),
    'tailscale_host': re.compile(r'\b[\w.-]+\.ts\.net\b', re.I),
    'github_credential': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b'),
    'private_key': re.compile(r'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----'),
    'embedded_secret': re.compile(r'''(?:password|passwd|otp_code|_sid)\s*[:=]\s*['"](?!fake|example|test)[A-Za-z0-9_./+=-]{12,}['"]''', re.I),
}


def public_files(root=ROOT):
    root = Path(root)
    files = []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if any(part in SKIP for part in rel.parts) or rel.parts[:2] == ('vendor', 'downloads'):
            continue
        if path.name == '.DS_Store' or path.is_dir():
            continue
        if path.is_symlink():
            raise ValueError('Public source must not contain symlinks: ' + str(rel))
        allowed = (len(rel.parts) == 1 and path.name in ROOT_FILES) or (
            rel.parts[0] in PUBLIC_DIRS and path.suffix in SUFFIXES) or str(rel) == 'vendor/lock.json'
        if not allowed:
            raise ValueError('Unexpected public source file: ' + str(rel))
        if path.stat().st_size > 1024 * 1024:
            raise ValueError('Unexpected large source file: ' + str(rel))
        files.append(path)
    return files


def check(root=ROOT):
    files = public_files(root)
    failures = []
    for path in files:
        data = path.read_bytes()
        if b'\0' in data:
            failures.append((path, 'binary_content'))
            continue
        text = data.decode('utf-8')
        for kind, pattern in PATTERNS.items():
            if pattern.search(text):
                failures.append((path, kind))
    if failures:
        message = '\n'.join(str(p.relative_to(root)) + ': ' + kind for p, kind in failures)
        raise ValueError('Public-source validation failed (matched values withheld):\n' + message)
    return files


if __name__ == '__main__':
    print('Public-source validation passed:', len(check()), 'files')
