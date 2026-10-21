"""Linux inotify adapter; read-only directory watches, no kernel/DSM hooks."""
import ctypes
import errno
import os
from pathlib import Path
import select
import struct

CLOSE_WRITE=0x8;MOVED_FROM=0x40;MOVED_TO=0x80;CREATE=0x100;DELETE=0x200
DELETE_SELF=0x400;MOVE_SELF=0x800;OVERFLOW=0x4000;IGNORED=0x8000;ISDIR=0x40000000
MASK=CLOSE_WRITE|MOVED_FROM|MOVED_TO|CREATE|DELETE|DELETE_SELF|MOVE_SELF|0x01000000|0x02000000
IGNORED_DIRS={'@eaDir','#recycle','.TemporaryItems'}

def allowed(path): return not any(part.startswith('.') or part in IGNORED_DIRS for part in Path(path).parts if part not in ('.','/'))

def parse(data):
    offset=0
    while offset+16<=len(data):
        wd,mask,cookie,size=struct.unpack_from('iIII',data,offset);offset+=16
        if size>len(data)-offset: raise ValueError('Incomplete inotify event')
        name=os.fsdecode(data[offset:offset+size].split(b'\0',1)[0]);offset+=size
        yield wd,mask,name
    if offset!=len(data):raise ValueError('Incomplete inotify header')

class Monitor:
    def __init__(self,extensions):
        self.lib=ctypes.CDLL(None,use_errno=True)
        self.lib.inotify_init1.argtypes=[ctypes.c_int];self.lib.inotify_init1.restype=ctypes.c_int
        self.lib.inotify_add_watch.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_uint32];self.lib.inotify_add_watch.restype=ctypes.c_int
        self.fd=self.lib.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)
        if self.fd<0:raise OSError(ctypes.get_errno(),'inotify initialization failed')
        self.paths={};self.reverse={};self.extensions=extensions;self.incomplete=False
    def close(self):os.close(self.fd)
    def add_tree(self,root,emit=False,recent_since=None):
        files=[]
        for base,dirs,names in os.walk(str(root),followlinks=False):
            path=Path(base)
            dirs[:]=[d for d in dirs if allowed(d) and not (path/d).is_symlink()]
            if path not in self.reverse:
                wd=self.lib.inotify_add_watch(self.fd,os.fsencode(str(path)),MASK)
                if wd<0:
                    if ctypes.get_errno() not in (errno.ENOENT,errno.ENOTDIR):self.incomplete=True
                    continue
                self.paths[wd]=path;self.reverse[path]=wd
            try:recent=recent_since is not None and path.stat().st_mtime>=recent_since
            except FileNotFoundError:continue
            if emit or recent:
                for name in names:
                    target=path/name
                    if not allowed(name) or target.suffix.lower() not in self.extensions:continue
                    try:
                        if emit or target.lstat().st_ctime>=recent_since:files.append(target)
                    except FileNotFoundError:pass
        return files
    def remove_tree(self,path):
        for wd,target in list(self.paths.items()):
            if target==path or path in target.parents:
                self.paths.pop(wd,None);self.reverse.pop(target,None)
                self.lib.inotify_rm_watch(self.fd,wd)
    def read(self,timeout=30):
        changed=[];overflow=False
        if not select.select([self.fd],[],[],timeout)[0]:return changed,overflow
        while True:
            try:data=os.read(self.fd,256*1024)
            except BlockingIOError:break
            for wd,mask,name in parse(data):
                if mask&OVERFLOW:overflow=True;continue
                base=self.paths.get(wd)
                if base is None:continue
                path=base/name if name else base
                if mask&IGNORED:
                    self.paths.pop(wd,None);self.reverse.pop(base,None);continue
                if mask&(DELETE_SELF|MOVE_SELF):self.remove_tree(base);continue
                if not allowed(name):continue
                if mask&ISDIR:
                    if mask&(MOVED_FROM|DELETE):self.remove_tree(path)
                    elif mask&(MOVED_TO|CREATE):changed.extend(self.add_tree(path,emit=True))
                elif mask&(CLOSE_WRITE|MOVED_TO) and path.suffix.lower() in self.extensions:
                    changed.append(path)
        return changed,overflow
