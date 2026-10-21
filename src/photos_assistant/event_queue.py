"""Root-private durable work queue. No Photos database access."""
import json
import os
from pathlib import Path
import sqlite3
import stat
import time

class Queue:
    def __init__(self,state):
        self.path=Path(state)/'events.sqlite3'
        if self.path.exists() or self.path.is_symlink():
            info=self.path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o022 or info.st_nlink!=1:
                raise RuntimeError('Unsafe event queue')
        self.db=sqlite3.connect(str(self.path),timeout=10)
        self.db.row_factory=sqlite3.Row
        os.chmod(self.path,0o600)
        self.db.executescript('''PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS contexts (key TEXT PRIMARY KEY,runner TEXT,space TEXT,root TEXT,offset INTEGER DEFAULT 0,scanned INTEGER DEFAULT 0,api_due REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS jobs (context TEXT,item INTEGER,phase TEXT,due REAL,token TEXT,force INTEGER DEFAULT 0,PRIMARY KEY(context,item,phase));
CREATE INDEX IF NOT EXISTS jobs_due ON jobs(phase,due);
CREATE TABLE IF NOT EXISTS events (context TEXT,relative TEXT,due REAL,created REAL,signature TEXT,attempts INTEGER DEFAULT 0,PRIMARY KEY(context,relative));
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT);
''')
        self.db.commit()
    def close(self): self.db.close()
    def contexts(self): return self.db.execute('SELECT * FROM contexts ORDER BY key').fetchall()
    def context(self,key): return self.db.execute('SELECT * FROM contexts WHERE key=?',(key,)).fetchone()
    def add_context(self,key,runner,space,root):
        with self.db:
            old=self.context(key)
            if old and old['root']==str(root): return
            self.db.execute('INSERT OR REPLACE INTO contexts(key,runner,space,root) VALUES (?,?,?,?)',(key,runner,space,str(root)))
    def reconcile(self,reason):
        with self.db:
            self.db.execute('UPDATE contexts SET offset=0,scanned=0,api_due=0')
            self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('reconcile_reason',reason))
    def request_reconcile(self,reason):
        with self.db:self.db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('reconcile_request',reason))
    def take_reconcile(self):
        with self.db:
            row=self.db.execute('SELECT value FROM meta WHERE key=?',('reconcile_request',)).fetchone()
            self.db.execute('DELETE FROM meta WHERE key=?',('reconcile_request',))
        return row['value'] if row else None
    def scan_page(self,key,count):
        with self.db:
            self.db.execute('UPDATE contexts SET offset=offset+?,scanned=? WHERE key=?',(count,int(count<100),key))
    def api_failure(self,key,scan=False):
        with self.db:
            self.db.execute('UPDATE contexts SET api_due=?,scanned=CASE WHEN ? THEN 1 ELSE scanned END WHERE key=?',(time.time()+3600,int(scan),key))
    def has_scan(self): return bool(self.db.execute('SELECT 1 FROM contexts WHERE scanned=0 AND api_due<=? LIMIT 1',(time.time(),)).fetchone())
    def add_job(self,context,item,phase,token,force=False,due=None):
        due=time.time() if due is None else due
        with self.db:
            self.db.execute('''INSERT INTO jobs VALUES (?,?,?,?,?,?) ON CONFLICT(context,item,phase) DO UPDATE SET
 due=CASE WHEN jobs.token!=excluded.token THEN excluded.due ELSE jobs.due END,
 force=max(jobs.force,excluded.force),token=excluded.token''',(context,item,phase,due,token,int(force)))
    def next_job(self,allow_video=True):
        return self.db.execute('''SELECT j.* FROM jobs j JOIN contexts c ON c.key=j.context
 WHERE j.due<=? AND c.api_due<=? AND (? OR j.phase='preview')
 ORDER BY j.phase,j.due LIMIT 1''',(time.time(),time.time(),int(allow_video))).fetchone()
    def finish(self,job):
        with self.db:self.db.execute('DELETE FROM jobs WHERE context=? AND item=? AND phase=?',(job['context'],job['item'],job['phase']))
    def retry(self,job,delay):
        with self.db:self.db.execute('UPDATE jobs SET due=? WHERE context=? AND item=? AND phase=?',(time.time()+delay,job['context'],job['item'],job['phase']))
    def add_events(self,events):
        now=time.time()
        with self.db:
            self.db.executemany('''INSERT INTO events(context,relative,due,created) VALUES (?,?,?,?)
 ON CONFLICT(context,relative) DO UPDATE SET due=excluded.due,created=excluded.created,signature=NULL,attempts=0''',[(key,relative,now+5,now) for key,relative in events])
    def ready_events(self):
        return self.db.execute('''SELECT e.* FROM events e JOIN contexts c ON c.key=e.context
 WHERE e.due<=? AND c.api_due<=? ORDER BY e.due LIMIT 100''',(time.time(),time.time())).fetchall()
    def event_retry(self,event,delay,signature=None):
        with self.db:self.db.execute('UPDATE events SET due=?,signature=coalesce(?,signature),attempts=attempts+1 WHERE context=? AND relative=?',(time.time()+delay,signature,event['context'],event['relative']))
    def event_done(self,event):
        with self.db:self.db.execute('DELETE FROM events WHERE context=? AND relative=?',(event['context'],event['relative']))
    def fresh_events(self):
        return bool(self.db.execute('SELECT 1 FROM events e JOIN contexts c ON c.key=e.context WHERE e.created>=? AND c.api_due<=? LIMIT 1',(time.time()-60,time.time())).fetchone())
    def next_delay(self,allow_video=True):
        rows=self.db.execute('''SELECT min(when_due) AS due FROM (
 SELECT max(j.due,c.api_due) AS when_due FROM jobs j JOIN contexts c ON c.key=j.context WHERE (? OR j.phase='preview')
 UNION ALL SELECT max(e.due,c.api_due) FROM events e JOIN contexts c ON c.key=e.context
 UNION ALL SELECT api_due FROM contexts WHERE scanned=0)''',(int(allow_video),)).fetchone()
        return max(0.05,min(60,(rows['due']-time.time()) if rows['due'] is not None else 60))
    def counts(self):
        return {kind:self.db.execute('SELECT count(*) FROM '+kind).fetchone()[0] for kind in ('jobs','events')}
