import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import runtime
from private_elf import private_elf, elf_needed


def spk(path,members):
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w:gz') as archive:
        for name,value in members.items():
            item=tarfile.TarInfo(name)
            if isinstance(value,tuple):
                item.type=tarfile.SYMTYPE;item.linkname=value[0];archive.addfile(item)
            else:
                item.size=len(value);item.mode=0o755;archive.addfile(item,io.BytesIO(value))
    with tarfile.open(path,'w') as archive:
        for name,value in [('INFO',b'package="fixture"\n'),('package.tgz',payload.getvalue())]:
            item=tarfile.TarInfo(name);item.size=len(value);archive.addfile(item,io.BytesIO(value))


class RuntimeTests(unittest.TestCase):
    def test_driver_dependency_closure(self):
        def needed(data): return ['dependency.so'] if data==b'shader' else []
        with mock.patch.object(runtime,'elf_needed',side_effect=needed):
            _,files,_=self.append({'lib/libshaderc_shared.so.1':b'shader',
                'lib/dependency.so':b'required','lib/unrelated.so':b'excluded'},'videodriver')
        self.assertIn('runtime/videodriver/lib/dependency.so',files)
        self.assertNotIn('runtime/videodriver/lib/unrelated.so',files)
    def test_private_gpu_driver_includes_dynamically_loaded_dependencies(self):
        with mock.patch.object(runtime,'elf_needed',side_effect=lambda data:['libigdgmm.so.12'] if data==b'intel-driver' else []):
            _,files,_=self.append({'lib/iHD_drv_video.so':b'intel-driver',
                'lib/libigdgmm.so.12':b'gmm','lib/libmfxhw64.so.1':b'qsv-runtime'},'videodriver')
        self.assertIn('runtime/videodriver/lib/iHD_drv_video.so',files)
        self.assertIn('runtime/videodriver/lib/libigdgmm.so.12',files)
        self.assertIn('runtime/videodriver/lib/libmfxhw64.so.1',files)
    def test_elf_dependency_string_table(self):
        ident=b'\x7fELF\x02\x01'+b'\0'*10
        header=struct.pack('<16sHHIQQQIHHHHHH',ident,3,62,1,0,64,0,0,64,56,2,0,0,0)
        strings=b'\0libneeded.so\0'
        size=240+len(strings)
        load=struct.pack('<IIQQQQQQ',1,0,0,0x1000,0,size,size,8)
        dynamic=struct.pack('<IIQQQQQQ',2,0,176,0,0,64,64,8)
        tags=struct.pack('<QQQQQQQQ',1,1,5,0x1000+240,10,len(strings),0,0)
        self.assertEqual(elf_needed(header+load+dynamic+tags+strings),['libneeded.so'])
    def append(self,members,name='imagemagick'):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.spk';spk(path,members)
            result=io.BytesIO()
            with tarfile.open(fileobj=result,mode='w') as archive:
                manifest=runtime.append_runtime(archive,name,path,ROOT/'src/photos_assistant/policy.xml')
            with tarfile.open(fileobj=io.BytesIO(result.getvalue())) as archive:
                files={m.name:archive.extractfile(m).read() for m in archive if m.isfile()}
                links={m.name:m.linkname for m in archive if m.issym()}
            return manifest,files,links
    def test_no_vendor_scripts_and_private_policy(self):
        manifest,files,links=self.append({'bin/magick':b'fixture','etc/ImageMagick-7/policy.xml':b'unsafe',
                                        'scripts/postinst':b'must-not-run','lib/alias.so':('real.so',),'lib/real.so':b'lib'})
        self.assertNotIn('runtime/imagemagick/scripts/postinst',files)
        self.assertIn(b'rights="none"',files['runtime/imagemagick/etc/ImageMagick-7/policy.xml'])
        self.assertEqual(links['runtime/imagemagick/lib/alias.so'],'real.so')
    def test_driver_selection_includes_link_targets_only(self):
        _,files,links=self.append({'lib/libdrm.so.2':('libdrm.so.2.0',),'lib/libdrm.so.2.0':b'drm',
                                  'lib/unrelated-driver.so':b'excluded','bin/tool':b'excluded'},'videodriver')
        self.assertEqual(set(files),{'runtime/videodriver/lib/libdrm.so.2.0'})
    def test_nonfree_is_recorded(self):
        manifest,_,_=self.append({'bin/ffmpeg':b'--enable-gpl --enable-nonfree'},'ffmpeg')
        self.assertTrue(manifest['nonfree_enabled'])
    def test_archive_escape_is_rejected(self):
        with self.assertRaises(ValueError):self.append({'../escape':b'x'})
        with self.assertRaises(ValueError):self.append({'lib/alias':('../../escape',)})
        with self.assertRaises(ValueError):self.append({'lib/a':('b',),'lib/b':('a',)})
    def test_offline_never_fetches_and_bad_cache_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder,mock.patch.object(runtime.urllib.request,'urlopen') as fetch:
            spec={'url':'https://packages.synocommunity.com/fixture.spk','sha256':'0'*64}
            with self.assertRaises(FileNotFoundError):runtime.download_locked('fixture',spec,folder,True)
            (Path(folder)/'fixture.spk').write_bytes(b'wrong')
            with self.assertRaises(ValueError):runtime.download_locked('fixture',spec,folder,True)
            fetch.assert_not_called()
    def test_elf_search_paths_are_cleared(self):
        ident=b'\x7fELF\x02\x01'+b'\0'*10
        header=struct.pack('<16sHHIQQQIHHHHHH',ident,3,62,1,0,64,0,0,64,56,1,0,0,0)
        segment=struct.pack('<IIQQQQQQ',2,0,120,0,0,48,48,8)
        data=header+segment+struct.pack('<QQQQQQ',15,99,29,101,0,0)
        changed,count=private_elf(data)
        self.assertEqual(count,2)
        self.assertEqual(struct.unpack_from('<QQQQ',changed,120),(29,0,29,0))
        self.assertEqual(changed[:120],data[:120])

if __name__=='__main__':unittest.main()
