#!/usr/bin/env python3
"""Root-only local API coordinator; all untrusted media decoding runs unprivileged."""
import argparse
import ctypes
import contextlib
import fcntl
import json
import logging
import logging.handlers
import os
from pathlib import Path
import pwd
import resource
import shutil
import signal
import stat
import subprocess
import sys
import secrets
from hardware import device_for, preference
from types import SimpleNamespace
import tempfile
import time
from worker import ApiError, atomic_json, assert_photos_version, require_space, MAX_OUTPUT_BYTES

VIDEO_EXT={'.3g2','.3gp','.asf','.avi','.divx','.m4v','.mov','.mpeg','.mpg','.mp4','.mts','.m2t','.m2ts','.qt','.wmv','.xvid'}
IMAGE_EXT={'.heic','.heif','.hif'}
MISSING={'ame_defect','broken'}
BATCH_SIZE=20
ADDITIONAL=['thumbnail','video_convert','resolution']

IDENTITY_FIELDS=('filename','filesize','indexed_time','folder_id','owner_user_id')

def source_identity(entry):
    return {key:entry.get(key) for key in IDENTITY_FIELDS}

def needs(entry,previous=None):
    ext=Path(entry.get('filename','')).suffix.lower()
    add=entry.get('additional',{})
    thumb=add.get('thumbnail',{})
    preview=ext in VIDEO_EXT|IMAGE_EXT and any(thumb.get(k) in MISSING for k in ('sm','m','xl'))
    video=(ext in VIDEO_EXT and add.get('video_convert_status') in MISSING
           and not any(v.get('quality')=='high' for v in add.get('video_convert',[])))
    if (previous and previous.get('source_compatible') is True
            and previous.get('source_identity')==source_identity(entry)
            and previous.get('cache_key')==thumb.get('cache_key')):
        video=False
    return bool(thumb.get('unit_id')) and preview, bool(thumb.get('unit_id')) and video

def phase_needs(entry,previous,phase):
    preview,video=needs(entry,previous)
    return preview and phase!='video',video and phase!='preview'


class NativePhotos:
    """No shell, credentials, session tokens, HTTP listener, or general command proxy."""
    def __init__(self, runner, state):
        self.runner=runner
        self.state=Path(state)
    def invoke(self, api, method, version, destination, **params):
        if api not in {'SYNO.Foto'+suffix for suffix in ('.Browse.RecentlyAdded','.Browse.Item','.Browse.Folder','.Download','.Upload.ConvertedFile')} | {'SYNO.FotoTeam'+suffix for suffix in ('.Browse.RecentlyAdded','.Browse.Item','.Browse.Folder','.Download','.Upload.ConvertedFile')}:
            raise ValueError('API not allowed')
        command=['/usr/syno/bin/synowebapi','--exec','api='+api,'method='+method,
                 'version='+str(version),'runner='+self.runner,'outfile='+str(destination)]
        command += [key+'='+json.dumps(value,separators=(',',':')) for key,value in params.items()]
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600,
                              env={'PATH':'/usr/bin:/bin','LANG':'C'})
        if not destination.is_file() or not destination.stat().st_size:
            # Different local handlers send JSON to stdout instead of outfile.
            try: json.loads(result.stdout)
            except (ValueError,TypeError): raise ApiError('empty_local_response')
            destination.write_bytes(result.stdout)
        return result
    def call(self, api, method, version=4, **params):
        with tempfile.TemporaryDirectory(prefix='api-',dir=str(self.state)) as d:
            response=Path(d)/'response.json'
            self.invoke(api,method,version,response,**params)
            result=json.loads(response.read_text())
            if not result.get('success'): raise ApiError(result.get('error',{}).get('code'))
            return result.get('data',{})
    def list(self, space, offset):
        return self.call(space+'.Browse.Item','list',4,offset=offset,limit=100,additional=ADDITIONAL).get('list',[])
    def get(self, space, item_id):
        entries=self.call(space+'.Browse.Item','get',4,id=[item_id],additional=ADDITIONAL).get('list',[])
        if len(entries)!=1: raise ValueError('Item disappeared')
        return entries[0]
    def open_original(self, entry):
        folder=self.call(entry['_space']+'.Browse.Folder','get',2,id=entry['folder_id']).get('folder',{})
        if folder.get('id')!=entry['folder_id'] or folder.get('owner_user_id')!=entry.get('owner_user_id'):
            raise ValueError('Original folder identity changed')
        name=entry['filename']
        if not name or name in ('.','..') or '/' in name or '\x00' in name:
            raise ValueError('Unsafe original filename')
        relative=folder.get('name','')
        if not relative.startswith('/') or any(p in ('.','..') for p in relative.split('/')):
            raise ValueError('Unsafe original folder')
        if entry['_space']=='SYNO.Foto':
            base=Path(pwd.getpwnam(self.runner).pw_dir)
            parts=['Photos']
        elif entry['_space']=='SYNO.FotoTeam':
            base=Path('/var/services/photo');parts=[]
        else: raise ValueError('Unknown Photos space')
        parts += [p for p in relative.split('/') if p]
        directory=os.open(str(base.resolve(strict=True)),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            for part in parts:
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
                os.close(directory);directory=child
            return os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        finally: os.close(directory)
    def upload(self, space, unit, outputs):
        params={'unit_id':unit}
        for name,path in outputs.items():
            if name not in {'thumb_sm','thumb_m','thumb_xl','film_h264'}: raise ValueError('Output not allowed')
            params[name]=path.name
            params[name+'_tmp']=str(path)
        return self.call(space+'.Upload.ConvertedFile','upload',3,**params)

def candidates():
    return sorted((p for p in pwd.getpwall() if 1024<=p.pw_uid<65534
                   and p.pw_dir.startswith('/var/services/homes/') and Path(p.pw_dir).is_dir()),key=lambda p:p.pw_uid)

def sandbox(uid,gid,gpu_gid=None):
    def enter():
        # Fail closed if network namespaces are unavailable; no decoder network access.
        libc=ctypes.CDLL(None,use_errno=True)
        if libc.unshare(0x40000000)!=0: raise OSError(ctypes.get_errno(),'network isolation failed')
        if libc.prctl(38,1,0,0,0)!=0: raise OSError('no_new_privs failed')
        os.setgroups([] if gpu_gid is None else ([gpu_gid] if isinstance(gpu_gid,int) else gpu_gid));os.setgid(gid);os.setuid(uid);os.umask(0o077)
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
        resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_OUTPUT_BYTES,MAX_OUTPUT_BYTES))
        resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
        os.nice(10)
    return enter

def checked_copy(source,destination,uid,max_bytes):
    fd=os.open(str(source),os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=uid or info.st_nlink!=1 or info.st_size>max_bytes:
            raise ValueError('Unsafe output')
        with os.fdopen(fd,'rb',closefd=False) as src,destination.open('xb') as dst:
            while True:
                require_space(destination.parent)
                chunk=src.read(1024*1024)
                if not chunk: break
                if dst.tell()+len(chunk)>max_bytes: raise ValueError('Output size limit')
                dst.write(chunk)
    finally: os.close(fd)

def fingerprint(info):
    return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)

@contextlib.contextmanager
def open_input(api,entry):
    """Keep one read-only original FD open; it is the decoder's only source grant."""
    fd=api.open_original(entry)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size<=0 or info.st_size!=int(entry['filesize']):
            raise ValueError('Original size or type changed')
        if fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE!=os.O_RDONLY:
            raise ValueError('Original descriptor is not read-only')
        expected=fingerprint(info)
        def verify():
            if fingerprint(os.fstat(fd))!=expected: raise ValueError('Original changed while decoding')
        yield fd,verify
    finally: os.close(fd)

def process(api,entry,state,package,commit=True,phase='all',previous=None):
    preview,video=phase_needs(entry,previous,phase)
    if not (preview or video): return False
    if int(entry.get('filesize',0))<=0: return False
    require_space(state,1024**3)
    unit=entry['additional']['thumbnail']['unit_id'];item=entry['id']
    ext=Path(entry['filename']).suffix.lower()
    with tempfile.TemporaryDirectory(prefix='job-',dir=str(state)) as d:
        job=Path(d);os.chmod(job,0o711)
        decode=job/'decode';decode.mkdir(mode=0o700);os.chown(decode,package.pw_uid,package.pw_gid)
        with open_input(api,entry) as (source_fd,verify_original):
            cmd=['/bin/python3',str(Path(__file__).with_name('decode_job.py')),str(decode),
                 str(int(preview)),str(int(video)),str(source_fd),ext]
            resolution=entry.get('additional',{}).get('resolution',{})
            if ext in IMAGE_EXT:
                cmd += [str(int(resolution.get('width',0))),str(int(resolution.get('height',0)))]
            gpu=device_for(Path(__file__).parent/'runtime',preference(state)) if video else None
            if gpu: cmd+=['--hardware',json.dumps(gpu,separators=(',',':'))]
            logging.info('item=%s source=readonly-fd bytes=%s',item,entry['filesize'])
            child=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,
                                   pass_fds=(source_fd,),env={'PATH':'/usr/bin:/bin','LANG':'C'},
                                   preexec_fn=sandbox(package.pw_uid,package.pw_gid,gpu['groups'] if gpu else None))
            try:
                out,err=child.communicate(timeout=22000)
            except BaseException:
                os.killpg(child.pid,signal.SIGKILL);child.wait();raise
            if child.returncode:
                reasons={b'DECODER_FAILURE='+reason.encode():reason for reason in
                         ('compatibility','duration','timeout','command','other')}
                reason=next((reasons[line] for line in err.splitlines() if line in reasons),'unknown')
                logging.warning('item=%s decoder_failure=%s exit=%s',item,reason,child.returncode)
                raise RuntimeError('Decoder failed')
            for backend in ('vaapi','qsv','nvenc','software'):
                if ('VIDEO_BACKEND='+backend).encode() in out.splitlines():
                    logging.info('item=%s video-backend=%s',item,backend)
            for driver in ('iHD','i965','radeonsi'):
                if ('VIDEO_DRIVER='+driver).encode() in out.splitlines():
                    logging.info('item=%s video-driver=%s',item,driver)
            for path in ('cpu-tonemapx','cpu-zscale'):
                if ('VIDEO_COLOR_PATH='+path).encode() in out.splitlines():
                    logging.info('item=%s video-color-path=%s',item,path)
            if b'VIDEO_PREFILTER=vaapi' in out.splitlines():
                logging.info('item=%s video-prefilter=vaapi',item)
            if b'HARDWARE_FALLBACK=software' in out.splitlines():
                logging.info('item=%s hardware-fallback=software',item)
            source_compatible=(video and b'SOURCE_COMPATIBLE' in out.splitlines()) or (
                not video and previous is not None and previous.get('source_compatible') is True
                and previous.get('source_identity')==source_identity(entry)
                and previous.get('cache_key')==entry.get('additional',{}).get('thumbnail',{}).get('cache_key'))
            if video and not source_compatible and not (decode/'compatible.mp4').exists():
                raise RuntimeError('Decoder returned no video decision')
            if source_compatible:
                logging.info('item=%s video=source-compatible',item)
            verify_original()
            fresh=api.get(entry['_space'],item)
            if fresh.get('additional',{}).get('thumbnail',{}).get('unit_id')!=unit: raise ValueError('Item changed')
            if any(fresh.get(k)!=entry.get(k) for k in ('filename','filesize','indexed_time','folder_id','owner_user_id')):
                raise ValueError('Original changed while decoding')
            still_preview,still_video=needs(fresh)
            expected={}
            if preview and still_preview:
                expected.update({'thumb_'+k.lower():k+'.jpg' for k in ('SM','M','XL')
                                 if fresh['additional']['thumbnail'].get(k.lower()) in MISSING})
            if video and still_video and (decode/'compatible.mp4').exists(): expected['film_h264']='compatible.mp4'
            publish=job/'publish';publish.mkdir(mode=0o711);os.chmod(publish,0o711)
            outputs={}
            account=pwd.getpwnam(api.runner)
            for key,name in expected.items():
                target=publish/name
                checked_copy(decode/name,target,package.pw_uid,MAX_OUTPUT_BYTES)
                os.chown(target,account.pw_uid,account.pw_gid);os.chmod(target,0o400)
                outputs[key]=target
            cache_key=fresh.get('additional',{}).get('thumbnail',{}).get('cache_key')
            if outputs and commit:
                # DSM local ConvertedFile can return an empty/117 transport reply even
                # after accepting files. Only freshly read Photos state proves success.
                try: api.upload(entry['_space'],unit,outputs)
                except ApiError: pass
                for attempt in range(6):
                    updated=api.get(entry['_space'],item).get('additional',{})
                    thumbnails=updated.get('thumbnail',{})
                    ready=all(thumbnails.get(key[6:])=='ready' for key in outputs if key.startswith('thumb_'))
                    if 'film_h264' in outputs:
                        ready=ready and updated.get('video_convert_status')=='ready' and any(
                            variant.get('quality')=='high' for variant in updated.get('video_convert',[]))
                    if ready:
                        cache_key=thumbnails.get('cache_key')
                        break
                    time.sleep(1)
                else: raise RuntimeError('Photos did not accept generated files')
            if commit:
                atomic_json(state/('item-%s-%s.json' % (api.runner,item)),
                            {'item':item,'space':entry['_space'],'bytes':sum(p.stat().st_size for p in outputs.values()),
                             'outputs':list(outputs),'cache_key':cache_key,
                             'source_compatible':bool(source_compatible),'source_identity':source_identity(fresh)})
    return True

def scan_progress(offset,page_size,processed,batch_size=BATCH_SIZE):
    """Keep draining work/pages; wait only after reaching the collection end."""
    if processed>=batch_size: return offset,True
    if page_size==100: return offset+100,True
    return 0,processed>0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['once','daemon','reconcile'])
    parser.add_argument('--state',type=Path,default=Path('/volume1/@PhotosAssistantNAS/state'))
    parser.add_argument('--test-item',type=int,action='append')
    parser.add_argument('--runner')
    args=parser.parse_args()
    if os.geteuid()!=0: raise RuntimeError('Local API coordinator requires root')
    logging.getLogger().setLevel(logging.INFO)
    os.umask(0o077);args.state.mkdir(mode=0o711,parents=True,exist_ok=True);os.chmod(args.state,0o711)
    # Root code/state must not be replaceable by the decoder package identity.
    for folder in (Path(__file__).resolve().parent,args.state.resolve()):
        info=folder.stat()
        if info.st_uid!=0 or info.st_mode&0o022: raise RuntimeError('Untrusted coordinator directory')
    if args.action=='reconcile':
        from event_queue import Queue
        queue=Queue(args.state);queue.request_reconcile('manual-request');queue.close()
        print('History reconciliation requested; existing media are unchanged.')
        return
    lock=(args.state/'native.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for pattern in ('job-*','api-*'):
        for leftover in args.state.glob(pattern):
            if leftover.is_symlink(): leftover.unlink()
            elif leftover.is_dir(): shutil.rmtree(leftover)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',handlers=[logging.handlers.RotatingFileHandler(str(args.state/'worker.log'),maxBytes=2*1024**2,backupCount=2)])
    signal.signal(signal.SIGTERM,lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    # A numeric, unused UID needs no login account or password database entry.
    while True:
        uid=2147000000+secrets.randbelow(100000)
        try: pwd.getpwuid(uid)
        except KeyError: break
    package=SimpleNamespace(pw_uid=uid,pw_gid=uid)
    if args.action=='daemon' and not args.test_item:
        from event_scheduler import run
        run(args,package)
        return
    retry_path=args.state/'retry.json'
    retries=json.loads(retry_path.read_text()) if retry_path.exists() else {}
    cursors_path=args.state/'native-priority-cursors.json'
    cursors=json.loads(cursors_path.read_text()) if cursors_path.exists() else {}
    api_retry={}
    phase='all' if args.action=='once' else 'preview'
    while True:
        busy=False
        completed=0
        batch_size=2 if phase=='video' else BATCH_SIZE
        assert_photos_version()
        users=[pwd.getpwnam(args.runner)] if args.runner else candidates()
        for user in users:
            api=NativePhotos(user.pw_name,args.state)
            for space in (('SYNO.Foto',) if args.test_item else ('SYNO.Foto','SYNO.FotoTeam')):
                api_key=user.pw_name+':'+space
                key=api_key+':'+phase
                if api_retry.get(api_key,0)>time.time(): continue
                try:
                    offset=cursors.get(key,0)
                    # Watch newest media while progressing through older pages.
                    pages=[(0,[api.get(space,item) for item in args.test_item])] if args.test_item else [(0,api.list(space,0))]
                    if offset and not args.test_item: pages.append((offset,api.list(space,offset)))
                    count=0
                    for _,entries in pages:
                        for entry in entries:
                            if args.test_item and entry['id'] not in args.test_item: continue
                            ledger=args.state/('item-%s-%s.json' % (user.pw_name,entry['id']))
                            previous=json.loads(ledger.read_text()) if ledger.exists() else None
                            if not any(phase_needs(entry,previous,phase)): continue
                            retry_key=api_key+':'+str(entry['id'])+':'+phase
                            if retries.get(retry_key,0)>time.time(): continue
                            entry['_space']=space
                            try:
                                if process(api,entry,args.state,package,phase=phase,previous=previous):
                                    logging.info('item=%s processed phase=%s',entry['id'],phase);count+=1;completed+=1
                            except Exception as error:
                                logging.warning('item=%s failed=%s',entry['id'],type(error).__name__)
                                retries[retry_key]=time.time()+3600
                                atomic_json(retry_path,retries)
                            if count>=batch_size: break
                        if count>=batch_size: break
                    last=pages[-1][1]
                    cursors[key],more=scan_progress(offset,len(last),count,batch_size)
                    busy=busy or more
                    atomic_json(cursors_path,cursors)
                except ApiError as error:
                    logging.info('Local API unavailable code=%s',error.code)
                    api_retry[api_key]=time.time()+60
                except Exception as error:
                    logging.warning('Scan failed=%s',type(error).__name__)
                    api_retry[api_key]=time.time()+60
        if args.action=='once': return
        if phase=='preview':
            if not busy:
                phase='video'
                logging.info('scheduler phase=video previews-scan-complete')
        elif completed or not busy:
            phase='preview'
            logging.info('scheduler phase=preview')
            if not completed and not busy: time.sleep(60)

if __name__=='__main__': main()
