"""Detect optional GPU backends without installing drivers or changing device modes."""
import functools
import json
import os
from pathlib import Path
import stat
import subprocess

BACKENDS={
    'vaapi':{'encoder':'h264_vaapi','vendors':{'0x8086':'iHD','0x1002':'radeonsi'}},
    'qsv':{'encoder':'h264_qsv','vendors':{'0x8086':'iHD'}},
    'nvenc':{'encoder':'h264_nvenc'},
}

def preference(state):
    path=Path(state)/'hardware.json'
    if not path.exists(): return 'auto'
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022: return 'software'
    try: backend=json.loads(path.read_text()).get('backend')
    except (ValueError,OSError,AttributeError): return 'software'
    return backend if backend in {'auto','software'}|set(BACKENDS) else 'software'

@functools.lru_cache(maxsize=4)
def encoders(runtime):
    runtime=Path(runtime)
    env={'PATH':'/usr/bin:/bin','LANG':'C','LD_LIBRARY_PATH':str(runtime/'ffmpeg/lib')+':'+str(runtime/'videodriver/lib')}
    try:
        result=subprocess.run([str(runtime/'ffmpeg/bin/ffmpeg'),'-hide_banner','-encoders'],env=env,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
        if result.returncode: return frozenset()
        return frozenset(line.split()[1] for line in result.stdout.decode(errors='replace').splitlines()
                         if len(line.split())>=2 and line.lstrip().startswith('V'))
    except (OSError,subprocess.TimeoutExpired): return frozenset()

def trusted_directory(path):
    # Optional system userspace drivers are read-only dependencies, never modified.
    try:
        for parent in (Path(path),*Path(path).parents):
            info=parent.stat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022: return False
        return True
    except OSError: return False

def device_for(runtime,backend='auto',device_root=Path('/dev/dri'),sys_root=Path('/sys/class/drm'),available=None):
    runtime=Path(runtime)
    if backend=='software': return None
    available=encoders(str(runtime)) if available is None else available
    choices=('vaapi','qsv','nvenc') if backend=='auto' else (backend,)
    for choice in choices:
        if choice not in BACKENDS or BACKENDS[choice]['encoder'] not in available: continue
        if choice=='nvenc':
            nodes=[Path('/dev/nvidia0'),Path('/dev/nvidiactl')]
            try:
                infos=[p.lstat() for p in nodes]
                if not all(stat.S_ISCHR(i.st_mode) and i.st_uid==0 for i in infos): continue
                extra=Path('/dev/nvidia-uvm')
                if extra.exists():
                    info=extra.lstat()
                    if not stat.S_ISCHR(info.st_mode) or info.st_uid!=0: continue
                    infos.append(info)
                return {'backend':choice,'device':'0','groups':sorted({i.st_gid for i in infos if i.st_gid!=0}),
                        'driver':None,'driver_path':None}
            except OSError: continue
        for path in sorted(Path(device_root).glob('renderD*')):
            try:
                info=path.lstat()
                if not stat.S_ISCHR(info.st_mode) or info.st_uid!=0 or os.major(info.st_rdev)!=226: continue
                vendor=(Path(sys_root)/path.name/'device/vendor').read_text().strip().lower()
                driver=BACKENDS[choice]['vendors'].get(vendor)
                if not driver: continue
                roots=[runtime/'videodriver/lib',Path('/usr/lib/dri'),Path('/usr/lib64/dri'),Path('/usr/local/lib/dri'),Path('/lib/dri')]
                for root in roots:
                    library=root/(driver+'_drv_video.so')
                    if not library.is_file(): continue
                    details=library.stat()
                    if details.st_uid!=0 or details.st_mode&0o022: continue
                    if root!=runtime/'videodriver/lib' and not trusted_directory(root.resolve()): continue
                    fallbacks=[]
                    legacy=root/'i965_drv_video.so'
                    if driver=='iHD' and legacy.is_file():
                        old=legacy.stat()
                        if old.st_uid==0 and not old.st_mode&0o022: fallbacks=['i965']
                    return {'backend':choice,'device':str(path),'driver':driver,'driver_path':str(root),'driver_fallbacks':fallbacks,
                            'groups':[info.st_gid] if info.st_gid!=0 else [],'gid':info.st_gid}
            except OSError: continue
    return None
