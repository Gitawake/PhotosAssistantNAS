from pathlib import Path
import sys
import tempfile
import unittest
import os
import json
from unittest import mock
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/photos_assistant'))
from worker import Decoder,atomic_json,video_budget,require_space,FREE_HEADROOM


class WorkerTests(unittest.TestCase):
    def test_fd_input_is_seekable_rewound_and_inherited_only_by_ffmpeg(self):
        with tempfile.TemporaryFile() as source:
            source.write(b'1234');source.flush()
            decoder=Decoder('/runtime');decoder.source_fd=source.fileno();decoder.nested=True
            args=decoder.input_args('fd:')
            self.assertEqual(os.lseek(source.fileno(),0,os.SEEK_CUR),0)
            self.assertEqual(args,['-fd',str(source.fileno()),'-protocol_whitelist','fd','-i','fd:'])
            child=mock.Mock(returncode=0);child.communicate.return_value=(b'{}',b'')
            with mock.patch('worker.subprocess.Popen',return_value=child) as start, mock.patch('worker.require_space'):
                decoder.run('ffmpeg','ffprobe',args,Path('/unused'))
                self.assertEqual(start.call_args.kwargs['pass_fds'],(source.fileno(),))
                decoder.run('imagemagick','convert',[],Path('/unused'))
                self.assertEqual(start.call_args.kwargs['pass_fds'],())
                decoder.run('heic','heic_fd',[source.fileno(),'/unused',0,0],Path('/unused'))
                self.assertEqual(start.call_args.kwargs['pass_fds'],(source.fileno(),))
                self.assertEqual(start.call_args.kwargs['env']['LD_PRELOAD'],'/runtime/imagemagick/lib/libjemalloc.so.2')
    def test_heic_preview_uses_direct_helper_without_encoded_intermediate(self):
        decoder=Decoder('/runtime');decoder.source_fd=5;decoder.expected_size=(4032,3024)
        with mock.patch.object(decoder,'run') as run:
            result=decoder.generate('fd:','.heic',Path('/work'))
            self.assertEqual(result, {label:Path('/work')/(label+'.jpg') for label in ('SM','M','XL')})
            self.assertEqual(run.call_args.args,('heic','heic_fd',[5,Path('/work'),4032,3024],Path('/work')))
        with self.assertRaises(ValueError): decoder.generate(Path('/source.heic'),'.heic',Path('/work'))
    def test_full_range_output_is_rejected_by_compatibility_guard(self):
        decoder=Decoder('/runtime')
        video={'codec_type':'video','codec_name':'h264','pix_fmt':'yuv420p',
               'level':31,'width':720,'height':1280,'color_transfer':'bt709'}
        for pixel_format,expected in (('yuv420p',True),('yuvj420p',False)):
            video['pix_fmt']=pixel_format
            with mock.patch.object(decoder,'run',return_value=json.dumps({'streams':[video]})):
                self.assertEqual(decoder.compatible_video(Path('/work/out.mp4'),Path('/work')),expected)

    def test_duration_and_output_budget(self):
        for duration in (0,-1,21601,float('nan'),float('inf')):
            with self.assertRaises(ValueError): video_budget(duration)
        self.assertEqual(video_budget(60),3*22500000+1024**3)
        self.assertGreater(video_budget(21600),16*1024**3)
    def test_space_guard_and_running_process_cleanup(self):
        with mock.patch('worker.shutil.disk_usage',return_value=SimpleNamespace(free=FREE_HEADROOM-1)):
            with self.assertRaises(RuntimeError): require_space('/unused')
            child=mock.Mock(pid=123)
            decoder=Decoder('/runtime');decoder.nested=True
            with mock.patch('worker.subprocess.Popen',return_value=child):
                with self.assertRaises(RuntimeError): decoder.run('ffmpeg','ffmpeg',[],Path('/unused'))
            child.kill.assert_called_once();child.wait.assert_called_once()
    def test_state_is_private(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'state.json';atomic_json(path,{'cursor':0})
            self.assertEqual(path.stat().st_mode&0o777,0o600)
    def test_decoder_environment_does_not_use_other_packages(self):
        decoder=Decoder('/private/runtime')
        im=decoder.env('imagemagick',Path('/private/work'))
        ff=decoder.env('ffmpeg',Path('/private/work'))
        self.assertEqual(im['LD_LIBRARY_PATH'],'/private/runtime/imagemagick/lib')
        self.assertNotIn('imagemagick',ff['LD_LIBRARY_PATH'])
        self.assertNotIn('/var/packages/',ff['LD_LIBRARY_PATH'])
        self.assertNotIn('PYTHONPATH',im)

if __name__=='__main__':unittest.main()
