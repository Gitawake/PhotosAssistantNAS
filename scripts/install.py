#!/usr/bin/env python3
"""SSH installer. Needs DSM administrator/root permission, never a Photos login."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

UNIT='photos-assistant-nas.service'
UNIT_PATH=Path('/etc/systemd/system')/UNIT

def run(*args,check=True):
    return subprocess.run(args,check=check,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

def require_root_directory(path,mode=0o711):
    if path.is_symlink(): raise RuntimeError('Refusing symbolic link: '+str(path))
    path.mkdir(mode=mode,exist_ok=True)
    info=path.stat()
    if info.st_uid or info.st_mode&0o022: raise RuntimeError('Unsafe installation directory')
    os.chmod(path,mode)
    return path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--volume',default='/volume1')
    p.add_argument('--test-item',type=int,action='append')
    p.add_argument('--runner')
    p.add_argument('--no-start',action='store_true')
    args=p.parse_args()
    print('WARNING: Experimental root service. Data loss/corruption and Photos unavailability are possible.', flush=True)
    print('Keep an independent, verified backup and test with noncritical media first. See DISCLAIMER.md.', flush=True)
    if os.geteuid()!=0: raise RuntimeError('Run install.sh with sudo or root')
    os.umask(0o077)
    if os.uname().machine!='x86_64': raise RuntimeError('x64 DSM is required')
    if not re.fullmatch(r'/volume[1-9][0-9]*',args.volume): raise ValueError('Invalid volume')
    if not Path(args.volume).is_dir(): raise ValueError('Volume unavailable')
    photos=Path('/var/packages/SynologyPhotos/INFO').read_text()
    if 'version="1.9.1-10928"' not in photos.splitlines():
        raise RuntimeError('Validated Photos version required: 1.9.1-10928')
    if not Path('/usr/syno/bin/synowebapi').is_file(): raise RuntimeError('DSM local API is unavailable')
    subprocess.run(['/bin/systemctl','--version'],check=True,stdout=subprocess.PIPE)
    here=Path(__file__).resolve().parent
    bundle=here/'PhotosAssistantNAS-x64-0.5.0.tar.gz'
    expected=(here/(bundle.name+'.sha256')).read_text().split()[0]
    if hashlib.sha256(bundle.read_bytes()).hexdigest()!=expected: raise RuntimeError('Payload checksum mismatch')
    root=Path(args.volume)/'@PhotosAssistantNAS'
    require_root_directory(root)
    marker=root/'installation.json'
    if root.exists() and any(root.iterdir()) and not marker.is_file():
        raise RuntimeError('Existing directory has no installation marker')
    if UNIT_PATH.exists() and ('PhotosAssistantNAS-managed' not in UNIT_PATH.read_text() or str(root/'app/service_entry.py') not in UNIT_PATH.read_text()):
        raise RuntimeError('Service name belongs to another installation')
    if marker.exists():
        previous=json.loads(marker.read_text())
        if previous.get('schema')!=1 or previous.get('root')!=str(root): raise RuntimeError('Invalid installation marker')
    with tempfile.TemporaryDirectory(prefix='.install-',dir=str(root)) as temp:
        stage=Path(temp)
        with tarfile.open(bundle,'r:gz') as archive:
            members=archive.getmembers()
            names={m.name for m in members}
            for member in members:
                path=Path(member.name)
                if path.is_absolute() or '..' in path.parts or member.isdev() or member.isfifo() or member.islnk():
                    raise RuntimeError('Unsafe archive member')
                if member.issym():
                    dest=os.path.normpath(str(path.parent/member.linkname))
                    if dest.startswith(('../','/')) or dest not in names: raise RuntimeError('Unsafe archive link')
            # Archive links are relative, file owners ignored; only root controls staging.
            archive.extractall(stage)
        for base,dirs,files in os.walk(stage):
            os.chmod(base,0o755)
            for name in files:
                path=Path(base)/name
                if not path.is_symlink(): os.chmod(path,0o755 if path.stat().st_mode&0o111 else 0o644)
        run('/bin/systemctl','stop',UNIT,check=False)
        previous_unit=UNIT_PATH.read_bytes() if UNIT_PATH.exists() else None
        previous_marker=marker.read_bytes() if marker.exists() else None
        app=root/'app';backup=root/'.previous-app'
        if backup.exists(): shutil.rmtree(backup)
        if app.exists(): app.rename(backup)
        stage.rename(app)
        try:
            require_root_directory(root/'state')
            command=['/bin/python3','-I',str(app/'service_entry.py'),'daemon','--state',str(root/'state')]
            for item in args.test_item or []: command.extend(['--test-item',str(item)])
            if args.runner:
                if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',args.runner): raise ValueError('Invalid runner')
                command.extend(['--runner',args.runner])
            unit='''# PhotosAssistantNAS-managed
[Unit]
Description=Synology Photos NAS Assistant replacement
After=pkgctl-SynologyPhotos.service

[Service]
Type=simple
User=root
UMask=0077
ExecStart={command}
Restart=on-failure
RestartSec=60
KillMode=mixed
TimeoutStopSec=30
Nice=10
CPUQuota=150%
MemoryLimit=1536M
LimitNOFILE=256
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectHome=yes
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
'''.format(command=' '.join(command))
            UNIT_PATH.write_text(unit);os.chmod(UNIT_PATH,0o644)
            marker.write_text(json.dumps({'schema':1,'root':str(root),'version':'0.5.0','unit':UNIT},indent=2))
            os.chmod(marker,0o600)
            (root/'uninstall.py').write_bytes((app/'uninstall.py').read_bytes());os.chmod(root/'uninstall.py',0o700)
            run('/bin/systemctl','daemon-reload')
            run('/bin/systemctl','enable',UNIT)
            if not args.no_start:
                run('/bin/systemctl','start',UNIT)
                run('/bin/systemctl','is-active','--quiet',UNIT)
        except BaseException:
            run('/bin/systemctl','stop',UNIT,check=False)
            if app.exists(): shutil.rmtree(app)
            if backup.exists(): backup.rename(app)
            if previous_unit is None:
                if UNIT_PATH.exists(): UNIT_PATH.unlink()
            else: UNIT_PATH.write_bytes(previous_unit)
            if previous_marker is None:
                if marker.exists(): marker.unlink()
            else: marker.write_bytes(previous_marker)
            run('/bin/systemctl','daemon-reload',check=False)
            if previous_unit is not None: run('/bin/systemctl','start',UNIT,check=False)
            raise
        if backup.exists():shutil.rmtree(backup)
    print('Installed:',root)
    print('Service:',UNIT,'(stopped)' if args.no_start else '(running)')
    print('Uninstall: sudo /bin/python3 -I '+str(root/'uninstall.py'))
    print('Photos originals, folders, and existing previews remain unchanged.')

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Installation failed:',str(error),file=sys.stderr);raise SystemExit(1)
