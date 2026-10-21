#!/usr/bin/env python3
"""Isolated Python startup, using only root-controlled application code."""
import os
from pathlib import Path
import stat
import sys
root=Path(__file__).resolve().parent
for name in ('service_entry.py','native_worker.py','worker.py','decode_job.py'):
    info=(root/name).stat()
    if info.st_uid!=0 or info.st_mode&0o022 or not stat.S_ISREG(info.st_mode):
        raise RuntimeError('Untrusted installed code')
sys.path.insert(0,str(root))
from native_worker import main
main()
