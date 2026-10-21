import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import json
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
