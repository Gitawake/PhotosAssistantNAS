import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import json
import os
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/photos_assistant'))
import native_worker as n
from worker import Decoder

def entry(**changes):
    result={'filename':'test.mp4','additional':{'thumbnail':{'unit_id':42,'sm':'ready','m':'ready','xl':'ready'},'video_convert':[],'video_convert_status':'ame_defect'}}
    result['additional'].update(changes)
    return result

class NativeTests(unittest.TestCase):
    def test_large_sparse_input_uses_readonly_fd_and_detects_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'original.mp4'
            with source.open('wb') as f: f.truncate(9*1024**3)
            api=SimpleNamespace(open_original=lambda _:os.open(source,os.O_RDONLY))
            with n.open_input(api,{'filesize':source.stat().st_size}) as (fd,verify):
                self.assertEqual(os.fstat(fd).st_size,9*1024**3)
                with self.assertRaises(OSError): os.write(fd,b'x')
                self.assertEqual(list(root.iterdir()),[source])
                verify()
                with source.open('r+b') as f: f.write(b'x')
                with self.assertRaises(ValueError): verify()
            with self.assertRaises(OSError): os.fstat(fd)
    def test_writable_source_descriptor_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'original';source.write_bytes(b'original')
            api=SimpleNamespace(open_original=lambda _:os.open(source,os.O_RDWR))
            with self.assertRaises(ValueError):
                with n.open_input(api,{'filesize':8}): pass
    def test_heic_job_inherits_only_readonly_original_and_cleans_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'original.heic';source.write_bytes(b'original')
            api=SimpleNamespace(open_original=lambda _:os.open(source,os.O_RDONLY))
            item={'filename':'original.heic','filesize':8,'id':1,'additional':{
                'thumbnail':{'unit_id':42,'sm':'broken'},'resolution':{'width':4000,'height':3000}}}
            def start(command,**kwargs):
                fd=kwargs['pass_fds'][0]
                self.assertEqual(command[-4:],[str(fd),'.heic','4000','3000'])
                self.assertEqual(os.read(fd,8),b'original')
                with self.assertRaises(OSError): os.write(fd,b'x')
                self.assertFalse(any(root.rglob('source.*')))
                return SimpleNamespace(communicate=lambda **_: (b'',b'/private/media/secret.heic\nDECODER_FAILURE=compatibility\n'),returncode=1)
            with mock.patch.object(n,'require_space'), mock.patch.object(n.os,'chown'), mock.patch.object(n.subprocess,'Popen',side_effect=start):
                with self.assertLogs(level='WARNING') as logs:
                    with self.assertRaises(RuntimeError): n.process(api,item,root,SimpleNamespace(pw_uid=1,pw_gid=1))
                self.assertIn('decoder_failure=compatibility',' '.join(logs.output))
                self.assertNotIn('secret.heic',' '.join(logs.output))
            self.assertEqual(list(root.iterdir()),[source])
            self.assertEqual(source.read_bytes(),b'original')

    def test_original_path_traversal_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'Photos').mkdir();(root/'outside').write_bytes(b'x')
            (root/'Photos/link.mp4').symlink_to(root/'outside')
            api=n.NativePhotos('someone',root)
            item={'_space':'SYNO.Foto','folder_id':1,'owner_user_id':2,'filename':'link.mp4'}
            metadata={'folder':{'id':1,'owner_user_id':2,'name':'/'}}
            with mock.patch.object(api,'call',return_value=metadata), mock.patch.object(n.pwd,'getpwnam',return_value=SimpleNamespace(pw_dir=str(root))):
                with self.assertRaises(OSError): api.open_original(item)
                item['filename']='../outside'
                with self.assertRaises(ValueError): api.open_original(item)
    def test_missing_video_with_ready_thumbnails_is_processed(self):
        self.assertEqual(n.needs(entry()),(False,True))
    def test_existing_high_variant_never_overwritten(self):
        self.assertEqual(n.needs(entry(video_convert=[{'quality':'high'}])),(False,False))
    def test_pending_unknown_and_ready_not_transcoded(self):
        for status in ['pending','future','ready']:
            self.assertFalse(n.needs(entry(video_convert_status=status))[1])
    def test_local_api_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            api=n.NativePhotos('someone',folder)
            with self.assertRaises(ValueError):
                api.invoke('SYNO.Core.User','create',1,Path(folder)/'out')
    def test_local_json_stdout_fallback(self):
        response=SimpleNamespace(stdout=b'{"success":true,"data":{"list":[]}}',stderr=b'',returncode=0)
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(n.subprocess,'run',return_value=response):
            self.assertEqual(n.NativePhotos('someone',folder).list('SYNO.Foto',0),[])
    def test_outfile_success_wins_over_transport_error(self):
        def invoke(command,**kwargs):
            out=next(x[8:] for x in command if x.startswith('outfile='))
            Path(out).write_text('{"success":true,"data":{"list":[]}}')
            return SimpleNamespace(stdout=b'{"success":false,"error":{"code":117}}',stderr=b'',returncode=0)
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(n.subprocess,'run',side_effect=invoke):
            self.assertEqual(n.NativePhotos('someone',folder).list('SYNO.Foto',0),[])
    def test_error_stdout_is_never_success(self):
        response=SimpleNamespace(stdout=b'{"success":false,"error":{"code":117}}',stderr=b'',returncode=0)
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(n.subprocess,'run',return_value=response):
            with self.assertRaises(n.ApiError): n.NativePhotos('someone',folder).list('SYNO.Foto',0)
    def test_tampered_decoder_output_rejected(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'file').write_bytes(b'x');(root/'link').symlink_to(root/'file')
            with self.assertRaises(OSError):n.checked_copy(root/'link',root/'out',os.getuid(),100)
            os.link(root/'file',root/'hardlink')
            with self.assertRaises(ValueError):n.checked_copy(root/'file',root/'out',os.getuid(),100)

if __name__=='__main__':unittest.main()
