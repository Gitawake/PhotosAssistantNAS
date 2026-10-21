from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/photos_assistant'))
from worker import Decoder,atomic_json


class WorkerTests(unittest.TestCase):
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
