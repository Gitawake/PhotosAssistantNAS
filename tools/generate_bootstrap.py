#!/usr/bin/env python3
"""Keep the downloadable shell entry point identical to its tested Python source."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def content():
    program = (ROOT / 'tools/online_bootstrap.py').read_text()
    if '\nPHOTOS_ASSISTANT_PY\n' in program:
        raise ValueError('Unexpected heredoc terminator')
    return ('#!/bin/sh\nset -eu\n'
            '/bin/python3 -I - "$@" <<\'PHOTOS_ASSISTANT_PY\'\n' + program +
            'PHOTOS_ASSISTANT_PY\n')


if __name__ == '__main__':
    (ROOT / 'bootstrap.sh').write_text(content())
