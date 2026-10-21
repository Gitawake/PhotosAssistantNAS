from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import json
import os
import struct
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/photos_assistant'))
from event_queue import Queue
from file_events import parse,allowed,CLOSE_WRITE,MOVED_TO
import event_scheduler as scheduler

class EventTests(unittest.TestCase):
    def context(self,q,root):
        q.add_context('user:SYNO.Foto','user','SYNO.Foto',root)
        return q.context('user:SYNO.Foto')
    def test_queue_survives_restart_and_prioritizes_thumbnails(self):
        with tempfile.TemporaryDirectory() as td:
            q=Queue(td);c=self.context(q,td)
            q.add_job(c['key'],1,'video','a');q.add_job(c['key'],2,'preview','b')
            q.close();q=Queue(td)
            self.assertEqual(q.next_job()['item'],2)
            q.finish(q.next_job());self.assertIsNone(q.next_job(allow_video=False));self.assertEqual(q.next_job()['item'],1)
            self.assertEqual(q.path.stat().st_mode&0o777,0o600);q.close()
    def test_duplicate_metadata_preserves_retry_but_changed_item_wakes_job(self):
        with tempfile.TemporaryDirectory() as td:
            q=Queue(td);c=self.context(q,td);q.add_job(c['key'],1,'video','v1');q.retry(q.next_job(),3600)
            q.add_job(c['key'],1,'video','v1');self.assertIsNone(q.next_job())
            q.add_job(c['key'],1,'video','v2',force=True);self.assertEqual(q.next_job()['force'],1);q.close()
    def test_pending_event_survives_restart_and_is_debounced(self):
        with tempfile.TemporaryDirectory() as td:
            q=Queue(td);c=self.context(q,td);q.add_events([(c['key'],'album/clip.mp4')]);q.add_events([(c['key'],'album/clip.mp4')])
            self.assertEqual(q.counts()['events'],1);self.assertEqual(q.ready_events(),[])
            q.close();q=Queue(td);self.assertEqual(q.counts()['events'],1);q.close()
    def test_inotify_parser_and_generated_cache_exclusion(self):
        name=b'clip.mp4\0';data=struct.pack('iIII',7,CLOSE_WRITE,0,len(name))+name
        self.assertEqual(list(parse(data)),[(7,CLOSE_WRITE,'clip.mp4')])
        self.assertFalse(allowed('album/@eaDir/clip.mp4'));self.assertFalse(allowed('#recycle/clip.mp4'));self.assertTrue(allowed('album/clip.mp4'))
        with self.assertRaises(ValueError):list(parse(data[:-1]))
    def test_source_stability_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);photos=root/'photos';photos.mkdir();(root/'outside.mp4').write_bytes(b'private');(photos/'clip.mp4').write_bytes(b'first')
            c={'root':str(photos)};one=scheduler.source_stat(c,'clip.mp4')[1];(photos/'clip.mp4').write_bytes(b'changed')
            self.assertNotEqual(one,scheduler.source_stat(c,'clip.mp4')[1])
            (photos/'escape.mp4').symlink_to(root/'outside.mp4')
            for relative in ('escape.mp4','../outside.mp4','/absolute.mp4'):
                with self.assertRaises(ValueError):scheduler.source_stat(c,relative)
    def test_targeted_folder_lookup_waits_for_stable_source_and_matching_size(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);photos=root/'photos';(photos/'album').mkdir(parents=True);(photos/'album/clip.mp4').write_bytes(b'original')
            q=Queue(td);c=self.context(q,photos);q.add_events([(c['key'],'album/clip.mp4')]);q.db.execute('UPDATE events SET due=0');q.db.commit()
            with mock.patch.object(scheduler.n,'NativePhotos') as api:
                scheduler.resolve_events(q,root);api.assert_not_called()
            q.db.execute('UPDATE events SET due=0');q.db.commit()
            e={'id':42,'filename':'clip.mp4','filesize':7,'additional':{'thumbnail':{'unit_id':1,'sm':'ame_defect'},'video_convert_status':'ame_defect','video_convert':[]}}
            backend=mock.Mock();backend.call.side_effect=[{'folder':{'id':9,'name':'/album'}},{'list':[e]}]
            with mock.patch.object(scheduler.n,'NativePhotos',return_value=backend):scheduler.resolve_events(q,root)
            self.assertEqual(q.counts()['events'],1);self.assertEqual(q.counts()['jobs'],0)
            q.db.execute('UPDATE events SET due=0');q.db.commit();e['filesize']=8
            backend.call.side_effect=[{'folder':{'id':9,'name':'/album'}},{'list':[e]}]
            with mock.patch.object(scheduler.n,'NativePhotos',return_value=backend):scheduler.resolve_events(q,root)
            self.assertEqual(q.counts()['events'],0);self.assertEqual(q.counts()['jobs'],2)
            self.assertEqual(q.next_job()['phase'],'preview')
            for call in backend.call.call_args_list:
                if call.args[0].endswith('.Browse.Item'):self.assertEqual(call.kwargs['folder_id'],9)
            q.close()
    def test_reconciliation_is_requested_by_overflow_not_job_completion(self):
        with tempfile.TemporaryDirectory() as td:
            q=Queue(td);c=self.context(q,td);q.scan_page(c['key'],3);self.assertFalse(q.has_scan())
            q.add_job(c['key'],1,'video','a');q.finish(q.next_job());self.assertFalse(q.has_scan());self.assertIsNone(q.take_reconcile())
            q.request_reconcile('inotify-overflow');self.assertEqual(q.take_reconcile(),'inotify-overflow');self.assertIsNone(q.take_reconcile())
            q.reconcile('inotify-overflow');self.assertTrue(q.has_scan());q.close()
    def test_fresh_uploads_wait_for_index_before_starting_another_video(self):
        with tempfile.TemporaryDirectory() as td:
            q=Queue(td);c=self.context(q,td);q.scan_page(c['key'],1)
            q.add_job(c['key'],1,'video','a');q.add_events([(c['key'],'new.heic')])
            self.assertTrue(q.fresh_events());self.assertIsNone(q.next_job(allow_video=False));self.assertGreater(q.next_delay(allow_video=False),1)
            q.db.execute('UPDATE events SET created=?',(time.time()-61,));q.db.commit();self.assertFalse(q.fresh_events());q.close()

    def test_removed_item_is_deleted_instead_of_retried_forever(self):
        with tempfile.TemporaryDirectory() as td:
            q=Queue(td);c=self.context(q,td);q.add_job(c['key'],1,'video','a')
            api=mock.Mock();api.get.side_effect=ValueError('Item disappeared')
            with mock.patch.object(scheduler.n,'NativePhotos',return_value=api):scheduler.process_job(q,Path(td),None,q.next_job())
            self.assertEqual(q.counts()['jobs'],0);q.close()

    def test_daemon_does_not_rescan_between_preview_and_video_jobs(self):
        class StopRun(Exception):pass
        import select
        actual_select=select.select
        with tempfile.TemporaryDirectory() as td:
            state=Path(td);photos=state/'photos';photos.mkdir();child=mock.Mock();child.poll.return_value=None;extra=[]
            def pipe(flags):
                r,w=os.pipe();os.set_blocking(r,False);os.set_blocking(w,False);return r,w
            def start(*args,**kwargs):
                w=kwargs['pass_fds'][0];extra.append(os.dup(w));os.write(w,b'R');return child
            def wait(read,write,error,timeout):
                if timeout==60 and actual_select(read,[],[],0)[0]:return actual_select(read,[],[],0)
                raise StopRun()
            e={'id':42,'filename':'clip.mp4','filesize':8,'additional':{'thumbnail':{'unit_id':1,'sm':'ame_defect','m':'ready','xl':'ready'},'video_convert_status':'ame_defect','video_convert':[]}}
            api=mock.Mock();api.list.return_value=[e];api.get.return_value=e;phases=[]
            def process(*args,**kwargs):
                phase=kwargs['phase'];phases.append(phase)
                if phase=='preview':e['additional']['thumbnail']['sm']='ready'
                else:e['additional'].update(video_convert_status='ready',video_convert=[{'quality':'high'}])
                return True
            def discovery(q,args):self.context(q,photos)
            try:
                with mock.patch.object(scheduler.os,'pipe2',side_effect=pipe,create=True),mock.patch.object(scheduler.subprocess,'Popen',side_effect=start),mock.patch.object(scheduler.select,'select',side_effect=wait),mock.patch.object(scheduler,'discover',side_effect=discovery),mock.patch.object(scheduler.n,'NativePhotos',return_value=api),mock.patch.object(scheduler.n,'process',side_effect=process),mock.patch.object(scheduler.n,'assert_photos_version'):
                    with self.assertRaises(StopRun):scheduler.run(SimpleNamespace(state=state),None)
            finally:
                for fd in extra:os.close(fd)
            self.assertEqual(phases,['preview','video']);api.list.assert_called_once();child.terminate.assert_called_once()

if __name__=='__main__':unittest.main()
