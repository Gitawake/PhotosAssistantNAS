#!/usr/bin/env python3
"""Remove this service only; never remove Photos media or generated previews."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
UNIT='photos-assistant-nas.service'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--volume',default='/volume1')
    args=parser.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Run with sudo or root')
    if not re.fullmatch(r'/volume[1-9][0-9]*',args.volume):raise ValueError('Invalid volume')
    root=Path(args.volume)/'@PhotosAssistantNAS'
    unit=Path('/etc/systemd/system')/UNIT
    if root.is_symlink():raise RuntimeError('Refusing symlink')
    marker=root/'installation.json'
    if not marker.exists():
        if unit.exists():raise RuntimeError('Installation marker missing; refusing unverified removal')
        print('Not installed.');return
    data=json.loads(marker.read_text())
    if data.get('schema')!=1 or data.get('root')!=str(root) or data.get('unit')!=UNIT:
        raise RuntimeError('Invalid installation marker')
    if root.stat().st_uid or marker.stat().st_uid or root.stat().st_mode&0o022:
        raise RuntimeError('Untrusted installation directory')
    if unit.exists() and ('PhotosAssistantNAS-managed' not in unit.read_text() or str(root/'app/service_entry.py') not in unit.read_text()):
        raise RuntimeError('Service definition belongs to another installation')
    subprocess.run(['/bin/systemctl','stop',UNIT],check=True)
    subprocess.run(['/bin/systemctl','disable',UNIT],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if unit.exists():unit.unlink()
    subprocess.run(['/bin/systemctl','daemon-reload'],check=True)
    subprocess.run(['/bin/systemctl','reset-failed',UNIT],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    shutil.rmtree(root)
    print('Uninstalled. Photos originals, previews and compatible videos were retained.')

if __name__=='__main__':main()
