#!/bin/sh
set -eu
/bin/python3 -I - "$@" <<'PHOTOS_ASSISTANT_UNINSTALL_PY'
import argparse
import os
from pathlib import Path
import re
p=argparse.ArgumentParser(description='Uninstall PhotosAssistantNAS; retain all Photos-generated resources.')
p.add_argument('--volume',default='/volume1')
a=p.parse_args()
if os.geteuid()!=0:raise SystemExit('Run using sudo or root.')
if not re.fullmatch(r'/volume[1-9][0-9]*',a.volume):raise SystemExit('Invalid volume.')
root=Path(a.volume)/'@PhotosAssistantNAS'
script=root/'uninstall.py'
if root.is_symlink() or script.is_symlink():raise SystemExit('Refusing symbolic link.')
if not script.exists():
    if root.exists():raise SystemExit('Installation exists but its trusted uninstaller is missing.')
    raise SystemExit('Not installed. Photos resources were not touched.')
for item in (root,script):
    info=item.stat()
    if info.st_uid!=0 or info.st_mode&0o022:raise SystemExit('Untrusted installation permissions.')
os.execv('/bin/python3',['/bin/python3','-I',str(script),'--volume',a.volume])
PHOTOS_ASSISTANT_UNINSTALL_PY
