import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import json
import os
import errno
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
    def test_large_sparse_input_is_not_rejected_or_read_into_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'original.mp4'
            with source.open('wb') as f: f.truncate(9*1024**3)
            api=SimpleNamespace(open_original=lambda _:os.open(source,os.O_RDONLY))
            def clone(out,request,original):
                os.ftruncate(out,os.fstat(original).st_size)
            with mock.patch.object(n.fcntl,'ioctl',side_effect=clone), mock.patch.object(n,'require_space'):
                with n.stage_original(api,{'id':1,'filesize':source.stat().st_size},root/'snapshot.mp4') as verify:
                    verify()
                    self.assertEqual((root/'snapshot.mp4').stat().st_size,9*1024**3)
                    with source.open('r+b') as f: f.write(b'x')
                    with self.assertRaises(ValueError): verify()
    def test_unsupported_clone_copies_without_changing_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'original';source.write_bytes(b'original')
            api=SimpleNamespace(open_original=lambda _:os.open(source,os.O_RDONLY))
            with mock.patch.object(n.fcntl,'ioctl',side_effect=OSError(errno.EXDEV,'cross-device')), mock.patch.object(n,'require_space'):
                with n.stage_original(api,{'id':1,'filesize':8},root/'snapshot') as verify:
                    self.assertEqual((root/'snapshot').read_bytes(),b'original')
                    (root/'snapshot').write_bytes(b'changed!');verify()
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
