import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import online_bootstrap as online
import generate_bootstrap
import check_public


def source_tar(path,name,link=False):
    with tarfile.open(path,'w:gz') as archive:
        member=tarfile.TarInfo(name)
        if link:
            member.type=tarfile.SYMTYPE;member.linkname='/etc/passwd';archive.addfile(member)
        else:
            member.size=1;archive.addfile(member,io.BytesIO(b'x'))


class BootstrapTests(unittest.TestCase):
    def test_downloadable_script_matches_tested_source(self):
        self.assertEqual((ROOT/'bootstrap.sh').read_text(),generate_bootstrap.content())
    def test_pinned_revision_needs_no_api_lookup(self):
        with mock.patch.object(online,'request') as request:
            self.assertEqual(online.resolve_ref('A'*40),'a'*40)
            request.assert_not_called()
    def test_source_archive_escape_and_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            for name,link in [('../escape',False),('/escape',False),('source/link',True)]:
                source_tar(folder/'source.tar.gz',name,link)
                with self.assertRaises(ValueError):online.extract_source(folder/'source.tar.gz',folder/'out')
    def test_safe_source_is_extracted(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source_tar(folder/'source.tar.gz','source/README.md')
            root=online.extract_source(folder/'source.tar.gz',folder/'out')
            self.assertEqual((root/'README.md').read_bytes(),b'x')
    def test_export_rejects_unexpected_root_file(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'private.txt').write_text('private fixture')
            with self.assertRaises(ValueError):check_public.check(Path(folder))

if __name__=='__main__':unittest.main()
