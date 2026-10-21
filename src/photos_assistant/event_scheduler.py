"""Event-driven coordinator with a durable queue and bounded, targeted index lookups."""
from collections import defaultdict
import json
import logging
import os
from pathlib import Path
import select
import subprocess
import time
import native_worker as n
from event_queue import Queue
from file_events import allowed

PENDING={'pending','processing','converting'}

def previous(state,context,item):
    path=Path(state)/('item-%s-%s.json'%(context['runner'],item))
    try: data=json.loads(path.read_text())
    except FileNotFoundError:return None
    except (ValueError,OSError):
        logging.warning('item=%s unreadable-ledger',item);return None
    return data if data.get('space')==context['space'] else None

def pending(entry,phase):
    ext=Path(entry.get('filename','')).suffix.lower();add=entry.get('additional',{});thumb=add.get('thumbnail',{})
    if phase=='preview':
        return ext in n.IMAGE_EXT|n.VIDEO_EXT and (not thumb.get('unit_id') or any(thumb.get(k) in PENDING for k in ('sm','m','xl')))
    return ext in n.VIDEO_EXT and add.get('video_convert_status') in PENDING

def enqueue(q,state,context,entry,force=False):
    old=None if force else previous(state,context,entry['id'])
    preview,video=n.needs(entry,old)
    token=json.dumps([n.source_identity(entry),entry.get('additional',{}).get('thumbnail',{}).get('cache_key')],sort_keys=True)
    for phase,needed in (('preview',preview),('video',video)):
        if needed or pending(entry,phase):
            due=time.time()+(30 if not needed else 0)
            if not force:due=max(due,getattr(q,'legacy_retry',{}).get(context['key']+':'+str(entry['id'])+':'+phase,0))
            q.add_job(context['key'],entry['id'],phase,token,force=force,due=due)

def discover(q,args):
    users=[n.pwd.getpwnam(args.runner)] if args.runner else n.candidates()
    for user in users:
        personal=Path(user.pw_dir)/'Photos'
        if personal.is_dir() and not personal.is_symlink():q.add_context(user.pw_name+':SYNO.Foto',user.pw_name,'SYNO.Foto',personal.resolve())
        shared=Path('/var/services/photo')
        if shared.is_dir():q.add_context(user.pw_name+':SYNO.FotoTeam',user.pw_name,'SYNO.FotoTeam',shared.resolve())

def scan_step(q,state):
    context=q.db.execute('SELECT * FROM contexts WHERE scanned=0 AND api_due<=? ORDER BY key LIMIT 1',(time.time(),)).fetchone()
    if context is None:return False
    try:
        api=n.NativePhotos(context['runner'],state);entries=api.list(context['space'],context['offset'])
        for entry in entries:enqueue(q,state,context,entry)
        q.scan_page(context['key'],len(entries))
        if len(entries)<100:logging.info('event-scheduler history-complete space=%s',context['space'])
    except n.ApiError as error:
        q.api_failure(context['key'],scan=True);logging.info('event-scheduler context-unavailable code=%s',error.code)
    return True

def source_stat(context,relative):
    rel=Path(relative)
    if rel.is_absolute() or '..' in rel.parts or not allowed(rel):raise ValueError('Unsafe event path')
    root=Path(context['root']).resolve(strict=True);target=root/rel
    if target.is_symlink():raise ValueError('Symlink event source')
    resolved=target.resolve(strict=True)
    if root not in resolved.parents:raise ValueError('Event outside photo root')
    info=target.stat()
    if not n.stat.S_ISREG(info.st_mode):raise ValueError('Event is not a regular file')
    return info,json.dumps(n.fingerprint(info))

def resolve_events(q,state):
    grouped=defaultdict(list)
    for event in q.ready_events():
        context=q.context(event['context'])
        try:info,signature=source_stat(context,event['relative'])
        except (OSError,ValueError,RuntimeError):q.event_done(event);continue
        if signature!=event['signature']:
            q.event_retry(event,3,signature);continue
        grouped[(context['key'],str(Path(event['relative']).parent))].append((event,info))
    for (key,parent),events in grouped.items():
        context=q.context(key);api=n.NativePhotos(context['runner'],state);folder_name='/' if parent=='.' else '/'+Path(parent).as_posix()
        try:
            folder=api.call(context['space']+'.Browse.Folder','get',2,name=folder_name).get('folder',{})
            if folder.get('name')!=folder_name:raise ValueError('Photos folder is not indexed')
            wanted={Path(event['relative']).name:(event,info) for event,info in events};offset=0
            while wanted:
                entries=api.call(context['space']+'.Browse.Item','list',4,folder_id=folder['id'],offset=offset,limit=100,additional=n.ADDITIONAL).get('list',[])
                for entry in entries:
                    match=wanted.get(entry.get('filename'))
                    if match is None:continue
                    event,info=match
                    # Photos must have an indexed item that matches the stable source size.
                    if int(entry.get('filesize',-1))!=info.st_size:continue
                    enqueue(q,state,context,entry,force=True);q.event_done(event);wanted.pop(entry['filename'])
                    logging.info('item=%s event=index-ready',entry['id'])
                offset+=len(entries)
                if len(entries)<100:break
            for event,info in wanted.values():q.event_retry(event,min(300,10*2**min(event['attempts'],5)))
        except n.ApiError as error:
            # A newly created folder can precede its Photos index entry.
            if error.code in (117,603,801):q.api_failure(key)
            for event,info in events:q.event_retry(event,30)
        except ValueError:
            for event,info in events:q.event_retry(event,10)
    return bool(grouped)

def process_job(q,state,package,job):
    context=q.context(job['context']);api=n.NativePhotos(context['runner'],state)
    try:
        entry=api.get(context['space'],job['item']);entry['_space']=context['space']
        old=None if job['force'] else previous(state,context,entry['id'])
        preview,video=n.needs(entry,old);needed=preview if job['phase']=='preview' else video
        if not needed:
            if pending(entry,job['phase']):q.retry(job,60)
            else:q.finish(job)
            return
        if n.process(api,entry,Path(state),package,phase=job['phase'],previous=old):
            logging.info('item=%s processed phase=%s source=queue',entry['id'],job['phase'])
        q.finish(job)
    except n.ApiError as error:
        q.api_failure(context['key']);q.retry(job,3600);logging.info('item=%s context-unavailable code=%s',job['item'],error.code)
    except ValueError as error:
        if str(error)=='Item disappeared':q.finish(job);logging.info('item=%s queue-item-removed',job['item'])
        else:q.retry(job,3600);logging.warning('item=%s failed=%s',job['item'],type(error).__name__)
    except Exception as error:
        q.retry(job,3600);logging.warning('item=%s failed=%s',job['item'],type(error).__name__)

def run(args,package):
    q=Queue(args.state)
    try:q.legacy_retry=json.loads((args.state/'retry.json').read_text())
    except (FileNotFoundError,ValueError):q.legacy_retry={}
    if not isinstance(q.legacy_retry,dict):q.legacy_retry={}
    discover(q,args);q.reconcile('startup-recovery')
    read_fd,write_fd=os.pipe2(os.O_NONBLOCK|os.O_CLOEXEC)
    watcher_log=(args.state/'events.log').open('ab',buffering=0)
    watcher=subprocess.Popen(['/bin/python3','-I',str(Path(__file__).with_name('event_watch.py')),
        '--state',str(args.state),'--parent',str(os.getpid()),'--notify-fd',str(write_fd)],
        pass_fds=(write_fd,),stdout=subprocess.DEVNULL,stderr=watcher_log,env={'PATH':'/usr/bin:/bin','LANG':'C'})
    os.close(write_fd);refresh=time.monotonic();idle=False
    logging.info('event-scheduler started mode=inotify durable-queue=enabled')
    try:
        if not select.select([read_fd],[],[],60)[0] or b'R' not in os.read(read_fd,65536):
            raise RuntimeError('Filesystem event collector did not become ready')
        while True:
            n.assert_photos_version()
            if watcher.poll() is not None:raise RuntimeError('Filesystem event collector stopped; inspect events.log')
            if time.monotonic()-refresh>=300:
                discover(q,args);refresh=time.monotonic()
            reason=q.take_reconcile()
            if reason:q.reconcile(reason);logging.info('event-scheduler reconciliation reason=%s',reason)
            resolve_events(q,args.state)
            scanning=scan_step(q,args.state)
            allow_video=not q.has_scan() and not q.fresh_events()
            job=q.next_job(allow_video=allow_video)
            if job is not None:
                idle=False;process_job(q,args.state,package,job);continue
            if scanning:idle=False;continue
            if not idle:logging.info('event-scheduler idle %s',json.dumps(q.counts(),sort_keys=True));idle=True
            if select.select([read_fd],[],[],q.next_delay(allow_video))[0]:
                try:os.read(read_fd,65536)
                except BlockingIOError:pass
    finally:
        watcher.terminate()
        try:watcher.wait(timeout=10)
        except subprocess.TimeoutExpired:watcher.kill();watcher.wait()
        os.close(read_fd);watcher_log.close();q.close()
