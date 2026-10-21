#!/usr/bin/env python3
"""Separate root event collector, so long decoder jobs cannot lose event wakeups."""
import argparse
import logging
import os
from pathlib import Path
import signal
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from event_queue import Queue
from file_events import Monitor

EXTENSIONS={'.heic','.heif','.hif','.3g2','.3gp','.asf','.avi','.divx','.m4v','.mov','.mpeg','.mpg','.mp4','.mts','.m2t','.m2ts','.qt','.wmv','.xvid'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);p.add_argument('--parent',type=int,required=True);p.add_argument('--notify-fd',type=int,required=True);args=p.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Event collector requires root')
    os.umask(0o077);signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
    q=Queue(args.state);monitor=Monitor(EXTENSIONS);seen=set();reported_incomplete=False;announced=False;started=time.time()
    def wake():
        try:os.write(args.notify_fd,b'1')
        except BlockingIOError:pass
    try:
        while os.getppid()==args.parent:
            contexts=q.contexts();roots={Path(c['root']) for c in contexts};startup_paths=[]
            for root in roots:
                if root.is_dir() and root not in monitor.reverse:
                    startup_paths.extend(monitor.add_tree(root,recent_since=started-60))
                    if root in seen:q.request_reconcile('root-watch-restored');wake()
                    seen.add(root)
            if monitor.incomplete and not reported_incomplete:
                raise RuntimeError('Event watch coverage incomplete; repair inotify capacity or permissions')
            if not announced:
                os.write(args.notify_fd,b'R');announced=True
            paths,overflow=monitor.read(0 if startup_paths else 30)
            paths=startup_paths+paths
            if overflow:q.request_reconcile('inotify-overflow');wake()
            events=set()
            for path in paths:
                for c in contexts:
                    try:relative=path.relative_to(Path(c['root']))
                    except ValueError:continue
                    events.add((c['key'],str(relative)))
            if events:q.add_events(events);wake()
    finally:monitor.close();q.close()

if __name__=='__main__':main()
